"""Jellies (aggressive enemies) chasing the same target never pile into the same space (half a pixel is a touch)."""
import math
from types import SimpleNamespace
from unittest.mock import Mock

from entities.enemy import Enemy
from entities.ship import Ship
from game_handlers.enemy_updater import EnemyUpdater


def chase(jellies, frames):
    ship = Ship((600.0, 300.0))
    ship.shield_active = True
    maze = SimpleNamespace(walls=[], spatial_grid=None)
    for _ in range(frames):
        EnemyUpdater().update_enemies(jellies, 1.0, (ship.x, ship.y), maze, ship, Mock(), [])
    return jellies


def gap(a, b):
    return math.dist(a.get_pos(), b.get_pos()) - (a.radius + b.radius)


def test_two_jellies_on_the_same_spot_are_pushed_apart():
    a, b = Enemy((300.0, 300.0), 'aggressive', 10), Enemy((300.5, 300.0), 'aggressive', 10)
    chase([a, b], 1)
    assert gap(a, b) >= -0.01


def test_jellies_chasing_one_target_never_overlap():
    jellies = [Enemy((200.0 + 3 * i, 300.0 + 2 * i), 'aggressive', 10) for i in range(5)]
    for _ in range(120):
        chase(jellies, 1)
        assert all(gap(a, b) >= -0.5 for i, a in enumerate(jellies) for b in jellies[i + 1:])


def test_a_crowd_pressed_into_a_corner_never_pushes_one_of_them_into_the_walls():
    # A corner pen: walls along x = 300 and y = 300, the target beyond both, so the crowd packs into the corner
    walls = [((300.0, 0.0), (300.0, 300.0)), ((0.0, 300.0), (300.0, 300.0))]
    ship = Ship((600.0, 600.0))
    ship.shield_active = True
    maze = SimpleNamespace(walls=walls, spatial_grid=None)
    crowd = [Enemy((240.0 + 4 * (i % 4), 240.0 + 5 * (i // 4)), 'aggressive', 10) for i in range(8)]
    for _ in range(240):
        EnemyUpdater().update_enemies(crowd, 1.0, (ship.x, ship.y), maze, ship, Mock(), [])
        assert all(j.x + j.radius <= 300.5 and j.y + j.radius <= 300.5 for j in crowd)
