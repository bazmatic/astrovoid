import asyncio
import json
import math
import pytest
import creatures
from tests.hunter_fixture import HunterRig
from hunter.jev_pilot import JevPilot
from hunter.model import ACTIONS, NEUTRAL
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.rule_params import BOUNDS, DEFAULT, SWITCHES, RuleParams
from hunter.rules_pilot import RulesClient, decide
from tests.test_hunter_perception import maze


def raw_state(enemies=(), heading=10):
    ship = HunterRig((150, 150))
    ship.vx, ship.vy, ship.angle = 3, 1, heading
    obs = HunterPerception().observe(ship, maze(), None, list(enemies), [], NEUTRAL, 0, 1)
    return json.loads(obs.state_json), obs


def test_defaults_are_todays_values():
    assert DEFAULT == RuleParams(
        steer_band_degrees=20.0, engage_standoff_cells=1.5, too_close_ratio=0.6, far_ratio=1.15,
        harmless_speed=15.0, wall_follow_cruise=0.6, wall_lookahead_cells=0.75,
        course_approach_fraction=0.7, cruising_speed_fraction=0.5, pulse_frames=6.0,
        strafe_cells=1.0, thrust_multiplier=0.25)


def test_every_default_is_inside_its_bounds():
    for name, (low, high) in BOUNDS.items():
        assert low < getattr(DEFAULT, name) < high
    assert set(BOUNDS) == set(DEFAULT.to_dict()) - set(SWITCHES)


def test_default_params_change_nothing():
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
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
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
    near = pilot_state(raw, RuleParams(engage_standoff_cells=1.0))['engage']
    far = pilot_state(raw, RuleParams(engage_standoff_cells=3.0))['engage']
    assert far['standoff_metres'] == pytest.approx(3 * near['standoff_metres'])


def test_harmless_speed_reaches_holding_still():
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
    speed = pilot_state(raw)['speed_metres_per_second']
    assert pilot_state(raw, RuleParams(harmless_speed=speed + 5))['engage']['holding_still']
    assert not pilot_state(raw, RuleParams(harmless_speed=speed - 5))['engage']['holding_still']


def test_ratios_reach_the_range_state():
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
    standoff = pilot_state(raw)['engage']['standoff_metres']
    distance = pilot_state(raw)['engage']['distance_metres']
    wide = RuleParams(too_close_ratio=distance / standoff * 1.1)
    assert pilot_state(raw, wide)['engage']['range_state'] == 'too_close'
    tight = RuleParams(far_ratio=distance / standoff * 0.9)
    assert pilot_state(raw, tight)['engage']['range_state'] == 'far'


def test_cruising_fraction_reaches_the_speed_state():
    ship = HunterRig((150, 150))
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
    raw, obs = raw_state([creatures.build('patrol', (250, 150), 1)])

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
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
    raw['visible_contacts'][0]['velocity'] = [20.0, 0.0]
    return raw


def test_switches_default_off_and_leave_the_state_unchanged():
    assert SWITCHES == ('pursue_unaimed', 'investigate_memory', 'strafe', 'hunt_first')
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
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
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
    raw, _ = raw_state([creatures.build('patrol', (250, 150), 1)])
    seen = raw['visible_contacts'][0]
    raw['remembered_contacts'] = [dict(seen, age=1.0)]
    assert pilot_state(raw, RuleParams(investigate_memory=True)).get('investigate') is None


# --- the rules pilot's own defaults ---------------------------------------------

def test_rules_defaults_are_the_global_defaults_plus_the_adopted_switches():
    from dataclasses import replace
    from hunter.rule_params import RULES
    assert RULES == replace(DEFAULT, investigate_memory=True, wall_follow_cruise=2.0,
                            wall_lookahead_cells=2.5, turn_rate_multiplier=2.0, hunt_first=True)
    assert DEFAULT.investigate_memory is False   # Jev is unchanged
    assert DEFAULT.wall_follow_cruise == 0.6 and DEFAULT.wall_lookahead_cells == 0.75


def test_the_rules_client_carries_the_rules_defaults_and_jev_pilot_uses_them():
    from hunter.rule_params import RULES
    client = RulesClient()
    assert client.params == RULES
    assert JevPilot(client).params == RULES
    custom = RuleParams(steer_band_degrees=33.0)
    assert JevPilot(RulesClient(custom)).params == custom
    assert JevPilot(RulesClient(custom), RuleParams(steer_band_degrees=9.0)).params.steer_band_degrees == 9.0

    class NotRules:
        async def system_one(self, **_):
            raise AssertionError
    assert JevPilot(NotRules()).params == DEFAULT


