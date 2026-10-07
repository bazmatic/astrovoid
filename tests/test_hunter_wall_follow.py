"""Wall following: when cut off, the hunter keeps a wall on its left and moves along it."""
import json
import math

import pytest
import config
from entities.hunter_ship import HunterShip
from entities.ship import Ship
from hunter.course import course_correction
from hunter.jev_pilot import PILOT_QUESTIONS
from hunter.model import NEUTRAL, PilotAction
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.wall_follow import wall_follow_target
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze

CELL, RADIUS = 60.0, 8.0


def target(origin, walls, heading=0.0):
    return wall_follow_target(origin, heading, RADIUS, walls, CELL)


def left_of(travel):
    """Unit vector pointing to the left of a direction of travel (screen y grows downward)."""
    length = math.hypot(*travel)
    return (travel[1] / length, -travel[0] / length)


# --- where to head ---

@pytest.mark.parametrize('wall,expected_travel', [
    (((0, 250), (600, 250)), (1, 0)),    # wall above: left of east is north
    (((0, 350), (600, 350)), (-1, 0)),   # wall below: head west
    (((350, 0), (350, 600)), (0, 1)),    # wall to the right: head south
    (((250, 0), (250, 600)), (0, -1)),   # wall to the left: head north
])
def test_travels_parallel_with_the_wall_on_the_left(wall, expected_travel):
    origin = (300.0, 300.0)
    goal = target(origin, [wall])
    travel = (goal.point[0] - origin[0], goal.point[1] - origin[1])
    along = travel[0] * expected_travel[0] + travel[1] * expected_travel[1]
    assert along > CELL * 0.5
    # The wall really is on the left of that direction
    nearest = (min(max(origin[0], wall[0][0]), wall[1][0]), min(max(origin[1], wall[0][1]), wall[1][1]))
    to_wall = (nearest[0] - origin[0], nearest[1] - origin[1])
    left = left_of(expected_travel)
    assert to_wall[0] * left[0] + to_wall[1] * left[1] > 0


def test_holds_a_steady_distance_from_the_wall():
    wall = ((0, 250), (600, 250))
    near, far = target((300.0, 262.0), [wall]), target((300.0, 330.0), [wall])
    assert near.point[1] == pytest.approx(far.point[1])
    standoff = near.point[1] - 250
    assert RADIUS * 2 <= standoff <= CELL / 2
    assert near.wall_distance == pytest.approx(12.0 - RADIUS)
    assert far.wall_distance == pytest.approx(80.0 - RADIUS)


def test_follows_the_nearest_wall():
    walls = [((0, 250), (600, 250)), ((0, 320), (600, 320))]
    goal = target((300.0, 300.0), walls)
    assert goal.point[0] < 300.0  # The lower wall is nearer, so it goes on the left: head west


def test_turns_left_round_the_end_of_a_wall():
    """Past the end of the wall it was following, it curls left to stay with it."""
    wall = ((0, 250), (300, 250))
    # Travelling east below the wall, now beyond its right-hand end
    goal = target((330.0, 270.0), [wall])
    assert goal.point[1] < 270.0  # Heading up, round the end
    assert goal.point[0] > 300.0


def test_turns_right_at_an_inside_corner():
    """A wall ahead becomes the nearer one, so it swings right to put that on the left."""
    walls = [((0, 250), (400, 250)), ((400, 250), (400, 600))]
    # Travelling east under the top wall, nearly at the wall ahead
    goal = target((385.0, 280.0), walls)
    assert goal.point[1] > 280.0 + CELL * 0.4  # Now heading south


def test_with_no_wall_in_sight_it_heads_straight_on_to_find_one():
    goal = target((300.0, 300.0), [], heading=90.0)
    assert goal.wall_distance is None
    assert goal.point[0] == pytest.approx(300.0)
    assert goal.point[1] > 300.0 + CELL * 0.5


# --- flying it ---

def rule_following_pilot(state, raw):
    """The decision a pilot obeying the written rules would make with no enemy in sight."""
    from dataclasses import replace
    from hunter.jev_pilot import navigation_course
    from hunter.model import ACTIONS
    # Too fast for a wall, or flying a course: either way the navigator has the nose.
    course = navigation_course(state)
    action = ACTIONS['course_thrust_hold' if course['burn_needed'] else 'course_coast_hold']
    return replace(action, burn_heading=course['burn_heading_degrees'],
                   burn_frames=course['burn_seconds'] * 60 if course['burn_needed'] else 0.0,
                   burn_reference=raw['self']['thrust_frames'])


def fly_by_the_rules(ship, world, seconds, on_frame, latency_frames=27):
    """Fly the real ship on the real sensor readings, decisions landing one round trip late."""
    perception = HunterPerception()
    action, pending = NEUTRAL, None
    for frame in range(int(seconds * 60)):
        if pending is not None and frame >= pending[0]:
            action, pending = pending[1], None
        if pending is None:
            observation = perception.observe(ship, world, None, [], [], action, frame / 60, 1)
            raw = json.loads(observation.state_json)
            pending = (frame + latency_frames, rule_following_pilot(pilot_state(raw), raw))
        ship.step(1, action)
        on_frame(frame)


