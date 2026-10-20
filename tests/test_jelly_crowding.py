"""Jellies chasing the same target never pile into the same space (half a pixel is a touch)."""
import math

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
