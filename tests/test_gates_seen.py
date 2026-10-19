"""Everything that sees walls sees gates too: a plank blocks sight and the senses' rays."""
from types import SimpleNamespace

import numpy as np

from entities.anemone import Anemone
from entities.enemy import Enemy
from entities.flighthouse_enemy import FlighthouseEnemy
from entities.hunter_ship import HunterShip
from hunter.fire_control import find_firing_solution
from hunter.model import NEUTRAL, HunterSettings
from hunter.perception import HunterPerception
from hunter.senses import RAYS, Senses, _INDEX
from maze.wall_segment import WallSegment

PLANK = WallSegment((300, 400), (300, 600), hit_points=1, destructible=False)


class Grid:
    def __init__(self, walls=()):
        self.walls = list(walls)

    def get_nearby_walls(self, pos, reach):
        return self.walls

    def get_walls_along_path(self, a, b, margin):
        return self.walls


def world(gates):
    return SimpleNamespace(cell_size_x=100, cell_size_y=100, offset_x=0, offset_y=0, grid_width=10,
                           grid_height=10, walls=[], spatial_grid=Grid(), gate_segments=list(gates))


def hunter():
    ship = HunterShip((100, 500))
    ship.angle = 0.0
    return ship


def target():
    return Enemy((500, 500), 'static')


def test_the_hunter_cannot_see_through_a_gate():
    def contacts(gates):
        state = HunterPerception(HunterSettings()).observe(
            hunter(), world(gates), None, [target()], [], NEUTRAL, 0.0, 1).state_json
        return state
    import json
    assert json.loads(contacts([]))['visible_contacts']
    assert not json.loads(contacts([PLANK]))['visible_contacts']


def test_the_neural_senses_feel_a_gate():
    def ahead(gates):
        out = Senses(HunterSettings()).observe(hunter(), world(gates), [], [], [], None, (1, False, False), 0.0)
        return out[_INDEX['ray_0']:_INDEX['ray_0'] + RAYS]
    assert ahead([PLANK]).min() < ahead([]).min()


def test_fire_control_will_not_shoot_through_a_gate():
    assert find_firing_solution(hunter(), [target()], world([]), HunterSettings()) is not None
    assert find_firing_solution(hunter(), [target()], world([PLANK]), HunterSettings()) is None


def test_an_anemone_cannot_see_through_a_gate():
    anemone = Anemone((100, 500))
    assert not anemone._wall_between((500, 500), world([]))
    assert anemone._wall_between((500, 500), world([PLANK]))


def test_a_flighthouse_cannot_see_through_a_gate():
    def sees(gates):
        lighthouse = FlighthouseEnemy((100, 500))
        lighthouse.angle = 0.0
        return lighthouse._player_in_fov((500, 500), [], Grid(), gates)
    assert sees([])
    assert not sees([PLANK])
