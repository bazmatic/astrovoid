"""Braking helper: the wall the hull will really reach, and whether the ship can stop for it."""
import math
import random

import pytest
import config
from entities.hunter_ship import HunterShip
from hunter.braking import braking_solution, hull_travel, stopping_run
from hunter.model import NEUTRAL, PilotAction

RADIUS = 8.0
WALL_ABOVE = ((0.0, 250.0), (2000.0, 250.0))
WALL_AHEAD = ((600.0, 0.0), (600.0, 1000.0))


def solve(position, velocity, walls, heading=0.0, **kwargs):
    kwargs.setdefault('friction', config.SHIP_FRICTION)
    kwargs.setdefault('sensor_range', 240.0)
    return braking_solution(position, velocity, heading, walls, RADIUS,
                            thrust=0.0375, rotation_per_frame=2.5, **kwargs)


# --- what the hull will reach ---

def test_head_on_distance_is_measured_from_the_hull():
    assert hull_travel((300, 300), (1, 0), RADIUS, [WALL_AHEAD], 1000) == pytest.approx(300 - RADIUS)


@pytest.mark.parametrize('gap', [RADIUS + 0.5, 12.0, 35.0, 120.0])
def test_sliding_along_a_wall_is_not_closing_on_it(gap):
    assert hull_travel((300, 250 + gap), (1, 0), RADIUS, [WALL_ABOVE], 1000) is None
    assert hull_travel((300, 250 + gap), (-1, 0), RADIUS, [WALL_ABOVE], 1000) is None


def test_moving_away_from_a_wall_never_reaches_it():
    assert hull_travel((300, 260), (0.2, 1), RADIUS, [WALL_ABOVE], 1000) is None


def test_glancing_approach_uses_the_closing_speed():
    # 30 degrees into the wall from 50 away: the hull has 50 - 8 to close at sin(30)
    direction = (math.cos(math.radians(-30)), math.sin(math.radians(-30)))
    assert hull_travel((300, 300), direction, RADIUS, [WALL_ABOVE], 1000) == pytest.approx((50 - RADIUS) / 0.5)


def test_clipping_the_end_of_a_wall_counts():
    wall = ((600.0, 0.0), (600.0, 295.0))  # Ends just above the path
    assert hull_travel((300, 300), (1, 0), RADIUS, [wall], 1000) == pytest.approx(
        300 - math.sqrt(RADIUS ** 2 - 5 ** 2))
    clear = ((600.0, 0.0), (600.0, 300 - RADIUS - 1))
    assert hull_travel((300, 300), (1, 0), RADIUS, [clear], 1000) is None


def test_wall_end_on_is_found_though_the_centre_line_runs_along_it():
    end_on = ((600.0, 300.0), (900.0, 300.0))
    assert hull_travel((300, 300), (1, 0), RADIUS, [end_on], 1000) == pytest.approx(300 - RADIUS)


def test_nearest_wall_wins_and_the_limit_is_respected():
    near = ((450.0, 0.0), (450.0, 1000.0))
    assert hull_travel((300, 300), (1, 0), RADIUS, [WALL_AHEAD, near], 1000) == pytest.approx(150 - RADIUS)
    assert hull_travel((300, 300), (1, 0), RADIUS, [WALL_AHEAD], 100) is None


def test_stationary_hull_goes_nowhere():
    assert hull_travel((300, 300), (0, 0), RADIUS, [WALL_AHEAD], 1000) is None


# --- must it brake? ---

@pytest.mark.parametrize('speed', [0.5, 2.0, 5.0, 8.0])
def test_fast_parallel_to_a_wall_is_not_too_fast(speed):
    """The same speed that demands braking head-on is fine alongside."""
    walls = [WALL_ABOVE]
    alongside = solve((300, 270), (speed, 0.0), walls, sensor_range=100000.0)
    assert alongside.wall_distance is None
    assert not alongside.must_brake


def test_same_speed_head_on_must_brake():
    assert solve((300, 300), (5.0, 0.0), [WALL_AHEAD]).must_brake


def test_the_slower_the_ship_the_closer_it_may_come():
    """The distance at which braking becomes necessary shrinks with speed."""
    def braking_point(speed):
        for gap in range(400, 8, -1):
            if solve((600 - gap, 300), (speed, 0.0), [WALL_AHEAD], heading=180.0).must_brake:
                return gap
        return 8
    points = [braking_point(speed) for speed in (3.0, 2.0, 1.0, 0.5, 0.2)]
    assert points == sorted(points, reverse=True)
    assert points[0] > points[-1] * 4


