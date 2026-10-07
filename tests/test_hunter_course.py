"""Course correction: the turn and burn that point the hunter's motion at a target."""
import math
import random

import pytest
import config
from entities.hunter_ship import HunterShip
from hunter.course import course_correction
from hunter.model import NEUTRAL, PilotAction

THRUST = PilotAction(0, True, False)
LIMIT = 3.0  # pixels per frame


def bearing(origin, point):
    return math.degrees(math.atan2(point[1] - origin[1], point[0] - origin[0]))


def off(a, b):
    return (a - b + 180) % 360 - 180


def solve(ship, target, limit=LIMIT, **kwargs):
    """The correction for the real ship, drag included unless friction is overridden."""
    kwargs.setdefault('friction', config.SHIP_FRICTION)
    return course_correction(
        ship.get_pos(), (ship.vx, ship.vy), ship.angle, target,
        thrust=ship.thrust_force, speed_limit=limit,
        rotation_per_frame=ship.current_rotation_speed, **kwargs)


NO_DRAG = {'friction': 1.0}  # Makes the arithmetic exact for the worked examples below


def fly(ship, correction, target=None, target_velocity=(0.0, 0.0)):
    """Swing to the burn heading at the turn rate, burn, and report what happened."""
    target = list(target) if target else None
    fastest = math.hypot(ship.vx, ship.vy)

    def frame(action):
        nonlocal fastest
        ship.step(1, action)
        fastest = max(fastest, math.hypot(ship.vx, ship.vy))
        if target:
            target[0] += target_velocity[0]
            target[1] += target_velocity[1]

    while abs(off(correction.heading_degrees, ship.angle)) > 1e-9:
        swing = off(correction.heading_degrees, ship.angle)
        rate = ship.current_rotation_speed
        ship.angle = (ship.angle + max(-rate, min(rate, swing))) % 360
        frame(NEUTRAL)
    for _ in range(round(correction.burn_frames)):
        frame(THRUST)
    return fastest, target


@pytest.fixture(autouse=True)
def open_space(monkeypatch):
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 100000)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 100000)


def ship_at(velocity=(0.0, 0.0), heading=0.0):
    ship = HunterShip((50000, 50000))
    ship.vx, ship.vy = velocity
    ship.angle = heading
    return ship


def test_stationary_ship_burns_straight_at_the_target():
    ship = ship_at(heading=200.0)
    target = (50300, 50400)
    correction = solve(ship, target, **NO_DRAG)
    assert correction.heading_degrees == pytest.approx(bearing(ship.get_pos(), target) % 360, abs=0.5)
    assert correction.final_speed == pytest.approx(LIMIT / 2)
    assert correction.burn_frames == pytest.approx(LIMIT / 2 / ship.thrust_force)


def test_already_on_course_needs_no_burn():
    ship = ship_at(velocity=(2.0, 0.0), heading=90.0)
    correction = solve(ship, (50500, 50000))
    assert correction.burn_frames == pytest.approx(0.0, abs=1e-6)
    assert correction.heading_degrees == 90.0
    assert correction.final_speed == pytest.approx(2.0)


def test_sideways_drift_is_cancelled_not_overpowered():
    """Moving across the line to the target: burn against the drift, keeping the useful speed."""
    ship = ship_at(velocity=(2.0, 1.5))
    correction = solve(ship, (55000, 50000), **NO_DRAG)
    assert correction.heading_degrees == pytest.approx(270.0, abs=3.0)
    assert correction.final_speed == pytest.approx(2.0, abs=0.05)


def test_moving_away_turns_the_motion_around():
    ship = ship_at(velocity=(-2.0, 0.0))
    correction = solve(ship, (50600, 50000))
    assert correction.heading_degrees == pytest.approx(0.0, abs=0.5)
    assert correction.final_speed == pytest.approx(LIMIT / 2)


