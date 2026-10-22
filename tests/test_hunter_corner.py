import asyncio
import json
import math
import pytest
from tests.hunter_fixture import HunterRig
from hunter.jev_pilot import JevPilot
from hunter.model import NEUTRAL
from hunter.perception import HunterPerception
from hunter.rules_pilot import RulesClient
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze


def corner_world(cell=43.2):
    """Walls on two sides: one just ahead of the hunter (west) and one just on its left (south)."""
    world = maze()
    world.cell_size_x = world.cell_size_y = cell
    world.walls = [WallSegment((243.0, 600.0), (243.0, 828.0), 3),      # ahead of a west-facing hunter
                   WallSegment((200.0, 828.0), (900.0, 828.0), 3)]      # on its left
    return world


def fly(ship, world, seconds, decide_every=15):
    perception, action, frame = HunterPerception(), NEUTRAL, 0
    pilot = JevPilot(RulesClient())
    gaps, path = [], []
    for frame in range(int(seconds * 60)):
        if frame % decide_every == 0:
            observation = perception.observe(ship, world, None, [], [], action, frame / 60, 1)
            action = asyncio.run(pilot.decide(observation)).action
        ship.step(1, action)
        path.append((ship.x, ship.y))
        gaps.append(min(math.hypot(ship.x - min(max(ship.x, min(w.start[0], w.end[0])), max(w.start[0], w.end[0])),
                                   ship.y - min(max(ship.y, min(w.start[1], w.end[1])), max(w.start[1], w.end[1])))
                        for w in world.walls))
    return path, gaps


def test_a_hunter_jammed_in_an_inside_corner_gets_out_and_follows_the_wall():
    """Facing a wall 14 px ahead with another 8 px on its left, the wall-follow target is straight
    into the wall and the safe speed there is tiny. It must still creep out, not sit forever."""
    ship = HunterRig((265.0, 812.0))
    ship.angle = 187.0
    path, gaps = fly(ship, corner_world(), 20.0)
    travelled = max(math.hypot(x - 265.0, y - 812.0) for x, y in path)
    assert travelled > 150, f'stuck: only moved {travelled:.0f} px in 20 s'
    assert min(gaps) > ship.radius, 'hit a wall'


def test_a_hunter_at_rest_with_room_to_move_is_not_held_by_the_noise_cutoff():
    ship = HunterRig((265.0, 812.0))
    ship.angle = 187.0
    from hunter.pilot_sensors import pilot_state
    obs = HunterPerception().observe(ship, corner_world(), None, [], [], NEUTRAL, 0, 1)
    course = pilot_state(json.loads(obs.state_json))['wall_follow']['course']
    assert course['speed_after_metres_per_second'] > 0
    assert course['burn_needed'] is True
