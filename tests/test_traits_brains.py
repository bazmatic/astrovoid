"""Brains: the traits that decide where a creature goes and when it fires."""
from types import SimpleNamespace

from creatures.traits.brains import Patrol
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