def gap_to(walls, ship):
    return min(
        math.hypot(ship.x - min(max(ship.x, min(w.start[0], w.end[0])), max(w.start[0], w.end[0])),
                   ship.y - min(max(ship.y, min(w.start[1], w.end[1])), max(w.start[1], w.end[1])))
        for w in walls)


def test_rule_following_pilot_circles_a_block_keeping_it_on_the_left(monkeypatch):
    """With no player and nothing to shoot, the hunter laps a block of wall without touching it."""
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 4000)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 4000)
    world = maze()
    world.walls = [WallSegment((1000, 1000), (1200, 1000), 3), WallSegment((1200, 1000), (1200, 1200), 3),
                   WallSegment((1200, 1200), (1000, 1200), 3), WallSegment((1000, 1200), (1000, 1000), 3)]
    centre = (1100.0, 1100.0)
    ship = HunterShip((1100.0, 955.0))
    ship.angle = 200.0
    track = {'swept': 0.0, 'last': None, 'gaps': []}

    def on_frame(frame):
        track['gaps'].append(gap_to(world.walls, ship))
        angle = math.atan2(ship.y - centre[1], ship.x - centre[0])
        if track['last'] is not None:
            track['swept'] += (angle - track['last'] + math.pi) % (2 * math.pi) - math.pi
        track['last'] = angle

    fly_by_the_rules(ship, world, 180, on_frame)
    assert min(track['gaps']) > ship.radius, 'hit the wall'
    assert max(track['gaps']) < world.cell_size_x * 1.5, 'wandered off'
    # Above the block the wall is on the left when heading west, so it circles
    # anticlockwise on screen, where angles grow clockwise: at least one full lap.
    assert track['swept'] < -2 * math.pi


def test_rule_following_pilot_explores_a_sealed_room_without_crashing(monkeypatch):
    """Walled in: it works its way round the inside of the room, wall on the left, never touching."""
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 4000)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 4000)
    world = maze()
    world.walls = [WallSegment((1000, 1000), (1300, 1000), 3), WallSegment((1300, 1000), (1300, 1300), 3),
                   WallSegment((1300, 1300), (1000, 1300), 3), WallSegment((1000, 1300), (1000, 1000), 3)]
    centre = (1150.0, 1150.0)
    ship = HunterShip((1150.0, 1150.0))
    ship.angle = 30.0
    track = {'swept': 0.0, 'last': None, 'gaps': []}

    def on_frame(frame):
        track['gaps'].append(gap_to(world.walls, ship))
        angle = math.atan2(ship.y - centre[1], ship.x - centre[0])
        if track['last'] is not None and math.hypot(ship.x - centre[0], ship.y - centre[1]) > 40:
            track['swept'] += (angle - track['last'] + math.pi) % (2 * math.pi) - math.pi
        track['last'] = angle

    fly_by_the_rules(ship, world, 180, on_frame)
    assert min(track['gaps']) > ship.radius, 'hit the wall'
    # Inside a room the wall on the left means going round clockwise on screen.
    assert track['swept'] > 2 * math.pi


# --- what the pilot is shown ---

def reading(ship, world, player):
    observation = HunterPerception().observe(ship, world, player, [], [], NEUTRAL, 0, 1)
    return pilot_state(json.loads(observation.state_json))


def sealed_room():
    """The hunter's cell walled in on all four sides: no route out."""
    world = maze()
    world.walls = [WallSegment((100, 100), (200, 100), 3), WallSegment((200, 100), (200, 200), 3),
                   WallSegment((200, 200), (100, 200), 3), WallSegment((100, 200), (100, 100), 3)]
    return world


def test_wall_follow_is_offered_only_when_cut_off_from_the_player():
    ship, player = HunterShip((150, 150)), Ship((450, 150))
    open_world = reading(ship, maze(), player)
    assert open_world['wall_follow'] is None
    assert open_world['follow_player'] is not None

    cut_off = reading(ship, sealed_room(), player)
    assert cut_off['follow_player'] is None
    assert cut_off['wall_follow'] is not None


def test_wall_follow_is_offered_when_there_is_no_player():
    assert reading(HunterShip((150, 150)), sealed_room(), None)['wall_follow'] is not None


def test_wall_follow_reading_has_a_course_and_a_bearing():
    ship = HunterShip((150, 170))
    ship.angle = 0.0
    follow = reading(ship, sealed_room(), Ship((450, 150)))['wall_follow']
    # Nearest wall is the bottom one, so it goes on the left: head west, behind the nose
    assert abs(follow['degrees_off_nose']) > 120
    assert follow['wall_distance_metres'] == pytest.approx(30 - ship.radius)
    course = follow['course']
    assert course['burn_needed']
    assert 0 < course['speed_after_metres_per_second'] <= course['speed_limit_metres_per_second']
    assert set(course) == set(reading(HunterShip((150, 150)), maze(), Ship((450, 150)))['follow_player']['course'])


def test_pilot_rules_cover_wall_following():
    for question in ('turn', 'thrust'):
        text = PILOT_QUESTIONS[question]['instructions'] + ' '.join(PILOT_QUESTIONS[question]['criteria'].values())
        assert 'wall_follow' in text
        assert 'wall_follow.course' in text
