"""A pilot that applies the Jev question criteria as plain rules, with no model or key."""
from types import SimpleNamespace
from hunter.rule_params import DEFAULT


def _navigation_course(state):
    """The course the navigator flies: the first of powerup, player, wall to be present."""
    for key in ('collect_powerup', 'follow_player', 'wall_follow'):
        block = state.get(key)
        if block is not None:
            return block.get('course')
    return None


def decide(state, params=None):
    """{'turn', 'thrust', 'fire'} choices for a pilot state, per the criteria in PILOT_QUESTIONS."""
    params = params or DEFAULT
    brake = (state.get('motion') or {}).get('brake') or {}
    too_fast = brake.get('speed_state') == 'too_fast'
    enemies = [c for c in state.get('visible_contacts') or [] if c.get('allegiance') == 'enemy']
    aimed = any(c.get('aim') for c in enemies)
    course = _navigation_course(state)
    engage = state.get('engage')

    if too_fast or (not aimed and course is not None):
        turn = 'course'
    elif aimed:
        turn = 'track'
    else:
        offset = (state.get('follow_player') or {}).get('degrees_off_nose_at_next_decision')
        turn = ('left' if offset is not None and offset < -params.steer_band_degrees else
                'right' if offset is not None and offset > params.steer_band_degrees else 'none')

    if too_fast or (engage and engage.get('burn_needed')) or (
            not engage and course and course.get('burn_needed')):
        thrust = 'burn'
    elif engage and engage.get('holding_still') and engage.get('range_state') == 'in_range':
        thrust = 'pulse'
    elif not engage and course is None and brake.get('thrust_effect') == 'slows':
        thrust = 'thrust'
    else:
        thrust = 'coast'
    return {'turn': turn, 'thrust': thrust, 'fire': 'fire' if aimed else 'hold'}


class RulesClient:
    """Answers like the Jev client, from decide()."""

    def __init__(self, params=None):
        self.params = params

    async def system_one(self, *, state, questions=None, **_):
        return SimpleNamespace(choices={
            head: SimpleNamespace(choice=choice, confidence=1.0, probabilities={choice: 1.0})
            for head, choice in decide(state, self.params).items()})

    async def aclose(self):
        pass