def test_the_rules_pilot_investigates_a_remembered_enemy_by_default():
    from hunter.rule_params import RULES
    raw, obs = raw_state()
    raw['self']['velocity'] = [0.2, 0.0]   # slow, so braking does not take the course
    raw['visible_contacts'] = []
    raw['remembered_contacts'] = [{
        'id': 7, 'type': 'patrol', 'allegiance': 'enemy', 'position': [150, 600],
        'relative_position': [0, 450], 'velocity': [0, 0], 'heading': 0, 'radius': 8,
        'distance': 450.0, 'bearing': 90.0, 'age': 2.0}]
    observation = obs.__class__(obs.generation, obs.snapshot_at, json.dumps(raw))
    expected = pilot_state(raw, RULES)['investigate']['course']['burn_heading_degrees']
    action = asyncio.run(JevPilot(RulesClient()).decide(observation)).action
    assert action.course and action.burn_heading == pytest.approx(expected)
    plain = asyncio.run(JevPilot(RulesClient(DEFAULT)).decide(observation)).action
    assert plain.burn_heading != pytest.approx(expected, abs=0.5) or not plain.course


def test_request_interval_is_not_a_rule_parameter():
    # It only ever worked inside the lab: the game's controller uses its own interval.
    assert 'request_interval' not in DEFAULT.to_dict()
    assert 'request_interval' not in BOUNDS
    with pytest.raises(ValueError):
        RuleParams.from_dict({'request_interval': 0.2})


# --- the strafe switch --------------------------------------------------------------

def strafing_state(walls=None, tracking=True, heading=0, speed=0.3):
    """A slow hunter aiming at an enemy dead ahead, last steering `track`, with the given walls."""
    ship = HunterRig((150, 150))
    ship.vx, ship.vy, ship.angle = speed, 0, heading
    obs = HunterPerception().observe(ship, maze(), None, [creatures.build('patrol', (250, 150), 1)], [], NEUTRAL, 0, 1)
    raw = json.loads(obs.state_json)
    raw['previous_action'] = {'track': tracking, 'turn': 0}
    if walls is not None:
        raw['visible_walls'] = walls
    return raw


def test_strafe_is_a_switch_that_defaults_off():
    assert 'strafe' in SWITCHES and DEFAULT.strafe is False
    assert 'strafe' not in pilot_state(strafing_state())


def test_strafe_offers_a_sideways_course_while_tracking_an_enemy():
    state = pilot_state(strafing_state(), RuleParams(strafe=True))
    strafe = state['strafe']
    assert strafe['side'] in ('left', 'right')
    assert strafe['course'] is not None and 'burn_heading_degrees' in strafe['course']
    # The burn heading is mostly across the line to the enemy (the nose points at it), though it also
    # works off the sideways-free speed the hunter already has.
    assert abs(math.sin(math.radians(strafe['course']['burn_degrees_off_nose']))) > 0.5


def test_strafe_goes_to_the_side_with_more_room():
    # A wall just south of the hunter (south is right of an east-pointing nose): go left.
    wall_south = [[[100.0, 165.0], [200.0, 165.0]]]
    assert pilot_state(strafing_state(walls=wall_south), RuleParams(strafe=True))['strafe']['side'] == 'left'
    wall_north = [[[100.0, 135.0], [200.0, 135.0]]]
    assert pilot_state(strafing_state(walls=wall_north), RuleParams(strafe=True))['strafe']['side'] == 'right'


@pytest.mark.parametrize('why,state', [
    ('not tracking last decision', lambda: strafing_state(tracking=False)),
    ('too fast, so braking comes first', lambda: strafing_state(speed=9.0)),
])
def test_strafe_is_absent_when_its_conditions_do_not_hold(why, state):
    assert pilot_state(state(), RuleParams(strafe=True)).get('strafe') is None, why


def test_strafe_is_absent_when_both_sides_are_blocked():
    walls = [[[100.0, 165.0], [200.0, 165.0]], [[100.0, 135.0], [200.0, 135.0]]]
    assert pilot_state(strafing_state(walls=walls), RuleParams(strafe=True)).get('strafe') is None


def test_strafe_distance_is_a_bounded_parameter():
    assert 'strafe_cells' in BOUNDS
    near = pilot_state(strafing_state(), RuleParams(strafe=True, strafe_cells=0.5))['strafe']
    far = pilot_state(strafing_state(), RuleParams(strafe=True, strafe_cells=2.5))['strafe']
    assert near['course'] != far['course']


def test_strafe_dodges_against_its_sideways_drift():
    # East-pointing nose: south is right. Drifting right (south) -> dodge left, and the reverse.
    drifting_right = strafing_state(speed=0.0)
    drifting_right['self']['velocity'] = [0.0, 0.5]
    assert pilot_state(drifting_right, RuleParams(strafe=True))['strafe']['side'] == 'left'
    drifting_left = strafing_state(speed=0.0)
    drifting_left['self']['velocity'] = [0.0, -0.5]
    assert pilot_state(drifting_left, RuleParams(strafe=True))['strafe']['side'] == 'right'