def test_harmless_speed_never_brakes():
    crawling = solve((585, 300), (0.2, 0.0), [WALL_AHEAD], harmless_speed=0.25)
    assert not crawling.must_brake
    assert crawling.safe_speed >= 0.25
    assert solve((585, 300), (0.4, 0.0), [WALL_AHEAD], harmless_speed=0.25).must_brake


def test_reaction_time_brings_the_braking_point_forward():
    quick = solve((300, 300), (2.2, 0.0), [WALL_AHEAD], heading=180.0)
    slow_to_react = solve((300, 300), (2.2, 0.0), [WALL_AHEAD], heading=180.0, reaction_frames=60)
    assert slow_to_react.stopping_distance > quick.stopping_distance
    assert slow_to_react.safe_speed < quick.safe_speed


def test_having_to_turn_round_costs_distance():
    nose_first = solve((300, 300), (2.0, 0.0), [WALL_AHEAD], heading=0.0)
    tail_first = solve((300, 300), (2.0, 0.0), [WALL_AHEAD], heading=180.0)
    assert nose_first.turn_frames == pytest.approx(72.0)
    assert tail_first.turn_frames == 0.0
    assert nose_first.stopping_distance > tail_first.stopping_distance
    assert nose_first.heading_degrees == tail_first.heading_degrees == 180.0
    assert abs(nose_first.degrees_off_nose) == 180.0 and tail_first.degrees_off_nose == 0.0


def test_at_rest_there_is_nothing_to_do():
    parked = solve((590, 300), (0.0, 0.0), [WALL_AHEAD])
    assert not parked.must_brake and parked.burn_frames == 0.0 and parked.wall_distance is None


def test_with_no_wall_in_sight_the_room_is_the_sensor_range():
    assert not solve((300, 300), (1.0, 0.0), []).must_brake
    assert solve((300, 300), (7.0, 0.0), []).must_brake  # Outrunning what it can see


def test_time_to_impact_allows_for_drag():
    reading = solve((400, 300), (2.0, 0.0), [WALL_AHEAD])
    assert reading.frames_to_impact > (200 - RADIUS) / 2.0
    assert solve((400, 300), (0.01, 0.0), [WALL_AHEAD]).frames_to_impact is None  # Drag stops it first


# --- flying it ---

@pytest.fixture
def open_space(monkeypatch):
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 100000)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 100000)


def test_stopping_run_matches_the_real_ship(open_space):
    ship = HunterShip((50000, 50000))
    ship.vx, ship.angle = 3.0, 180.0
    predicted, burn = stopping_run(3.0, 20, ship.thrust_force, config.SHIP_FRICTION)
    for _ in range(20):
        ship.step(1, NEUTRAL)
    frames = 0
    while ship.vx > 0:
        ship.step(1, PilotAction(0, True, False))
        frames += 1
    assert frames == burn
    assert ship.x - 50000 == pytest.approx(predicted, abs=abs(ship.vx) + 0.01)


@pytest.mark.parametrize('seed', range(25))
def test_braking_when_told_to_always_stops_short_of_the_wall(open_space, seed):
    """Coast until the helper says brake, then fly its burn: the hull never reaches the wall."""
    rng = random.Random(seed)
    reaction = 27  # A decision takes 0.45 s to land
    ship = HunterShip((50000, 50000))
    course = rng.uniform(0, 2 * math.pi)
    speed = rng.uniform(0.6, 5.0)
    ship.vx, ship.vy = math.cos(course) * speed, math.sin(course) * speed
    ship.angle = rng.uniform(0, 360)
    # A wall square across the course: far enough off that the ship starts out safe,
    # near enough that drag alone will not stop it first
    away = min(1500.0, 0.6 * speed * config.SHIP_FRICTION / (1 - config.SHIP_FRICTION))
    centre = (ship.x + math.cos(course) * away, ship.y + math.sin(course) * away)
    across = (-math.sin(course), math.cos(course))
    wall = ((centre[0] - across[0] * 500, centre[1] - across[1] * 500),
            (centre[0] + across[0] * 500, centre[1] + across[1] * 500))

    def reading():
        return braking_solution(ship.get_pos(), (ship.vx, ship.vy), ship.angle, [wall], ship.radius,
                                thrust=ship.thrust_force, rotation_per_frame=ship.current_rotation_speed,
                                sensor_range=3000.0, friction=config.SHIP_FRICTION,
                                # Checked once a frame here, so the call can come a frame late
                                reaction_frames=reaction + 1)

    def gap():
        return abs((ship.x - centre[0]) * math.cos(course) + (ship.y - centre[1]) * math.sin(course)) - ship.radius

    assert not reading().must_brake
    for _ in range(5000):
        if reading().must_brake:
            break
        ship.step(1, NEUTRAL)
    solution = reading()
    assert solution.must_brake
    for _ in range(reaction):  # The decision is still on its way
        ship.step(1, NEUTRAL)
    while abs((solution.heading_degrees - ship.angle + 180) % 360 - 180) > 1e-9:
        swing = (solution.heading_degrees - ship.angle + 180) % 360 - 180
        rate = ship.current_rotation_speed
        ship.angle = (ship.angle + max(-rate, min(rate, swing))) % 360
        ship.step(1, NEUTRAL)
    for _ in range(int(solution.burn_frames)):
        ship.step(1, PilotAction(0, True, False))
    assert gap() > 0.0, 'reached the wall'
    assert math.hypot(ship.vx, ship.vy) < 0.1
    # ... and it did not brake needlessly early: it stops within a few lengths of the wall
    assert gap() < 40.0


