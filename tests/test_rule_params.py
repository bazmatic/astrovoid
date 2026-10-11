import asyncio
import json
import pytest
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.jev_pilot import JevPilot
from hunter.model import ACTIONS, NEUTRAL
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.rule_params import BOUNDS, DEFAULT, RuleParams
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
    assert set(BOUNDS) == set(DEFAULT.to_dict())


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