def test_strafe_drift_rule_still_respects_blocked_sides():
    # Drifting right would send the dodge left, but a wall just north blocks it: no dodge at all.
    state = strafing_state(speed=0.0, walls=[[[100.0, 135.0], [200.0, 135.0]]])
    state['self']['velocity'] = [0.0, 0.5]
    assert pilot_state(state, RuleParams(strafe=True)).get('strafe') is None


def test_strafe_falls_back_to_the_roomier_side_when_barely_drifting():
    wall_south = [[[100.0, 165.0], [200.0, 165.0]]]
    state = strafing_state(speed=0.0, walls=wall_south)
    state['self']['velocity'] = [0.0, 0.05]   # about 3 m/s, under the drift threshold
    assert pilot_state(state, RuleParams(strafe=True))['strafe']['side'] == 'left'


# --- wall-following confidence --------------------------------------------------------

def wall_following_state():
    """A hunter cut off from the player, with a wall beside it and nothing to shoot."""
    raw, _ = raw_state()
    raw['visible_contacts'] = []
    raw['self']['velocity'] = [0.2, 0.0]
    raw['visible_walls'] = [[[100.0, 175.0], [300.0, 175.0]]]
    return raw


def test_wall_follow_cruise_range_allows_much_faster_exploration():
    assert BOUNDS['wall_follow_cruise'][1] >= 3.0


def test_wall_look_ahead_is_a_parameter_with_todays_default():
    assert DEFAULT.wall_lookahead_cells == 0.75
    assert 'wall_lookahead_cells' in BOUNDS


def test_a_longer_look_ahead_puts_the_wall_follow_target_further_along():
    raw = wall_following_state()
    near = pilot_state(raw, RuleParams(wall_lookahead_cells=0.5))['wall_follow']
    far = pilot_state(raw, RuleParams(wall_lookahead_cells=2.0))['wall_follow']
    assert near['course'] != far['course']


def test_a_higher_cruise_lifts_the_wall_follow_speed_limit():
    raw = wall_following_state()
    slow = pilot_state(raw, RuleParams(wall_follow_cruise=0.6))['wall_follow']['course']
    fast = pilot_state(raw, RuleParams(wall_follow_cruise=2.5))['wall_follow']['course']
    assert fast['speed_limit_metres_per_second'] > slow['speed_limit_metres_per_second']


# --- ship thrust --------------------------------------------------------------------

def test_thrust_multiplier_is_a_bounded_parameter_that_matches_the_ship_default():
    from hunter.model import HunterSettings
    assert 'thrust_multiplier' in BOUNDS
    low, high = BOUNDS['thrust_multiplier']
    assert low <= 0.25 <= high and high >= 1.5
    assert HunterSettings().thrust_multiplier == 0.25   # tried 1.0, reverted: docs/experiments/008
    # The lab applies it to the hunter ship; the game uses HunterSettings. They must not drift apart
    # silently, or a lab-only gain would look like a real one.
    assert DEFAULT.thrust_multiplier == HunterSettings().thrust_multiplier
    from hunter.rule_params import RULES
    assert RULES.thrust_multiplier == HunterSettings().thrust_multiplier


# --- the minimum burn scales with the engine ---------------------------------------

def standing_still_with_a_wall(thrust):
    """A stationary hunter beside a wall: wall-follow wants a small speed-up to cruise."""
    ship = HunterRig((150, 170), replace_settings(thrust))
    ship.angle = 180.0
    obs = HunterPerception().observe(ship, maze(), None, [], [], NEUTRAL, 0, 1)
    raw = json.loads(obs.state_json)
    raw['follow_player'] = None
    return raw


def replace_settings(thrust):
    from dataclasses import replace
    from hunter.model import HunterSettings
    return replace(HunterSettings(), thrust_multiplier=thrust)


def cruising_just_short_of_cruise(thrust, shortfall):
    """Heading west along a wall `shortfall` px/frame slower than the wall-follow cruise."""
    raw = standing_still_with_a_wall(thrust)
    cruise = pilot_state(raw)['wall_follow']['course']['speed_after_metres_per_second'] / raw['physics']['fps']
    raw['self']['velocity'] = [-(cruise - shortfall), 0.0]
    return raw


