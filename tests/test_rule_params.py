import asyncio
import json
import pytest
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.jev_pilot import JevPilot
from hunter.model import ACTIONS, NEUTRAL
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.rule_params import BOUNDS, DEFAULT, SWITCHES, RuleParams
from hunter.rules_pilot import RulesClient, decide
from tests.test_hunter_perception import maze


def raw_state(enemies=(), heading=10):
    ship = HunterShip((150, 150))
    ship.vx, ship.vy, ship.angle = 3, 1, heading
    obs = HunterPerception().observe(ship, maze(), None, list(enemies), [], NEUTRAL, 0, 1)
    return json.loads(obs.state_json), obs


def test_defaults_are_todays_values():
    assert DEFAULT == RuleParams(
        steer_band_degrees=20.0, engage_standoff_cells=1.5, too_close_ratio=0.6, far_ratio=1.15,
        harmless_speed=15.0, wall_follow_cruise=0.6, course_approach_fraction=0.7,
        cruising_speed_fraction=0.5, pulse_frames=6.0, request_interval=0.25)


def test_every_default_is_inside_its_bounds():
    for name, (low, high) in BOUNDS.items():
        assert low < getattr(DEFAULT, name) < high
    assert set(BOUNDS) == set(DEFAULT.to_dict()) - set(SWITCHES)


def test_default_params_change_nothing():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    assert pilot_state(raw) == pilot_state(raw, DEFAULT)


def test_round_trip_through_a_dict():
    params = RuleParams(steer_band_degrees=30.0)
    assert RuleParams.from_dict(params.to_dict()) == params
    assert RuleParams.from_dict({'steer_band_degrees': 30}).steer_band_degrees == 30.0


@pytest.mark.parametrize('bad', [{'warp_factor': 2}, {'steer_band_degrees': 'wide'},
                                 {'steer_band_degrees': True}, {'steer_band_degrees': 1e9},
                                 {'steer_band_degrees': -5}])
def test_bad_params_are_rejected(bad):
    with pytest.raises(ValueError):
        RuleParams.from_dict(bad)


def test_engage_standoff_reaches_the_engage_reading():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    near = pilot_state(raw, RuleParams(engage_standoff_cells=1.0))['engage']
    far = pilot_state(raw, RuleParams(engage_standoff_cells=3.0))['engage']
    assert far['standoff_metres'] == pytest.approx(3 * near['standoff_metres'])


def test_harmless_speed_reaches_holding_still():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    speed = pilot_state(raw)['speed_metres_per_second']
    assert pilot_state(raw, RuleParams(harmless_speed=speed + 5))['engage']['holding_still']
    assert not pilot_state(raw, RuleParams(harmless_speed=speed - 5))['engage']['holding_still']


def test_ratios_reach_the_range_state():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    standoff = pilot_state(raw)['engage']['standoff_metres']
    distance = pilot_state(raw)['engage']['distance_metres']
    wide = RuleParams(too_close_ratio=distance / standoff * 1.1)
    assert pilot_state(raw, wide)['engage']['range_state'] == 'too_close'
    tight = RuleParams(far_ratio=distance / standoff * 0.9)
    assert pilot_state(raw, tight)['engage']['range_state'] == 'far'


def test_cruising_fraction_reaches_the_speed_state():
    ship = HunterShip((150, 150))
    ship.vx, ship.vy, ship.angle = 0.5, 0, 0
    obs = HunterPerception().observe(ship, maze(), None, [], [], NEUTRAL, 0, 1)
    raw = json.loads(obs.state_json)
    assert pilot_state(raw)['motion']['brake']['speed_state'] == 'slow'
    tiny = RuleParams(cruising_speed_fraction=0.0001)
    assert pilot_state(raw, tiny)['motion']['brake']['speed_state'] == 'cruising'


def test_steer_band_reaches_the_turn_choice():
    follow = {'degrees_off_nose_at_next_decision': 25.0, 'course': None}
    state = {'follow_player': follow, 'motion': {'brake': {}}}
    assert decide(state)['turn'] == 'right'
    assert decide(state, RuleParams(steer_band_degrees=30.0))['turn'] == 'none'


