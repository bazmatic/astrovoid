"""Brains: the traits that decide where a creature goes and when it fires."""
import math
from types import SimpleNamespace

import pytest

import config
from creatures.traits.brains import Chase, Patrol
from creatures.traits.propulsion import Drift
from tests.creature_parts import creature, encounter, target, world


def patroller(angle, pos=(300.0, 300.0), walls=()):
    crab = creature([Patrol(), Drift(speed=1.0)], pos=pos, key='patrol')
    crab.angle = angle
    stand_in = world(ship=target((2000.0, 2000.0)), maze=SimpleNamespace(walls=list(walls), spatial_grid=None))
    return crab, encounter(crab, world_=stand_in)


def test_a_patrolling_creature_turns_around_at_its_distance_and_at_a_wall():
    crab, enc = patroller(0.0)
    enc.step(1.0)
    crab.patrol_max = 40.0
    start_x = crab.x
    headings = []
    for _ in range(200):
        enc.step(1.0)
        headings.append(crab.controls.heading)
    assert 180.0 in headings and 0.0 in headings
    assert max(abs(h - headings[0]) for h in headings) == 180.0
    assert abs(crab.x - start_x) < 60.0                     # it paces, it does not wander off

    wall = ((330.0, 0.0), (330.0, 600.0))
    crab, enc = patroller(0.0, walls=[wall])
    enc.step(1.0)
    crab.patrol_max = 1000.0
    headings = []
    for _ in range(100):
        enc.step(1.0)
        headings.append(crab.controls.heading)
        assert crab.x + crab.radius < 330.0                  # never into the wall
    assert 180.0 in headings                                 # the wall, not the distance, turned it


def test_an_inactive_wall_does_not_turn_a_patroller():
    wall = SimpleNamespace(active=False, get_segment=lambda: ((310.0, 0.0), (310.0, 600.0)))
    crab, enc = patroller(0.0, walls=[wall])
    enc.step(1.0)
    crab.patrol_max = 1000.0
    for _ in range(30):
        enc.step(1.0)
    assert crab.x > 315.0


def test_a_patroller_aims_at_a_target_in_range_only():
    crab, enc = patroller(0.0)
    enc.step(1.0)
    crab.gun_range = 100.0
    aim = (crab.x + 50.0, crab.y)
    enc.world.ship = target(aim)
    enc.step(1.0)
    assert crab.controls.fire and crab.controls.aim == aim
    enc.world.ship = target((crab.x + 500.0, crab.y))
    enc.step(1.0)
    assert not crab.controls.fire


def chaser(pos=(300.0, 300.0), speed=1.0, ship_at=(600.0, 300.0)):
    jelly = creature([Chase(), Drift(speed=speed)], pos=pos, key='aggressive')
    return jelly, encounter(jelly, world_=world(ship=target(ship_at)))


def test_a_chasing_creature_closes_on_its_target():
    jelly, enc = chaser()
    for _ in range(60):
        enc.step(1.0)
    assert jelly.is_alert and not jelly.backing_off
    assert 330.0 < jelly.x < 600.0 and jelly.y == pytest.approx(300.0)


def test_a_stuck_chaser_backs_off_then_chases_again(monkeypatch):
    monkeypatch.setattr(config, 'ENEMY_SHIFT_DURATION_MIN', 5)
    monkeypatch.setattr(config, 'ENEMY_SHIFT_DURATION_MAX', 5)
    jelly, enc = chaser(speed=0.0)                            # it cannot move, so it is stuck at once
    backing = []
    for _ in range(12):
        enc.step(1.0)
        backing.append(jelly.backing_off)
        if jelly.backing_off:
            away = (jelly.controls.heading - 180.0 + 180) % 360 - 180   # the target is due east (0 degrees)
            assert abs(away) <= 45.0
    assert backing[0] is False                                # nothing to compare with on its first frame
    assert backing[1:6] == [True] * 5                         # five frames of backing off
    assert backing[6] is False                                # then it chases again


def test_crowd_traits_keep_jellies_from_overlapping():
    from creatures.traits.crowd import KeepsApart
    jellies = [creature([Chase(), Drift(speed=1.0), KeepsApart()], pos=(300.0 + 0.5 * i, 300.0), key='aggressive')
               for i in range(3)]
    enc = encounter(*jellies, world_=world(ship=target((600.0, 300.0))))
    enc.step(1.0)
    gaps = [math.dist(a.get_pos(), b.get_pos()) - a.radius - b.radius
            for i, a in enumerate(jellies) for b in jellies[i + 1:]]
    assert min(gaps) >= -0.01