def test_too_fast_toward_the_target_sheds_speed_to_the_limit():
    ship = ship_at(velocity=(5.0, 0.0))
    correction = solve(ship, (59000, 50000), **NO_DRAG)
    assert correction.heading_degrees == pytest.approx(180.0, abs=0.5)
    assert correction.final_speed == pytest.approx(LIMIT)
    assert correction.burn_frames == pytest.approx(2.0 / ship.thrust_force)


def test_drag_does_some_of_the_braking():
    """Drag bleeds speed through the turn, so shedding it takes a shorter burn."""
    ship = ship_at(velocity=(5.0, 0.0))
    with_drag = solve(ship, (59000, 50000))
    without = solve(ship, (59000, 50000), **NO_DRAG)
    assert with_drag.burn_frames < without.burn_frames * 0.8
    assert with_drag.final_speed == pytest.approx(LIMIT)


def test_approach_speed_can_be_chosen():
    ship = ship_at()
    assert solve(ship, (50400, 50000), approach_speed=1.0).final_speed == pytest.approx(1.0)
    assert solve(ship, (50400, 50000), approach_speed=99.0).final_speed == pytest.approx(LIMIT)


def test_reports_the_swing_and_the_total_time():
    ship = ship_at(heading=0.0)
    correction = solve(ship, (50000, 50400))
    assert correction.turn_frames == pytest.approx(90.0 / ship.current_rotation_speed, abs=0.5)
    assert correction.degrees_off_nose == pytest.approx(90.0, abs=0.5)
    assert correction.total_frames == pytest.approx(correction.turn_frames + correction.burn_frames)


def test_no_answer_without_an_engine_or_a_speed_to_aim_for():
    ship = ship_at()
    args = (ship.get_pos(), (0.0, 0.0), 0.0, (50300, 50000))
    assert course_correction(*args, thrust=0.0, speed_limit=LIMIT, rotation_per_frame=2.5) is None
    assert course_correction(*args, thrust=0.04, speed_limit=0.0, rotation_per_frame=2.5) is None


def test_target_underfoot_needs_nothing():
    ship = ship_at(velocity=(1.0, 0.0))
    correction = solve(ship, ship.get_pos())
    assert correction.burn_frames == 0.0


@pytest.mark.parametrize('seed', range(40))
def test_flying_the_correction_points_the_motion_at_the_target(seed):
    """Fly it on the real ship: the motion ends up aimed at the target, within the limit."""
    rng = random.Random(seed)
    speed, course = rng.uniform(0.0, 4.5), rng.uniform(0, 2 * math.pi)
    ship = ship_at((math.cos(course) * speed, math.sin(course) * speed), rng.uniform(0, 360))
    away, direction = rng.uniform(600, 3000), rng.uniform(0, 2 * math.pi)
    target = (ship.x + math.cos(direction) * away, ship.y + math.sin(direction) * away)
    limit = rng.uniform(1.0, 4.0)

    correction = solve(ship, target, limit)
    fastest, _ = fly(ship, correction)

    final_speed = math.hypot(ship.vx, ship.vy)
    travel = math.degrees(math.atan2(ship.vy, ship.vx))
    assert abs(off(travel, bearing(ship.get_pos(), target))) < 2.0
    assert final_speed <= limit + 0.05
    assert final_speed == pytest.approx(correction.final_speed, abs=0.08)
    # The burn never pushes the speed above where it started or the limit, whichever is higher.
    assert fastest <= max(speed, limit) + 0.05


@pytest.mark.parametrize('seed', range(15))
def test_moving_target_is_met_where_it_will_be(seed):
    rng = random.Random(100 + seed)
    ship = ship_at((rng.uniform(-2, 2), rng.uniform(-2, 2)), rng.uniform(0, 360))
    target = (ship.x + rng.choice((-1, 1)) * rng.uniform(900, 2000), ship.y + rng.uniform(-800, 800))
    target_velocity = (rng.uniform(-1, 1), rng.uniform(-1, 1))

    correction = solve(ship, target, target_velocity=target_velocity)
    _, target_now = fly(ship, correction, target, target_velocity)

    # Aimed at the target's present position plus the relative closing geometry:
    # the motion relative to the target must point at it.
    relative_travel = math.degrees(math.atan2(ship.vy - target_velocity[1], ship.vx - target_velocity[0]))
    assert abs(off(relative_travel, bearing(ship.get_pos(), target_now))) < 2.5
    assert math.hypot(ship.vx, ship.vy) <= LIMIT + 0.05


