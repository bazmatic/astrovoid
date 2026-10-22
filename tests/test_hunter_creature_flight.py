"""A flight owns a Creature's pilot lifetime, never a private moving ship."""
from dataclasses import replace

from creatures.creature import Creature
from hunter.build import PilotSetup, make_hunter
from hunter.flight import NeuralPilot
from hunter.model import HunterSettings
from hunter.neural.policy import random_policy
from tests.creature_parts import pilot_world
from tests.test_hunter_flight import Surroundings
from tests.test_senses import world as maze


def make():
    w = pilot_world()
    w.maze = maze()
    setup = PilotSetup(HunterSettings(), NeuralPilot(random_policy(0), 1), Surroundings(w.maze))
    return make_hunter((400, 400), world=w, setup=setup), w


def test_a_flight_moves_its_creature_once_without_a_craft():
    f, w = make()
    assert isinstance(f.ship, Creature)
    assert not hasattr(f.ship, 'craft')
    f.step(1)
    assert f.ship.flight is f
    assert f.controller.frames == 1


def test_pausing_keeps_position_and_clocks_while_cancelling_the_burst():
    f, _ = make()
    f.ship.burst_remaining = 2
    f.ship.fire_remaining = 0.25
    before = f.ship.get_pos()
    f.pause()
    assert f.ship.get_pos() == before
    assert f.ship.fire_remaining == 0.25
    assert f.ship.burst_remaining == 0


def test_close_is_idempotent_and_a_copy_has_no_live_pilot():
    from copy import deepcopy
    f, _ = make()
    portrait = deepcopy(f.ship)
    assert portrait.flight is portrait.pilot_setup is None
    f.close()
    f.close()
    assert f.ship.flight is None


def test_the_final_frame_listener_keeps_the_decision_when_a_wall_closes_the_pilot():
    from hunter.model import PilotAction
    from maze.wall_segment import WallSegment
    f, w = make()
    c = f.ship
    c.indestructible, c.health, c.wall_energy = False, 1, 100
    c.vx = 4
    wall = WallSegment((c.x + c.radius + 1, c.y - 100), (c.x + c.radius + 1, c.y + 100), 3)
    w.maze.walls.append(wall)
    w.maze.spatial_grid.add_walls([wall])
    f.controller.override = PilotAction(0, False, True)
    seen = []
    f.on_frame(lambda creature, dt, action, volleys: seen.append(action.fire))
    f.step(1)
    assert not c.active and c.flight is None
    assert seen == [True]