def test_rules_client_passes_params_to_decide():
    follow = {'degrees_off_nose_at_next_decision': 25.0, 'course': None}
    state = {'follow_player': follow, 'motion': {'brake': {}}}
    result = asyncio.run(RulesClient(RuleParams(steer_band_degrees=30.0)).system_one(state=state))
    assert result.choices['turn'].choice == 'none'


def test_pulse_frames_reach_the_action():
    raw, obs = raw_state([Enemy((250, 150), 'patrol', 1)])

    class Pulse:
        async def system_one(self, **_):
            from types import SimpleNamespace
            pick = {'turn': 'none', 'thrust': 'pulse', 'fire': 'hold'}
            return SimpleNamespace(choices={k: SimpleNamespace(choice=v, confidence=1.0)
                                            for k, v in pick.items()})
    default = asyncio.run(JevPilot(Pulse()).decide(obs)).action
    longer = asyncio.run(JevPilot(Pulse(), RuleParams(pulse_frames=12.0)).decide(obs)).action
    assert default.burn_frames == ACTIONS['none_pulse_hold'].burn_frames
    assert longer.burn_frames == 12.0


# --- structural switches ------------------------------------------------------

def moving_away_state():
    """A real raw state with one visible enemy that runs away too fast to be shot."""
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    raw['visible_contacts'][0]['velocity'] = [20.0, 0.0]
    return raw


def test_switches_default_off_and_leave_the_state_unchanged():
    assert SWITCHES == ('pursue_unaimed', 'investigate_memory')
    assert DEFAULT.pursue_unaimed is False and DEFAULT.investigate_memory is False
    raw = moving_away_state()
    state = pilot_state(raw)
    assert 'pursue' not in state and 'investigate' not in state


def test_switches_round_trip_and_reject_non_booleans():
    params = RuleParams(pursue_unaimed=True)
    assert RuleParams.from_dict(params.to_dict()) == params
    assert RuleParams.from_dict({'investigate_memory': True}).investigate_memory is True
    for bad in ({'pursue_unaimed': 1}, {'pursue_unaimed': 'yes'}, {'investigate_memory': 0.5}):
        with pytest.raises(ValueError):
            RuleParams.from_dict(bad)
    assert hash(params) != hash(DEFAULT) or params != DEFAULT


def test_pursue_gives_a_course_to_a_visible_enemy_that_cannot_be_aimed_at():
    raw = moving_away_state()
    assert pilot_state(raw)['visible_contacts'][0]['aim'] is None
    pursue = pilot_state(raw, RuleParams(pursue_unaimed=True))['pursue']
    assert pursue['distance_metres'] == pytest.approx(100.0)
    assert pursue['course'] is not None and 'burn_needed' in pursue['course']


def test_pursue_is_absent_when_the_enemy_can_be_aimed_at():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    assert pilot_state(raw)['visible_contacts'][0]['aim'] is not None
    assert pilot_state(raw, RuleParams(pursue_unaimed=True)).get('pursue') is None


def test_investigate_heads_for_the_nearest_remembered_enemy_that_is_out_of_sight():
    raw, _ = raw_state()
    raw['visible_contacts'] = []
    near = {'id': 7, 'type': 'patrol', 'allegiance': 'enemy', 'position': [400, 150],
            'relative_position': [250, 0], 'velocity': [0, 0], 'heading': 0, 'radius': 8,
            'distance': 250.0, 'bearing': 0.0, 'age': 2.0}
    far = dict(near, id=8, position=[900, 150], relative_position=[750, 0], distance=750.0)
    raw['remembered_contacts'] = [far, near]
    investigate = pilot_state(raw, RuleParams(investigate_memory=True))['investigate']
    assert investigate['distance_metres'] == pytest.approx(250.0)
    assert investigate['course'] is not None
    assert 'investigate' not in pilot_state(raw)


def test_investigate_ignores_a_remembered_enemy_that_is_visible_again():
    raw, _ = raw_state([Enemy((250, 150), 'patrol', 1)])
    seen = raw['visible_contacts'][0]
    raw['remembered_contacts'] = [dict(seen, age=1.0)]
    assert pilot_state(raw, RuleParams(investigate_memory=True)).get('investigate') is None