# --- what the pilot is shown ---

def follow_reading(ship, player_pos, action=NEUTRAL):
    import json
    from entities.ship import Ship
    from hunter.perception import HunterPerception
    from hunter.pilot_sensors import pilot_state
    from tests.test_hunter_perception import maze
    observation = HunterPerception().observe(ship, maze(), Ship(player_pos), [], [], action, 0, 1)
    return pilot_state(json.loads(observation.state_json))


def near_ship(velocity=(0.0, 0.0), heading=0.0):
    ship = HunterShip((150, 500))
    ship.vx, ship.vy = velocity
    ship.angle = heading
    return ship


def test_pilot_is_shown_the_course_to_the_waypoint():
    course = follow_reading(near_ship(heading=90.0), (450, 500))['follow_player']['course']
    assert course['burn_needed']
    assert course['burn_degrees_off_nose'] == pytest.approx(-90.0, abs=1.0)
    assert course['burn_seconds'] > 0.2
    assert 0 < course['speed_after_metres_per_second'] <= course['speed_limit_metres_per_second']


def test_course_reading_cancels_sideways_drift():
    """Drifting down while the player is to the right: burn up-and-forward, not at the player."""
    state = follow_reading(near_ship(velocity=(0.5, 1.5)), (450, 500))
    course = state['follow_player']['course']
    assert state['follow_player']['degrees_off_nose'] == pytest.approx(0.0, abs=1.0)
    assert course['burn_needed']
    assert -100 < course['burn_degrees_off_nose'] < -45


def test_course_reading_allows_for_held_steering():
    from hunter.model import ACTIONS
    ship = near_ship(heading=90.0)
    held = follow_reading(ship, (450, 500), ACTIONS['left_coast_hold'])
    course = held['follow_player']['course']
    swing = held['turning']['degrees_per_decision']
    assert course['burn_degrees_off_nose_at_next_decision'] == pytest.approx(
        course['burn_degrees_off_nose'] + swing, abs=0.2)


def test_course_speed_limit_respects_the_wall_beyond_the_waypoint():
    """With a wall close behind the player the ship must arrive slower than in the open."""
    import json
    from entities.ship import Ship
    from hunter.perception import HunterPerception
    from hunter.pilot_sensors import pilot_state
    from maze.wall_segment import WallSegment
    from tests.test_hunter_perception import maze

    def limit(walls):
        world = maze()
        world.walls = walls
        observation = HunterPerception().observe(near_ship(), world, Ship((350, 500)), [], [], NEUTRAL, 0, 1)
        return pilot_state(json.loads(observation.state_json))['follow_player']['course']['speed_limit_metres_per_second']

    assert limit([WallSegment((400, 0), (400, 1000), 3)]) < limit([])


def test_no_burn_needed_when_already_on_course():
    limit = follow_reading(near_ship(), (450, 500))['follow_player']['course']['speed_limit_metres_per_second']
    # Heading straight for the player at a speed between the approach speed and the limit
    state = follow_reading(near_ship(velocity=(limit * 0.75 / config.FPS, 0.0)), (450, 500))
    course = state['follow_player']['course']
    assert not course['burn_needed']
    assert course['burn_seconds'] < 0.15


def test_no_course_once_alongside_the_player():
    assert follow_reading(near_ship(), (200, 500))['follow_player']['course'] is None


def test_pilot_rules_mention_the_course():
    from hunter.jev_pilot import PILOT_QUESTIONS
    for question in ('turn', 'thrust'):
        text = PILOT_QUESTIONS[question]['instructions'] + ' '.join(PILOT_QUESTIONS[question]['criteria'].values())
        assert 'follow_player.course' in text
        assert 'burn_needed' in text