def test_a_sub_two_frame_burn_still_counts_when_the_engine_is_strong():
    # A shortfall of 0.2 px/frame is 5 frames of the old engine and 1.33 of the new one. The old
    # two-frame cutoff would have dropped it, leaving a strong engine unable to make small corrections.
    for thrust, frames in ((0.25, 0.2 / 0.0375), (1.0, 0.2 / 0.15)):
        course = pilot_state(cruising_just_short_of_cruise(thrust, 0.2))['wall_follow']['course']
        assert course['burn_needed'] is True, thrust
        assert course['burn_seconds'] * 60 == pytest.approx(frames, abs=0.35)
    assert 1.0 < 0.2 / 0.15 < 2.0


def test_a_correction_below_one_frame_of_the_strong_engine_is_not_a_burn():
    course = pilot_state(cruising_just_short_of_cruise(1.0, 0.05))['wall_follow']['course']
    assert course['burn_needed'] is False   # the computed length (0.6 frames) is below the 1-frame floor
    assert course['burn_seconds'] * 60 < 1.0


def test_the_weak_engine_keeps_the_two_frame_cutoff_exactly():
    from hunter.pilot_sensors import MIN_BURN_FRAMES, REFERENCE_THRUST_PER_FRAME, min_burn_frames
    assert MIN_BURN_FRAMES == 2 and REFERENCE_THRUST_PER_FRAME == pytest.approx(0.0375)
    assert min_burn_frames(0.0375) == 2
    assert min_burn_frames(0.15) == 1          # floor: one frame is the smallest burn
    assert min_burn_frames(0.075) == 1.0
    assert min_burn_frames(0.01) == pytest.approx(2 * 0.0375 / 0.01)   # weaker engines wait longer


# --- sensor range ----------------------------------------------------------------------

def test_sensor_range_fraction_is_a_bounded_parameter_that_matches_the_hunter_default():
    from hunter.model import HunterSettings
    from hunter.rule_params import RULES
    assert 'sensor_range_fraction' in BOUNDS
    low, high = BOUNDS['sensor_range_fraction']
    assert low < 0.8 < high and high >= 1.0
    # The lab applies it to the hunter; the game uses HunterSettings. They must not drift apart silently.
    assert DEFAULT.sensor_range_fraction == HunterSettings().sensor_range_fraction == 0.8   # 009
    assert RULES.sensor_range_fraction == HunterSettings().sensor_range_fraction


# --- turn rate -------------------------------------------------------------------------

def test_turn_rate_multiplier_is_a_bounded_parameter_that_matches_the_hunter_default():
    from hunter.model import HunterSettings
    from hunter.rule_params import RULES
    assert 'turn_rate_multiplier' in BOUNDS
    low, high = BOUNDS['turn_rate_multiplier']
    assert low < 0.5 < high and high >= 3.0
    assert DEFAULT.turn_rate_multiplier == HunterSettings().turn_rate_multiplier == 0.5
    # The rules pilot's hunter turns faster (010); hunter_settings_for applies it, and a test in
    # tests/test_hunter_settings_for.py keeps the game and the lab in step.
    assert RULES.turn_rate_multiplier == 2.0


# --- hunt before following -----------------------------------------------------------

def following_state(enemies_present):
    """A hunter with a player in plain sight and a clear route to it, and no enemy in sight."""
    raw, _ = raw_state()
    raw['visible_contacts'] = []
    raw['enemies_present'] = enemies_present
    raw['follow_player'] = {'bearing': 0.0, 'waypoint': [400.0, 150.0], 'waypoint_distance': 250.0,
                            'route_distance': 250.0, 'player_visible': True, 'player_distance': 250.0}
    raw['visible_walls'] = [[[100.0, 175.0], [300.0, 175.0]]]
    return raw


def test_hunt_first_is_a_switch_that_defaults_off():
    assert 'hunt_first' in SWITCHES and DEFAULT.hunt_first is False


def test_by_default_the_hunter_follows_the_player_whether_or_not_enemies_remain():
    for present in (True, False):
        state = pilot_state(following_state(present))
        assert state['follow_player'] is not None and state['wall_follow'] is None


def test_with_hunt_first_it_follows_only_once_no_enemy_remains():
    params = RuleParams(hunt_first=True)
    hunting = pilot_state(following_state(True), params)
    assert hunting['follow_player'] is None and hunting['wall_follow'] is not None
    following = pilot_state(following_state(False), params)
    assert following['follow_player'] is not None and following['wall_follow'] is None


def test_hunt_first_without_the_enemies_present_key_still_follows():
    raw = following_state(True)
    del raw['enemies_present']
    assert pilot_state(raw, RuleParams(hunt_first=True))['follow_player'] is not None


def test_the_rules_pilot_hunts_before_following_by_default_and_jev_does_not():
    from hunter.rule_params import RULES
    state = following_state(True)
    assert pilot_state(state, RULES)['follow_player'] is None
    assert pilot_state(state, DEFAULT)['follow_player'] is not None   # Jev's instructions describe following
