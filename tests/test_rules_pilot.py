import asyncio
import pytest
from hunter.jev_pilot import JevPilot, PILOT_QUESTIONS, PilotUnavailable
from hunter.rules_pilot import RulesClient, decide

COURSE = {'burn_needed': False, 'burn_heading_degrees': 90.0, 'burn_seconds': 0.0}
AIM = {'lead_degrees_off_nose': 5.0, 'on_target': False}


def state(**parts):
    base = {'motion': {'brake': {'speed_state': 'slow', 'thrust_effect': 'speeds_up'}},
            'visible_contacts': [], 'engage': None, 'collect_powerup': None,
            'follow_player': None, 'wall_follow': None}
    base.update(parts)
    return base


def enemy(aim=AIM):
    return {'allegiance': 'enemy', 'aim': aim}


def test_nothing_to_do_holds_still():
    assert decide(state()) == {'turn': 'none', 'thrust': 'coast', 'fire': 'hold'}


def test_too_fast_brakes_whatever_else_is_happening():
    s = state(visible_contacts=[enemy()], motion={'brake': {'speed_state': 'too_fast'}})
    assert decide(s) == {'turn': 'course', 'thrust': 'burn', 'fire': 'fire'}


def test_an_enemy_with_an_aim_is_tracked_and_fired_on():
    assert decide(state(visible_contacts=[enemy()]))['turn'] == 'track'
    assert decide(state(visible_contacts=[enemy()]))['fire'] == 'fire'


def test_an_enemy_without_an_aim_is_not_a_target():
    s = state(visible_contacts=[enemy(aim=None)])
    assert decide(s)['turn'] == 'none' and decide(s)['fire'] == 'hold'


def test_the_player_is_never_a_target():
    s = state(visible_contacts=[{'allegiance': 'friendly', 'aim': AIM}])
    assert decide(s)['fire'] == 'hold'


@pytest.mark.parametrize('offset,turn', [(-30, 'left'), (30, 'right'), (0, 'none'),
                                         (-20, 'none'), (20, 'none')])
def test_alongside_the_player_the_nose_follows_its_bearing(offset, turn):
    s = state(follow_player={'degrees_off_nose_at_next_decision': offset, 'course': None})
    assert decide(s)['turn'] == turn


def test_a_course_is_flown_when_no_enemy_has_an_aim():
    s = state(wall_follow={'course': dict(COURSE, burn_needed=True)})
    assert decide(s) == {'turn': 'course', 'thrust': 'burn', 'fire': 'hold'}


def test_a_course_that_needs_no_burn_coasts():
    s = state(wall_follow={'course': COURSE})
    assert decide(s) == {'turn': 'course', 'thrust': 'coast', 'fire': 'hold'}


def test_course_source_priority_is_powerup_then_player_then_wall():
    powerup = {'course': dict(COURSE, burn_needed=True)}
    player = {'course': COURSE, 'degrees_off_nose_at_next_decision': 0}
    assert decide(state(collect_powerup=powerup, follow_player=player))['thrust'] == 'burn'
    # A player block with no course (alongside) hides the wall-follow course beneath it.
    assert decide(state(follow_player={'course': None, 'degrees_off_nose_at_next_decision': 0},
                        wall_follow={'course': dict(COURSE, burn_needed=True)}))['turn'] == 'none'


def test_engaging_burns_while_the_approach_needs_it():
    s = state(visible_contacts=[enemy()], engage={'burn_needed': True})
    assert decide(s) == {'turn': 'track', 'thrust': 'burn', 'fire': 'fire'}


def test_a_still_hunter_in_range_pulses():
    s = state(visible_contacts=[enemy()], engage={
        'burn_needed': False, 'holding_still': True, 'range_state': 'in_range'})
    assert decide(s)['thrust'] == 'pulse'


@pytest.mark.parametrize('engage', [
    {'burn_needed': False, 'holding_still': False, 'range_state': 'in_range'},
    {'burn_needed': False, 'holding_still': True, 'range_state': 'far'}])
def test_otherwise_engaging_coasts(engage):
    assert decide(state(visible_contacts=[enemy()], engage=engage))['thrust'] == 'coast'


def test_thrust_takes_off_speed_when_nothing_else_applies():
    s = state(motion={'brake': {'speed_state': 'cruising', 'thrust_effect': 'slows'}})
    assert decide(s)['thrust'] == 'thrust'


def test_every_answer_is_a_choice_the_questions_define():
    for s in (state(), state(visible_contacts=[enemy()]),
              state(follow_player={'degrees_off_nose_at_next_decision': 90, 'course': None})):
        for head, choice in decide(s).items():
            assert choice in PILOT_QUESTIONS[head]['criteria']


def test_empty_state_is_decidable():
    assert decide({}) == {'turn': 'none', 'thrust': 'coast', 'fire': 'hold'}


def test_client_answers_in_the_shape_jev_pilot_reads():
    result = asyncio.run(RulesClient().system_one(state=state(visible_contacts=[enemy()]), questions={}))
    assert result.choices['turn'].choice == 'track'
    assert result.choices['turn'].confidence == 1.0
    assert result.choices['turn'].probabilities == {'track': 1.0}


def test_jev_pilot_decides_with_the_rules_client():
    from entities.enemy import Enemy
    from entities.hunter_ship import HunterShip
    from hunter.model import NEUTRAL
    from hunter.perception import HunterPerception
    from tests.test_hunter_perception import maze
    ship = HunterShip((150, 150))
    ship.angle = 0
    obs = HunterPerception().observe(ship, maze(), None, [Enemy((250, 150), 'patrol', 1)], [], NEUTRAL, 0, 1)
    decision = asyncio.run(JevPilot(RulesClient()).decide(obs))
    assert decision.action.track and decision.action.fire
    assert decision.confidence == 1.0
