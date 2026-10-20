"""Jellies chasing the same target never pile into the same space (half a pixel is a touch)."""
import math
from types import SimpleNamespace

import creatures
from entities.ship import Ship
from tests.creature_parts import encounter, world


def chase(jellies, frames):
    ship = Ship((600.0, 300.0))
    ship.shield_active = True
    enc = encounter(*jellies, world_=world(ship=ship))
    for _ in range(frames):
        enc.step(1.0)
    return jellies


def gap(a, b):
    return math.dist(a.get_pos(), b.get_pos()) - (a.radius + b.radius)


def test_jellies_on_one_spot_end_up_only_touching():
    a, b = creatures.build('aggressive', (300.0, 300.0), 10), creatures.build('aggressive', (300.5, 300.0), 10)
    chase([a, b], 1)
    assert gap(a, b) >= -0.01


def test_jellies_chasing_one_target_never_overlap():
    jellies = [creatures.build('aggressive', (200.0 + 3 * i, 300.0 + 2 * i), 10) for i in range(5)]
    ship = Ship((600.0, 300.0))
    ship.shield_active = True
    enc = encounter(*jellies, world_=world(ship=ship))
    for _ in range(120):
        enc.step(1.0)
        assert all(gap(a, b) >= -0.5 for i, a in enumerate(jellies) for b in jellies[i + 1:])


def test_a_crowd_pressed_into_a_corner_never_pushes_one_of_them_into_the_walls():
    # A corner pen: walls along x = 300 and y = 300, the target beyond both, so the crowd packs into the corner
    walls = [((300.0, 0.0), (300.0, 300.0)), ((0.0, 300.0), (300.0, 300.0))]
    ship = Ship((600.0, 600.0))
    ship.shield_active = True
    crowd = [creatures.build('aggressive', (240.0 + 4 * (i % 4), 240.0 + 5 * (i // 4)), 10) for i in range(8)]
    enc = encounter(*crowd, world_=world(ship=ship, maze=SimpleNamespace(walls=walls, spatial_grid=None)))
    for _ in range(240):
        enc.step(1.0)
        assert all(j.x + j.radius <= 300.5 and j.y + j.radius <= 300.5 for j in crowd)