# --- what the pilot is shown, and what it does with it ---

def brake_reading(ship, walls):
    import json
    from hunter.perception import HunterPerception
    from hunter.pilot_sensors import pilot_state
    from maze.wall_segment import WallSegment
    from tests.test_hunter_perception import maze
    world = maze()
    world.walls = [WallSegment(a, b, 3) for a, b in walls]
    observation = HunterPerception().observe(ship, world, None, [], [], NEUTRAL, 0, 1)
    return pilot_state(json.loads(observation.state_json))


def moving_ship(position, velocity, heading=0.0):
    ship = HunterShip(position)
    ship.vx, ship.vy = velocity
    ship.angle = heading
    return ship


@pytest.mark.parametrize('gap', [12.0, 25.0, 60.0])
def test_pilot_is_not_told_too_fast_for_a_wall_it_is_flying_alongside(gap):
    wall = ((0.0, 250.0), (2000.0, 250.0))
    alongside = brake_reading(moving_ship((300, 250 + gap), (2.0, 0.0)), [wall])
    assert alongside['motion']['wall_clearance_metres'] is None
    assert alongside['motion']['brake']['speed_state'] != 'too_fast'
    # The same speed straight at it is another matter
    head_on = brake_reading(moving_ship((300, 250 + 60.0), (0.0, -2.0)), [wall])
    assert head_on['motion']['brake']['speed_state'] == 'too_fast'


def test_crawling_up_to_a_wall_is_not_too_fast():
    wall = ((320.0, 0.0), (320.0, 1000.0))
    assert brake_reading(moving_ship((300, 300), (0.2, 0.0)), [wall])['motion']['brake']['speed_state'] != 'too_fast'


def test_too_fast_hands_the_navigator_the_braking_burn():
    from hunter.jev_pilot import navigation_course
    state = brake_reading(moving_ship((300, 300), (3.0, 0.0)), [WALL_AHEAD])
    brake = state['motion']['brake']
    assert brake['speed_state'] == 'too_fast'
    assert brake['burn_heading_degrees'] == pytest.approx(180.0)
    burn = navigation_course(state)
    assert burn['burn_needed']
    assert burn['burn_heading_degrees'] == brake['burn_heading_degrees']
    assert burn['burn_seconds'] == brake['burn_seconds'] > 0.5


def test_pilot_rules_fly_the_braking_burn_with_the_navigator():
    from hunter.jev_pilot import PILOT_QUESTIONS
    turn, thrust = PILOT_QUESTIONS['turn'], PILOT_QUESTIONS['thrust']
    assert 'too_fast' in turn['criteria']['course']
    assert 'alongside a wall is not moving towards it' in turn['instructions']
    assert thrust['criteria']['burn'].startswith('brake.speed_state is too_fast;')
    for steering in ('left', 'none', 'right', 'track'):
        assert 'not too_fast' in turn['criteria'][steering]


@pytest.mark.parametrize('share,heading', [(0.95, 0.0), (0.95, 90.0), (0.8, 200.0), (0.5, 300.0)])
def test_rule_following_pilot_stops_short_of_a_wall_dead_ahead(open_space, share, heading):
    """Flying as fast as the rules allow in the open, the real ship still stops for a wall
    that comes into sensor range dead ahead."""
    from maze.wall_segment import WallSegment
    from tests.test_hunter_perception import maze
    from tests.test_hunter_wall_follow import fly_by_the_rules
    world = maze()
    world.cell_size_x = world.cell_size_y = 60
    probe = moving_ship((50000.0, 50000.0), (1.0, 0.0), heading)
    safe = brake_reading(probe, [])['motion']['brake']['safe_speed_metres_per_second'] / 60
    world.walls = [WallSegment((50600.0, 49000.0), (50600.0, 51000.0), 3)]
    ship = moving_ship((50000.0, 50000.0), (safe * share, 0.0), heading)
    closest = []
    fly_by_the_rules(ship, world, 30, lambda frame: closest.append(50600.0 - ship.x - ship.radius))
    assert min(closest) > 0.0, 'reached the wall'
