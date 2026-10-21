"""Traits that put new enemies on the level: a boss splitting into Squidlets, a Mother laying eggs."""
import math
from types import SimpleNamespace

import pytest

import creatures
from creatures.traits.spawning import LaysEggs, SplitsOnDeath
from creatures.creature import Creature
from entities.command_recorder import CommandRecorder
from tests.creature_parts import creature, encounter, target, world

POS = (400.0, 300.0)


def open_maze(open_everywhere=True, spot=(10.0, 10.0)):
    return SimpleNamespace(walls=[], spatial_grid=None, is_open=lambda pos, radius: open_everywhere,
                           open_spot_near=lambda origin, radius, max_offset, *a, **k: spot)


def children_of(enc, parent):
    return [e for e in enc.roster.all() if e is not parent]


def test_splitting_puts_its_children_on_the_roster_moving_apart():
    boss = creature([SplitsOnDeath(into='baby', count=6, spread=80, speed=2.0)], pos=POS, key='split_boss')
    boss.vx, boss.vy = 0.0, 3.0                                   # travelling straight down (90 degrees)
    enc = encounter(boss, world_=world(maze=open_maze(), command_recorder=CommandRecorder()))
    enc.kill(boss)
    children = children_of(enc, boss)
    assert len(children) == 6 and all(isinstance(c, Creature) and c.type == 'baby' for c in children)
    assert all(40.0 - 1e-9 <= math.dist(c.get_pos(), POS) <= 80.0 + 1e-9 for c in children)
    headings = [math.degrees(math.atan2(c.vy, c.vx)) for c in children]
    assert headings[0] == pytest.approx(45.0) and all(h == pytest.approx(135.0) for h in headings[1:])
    assert all(math.hypot(c.vx, c.vy) == pytest.approx(2.0) for c in children)


def test_a_child_with_no_room_moves_to_an_open_spot():
    boss = creature([SplitsOnDeath(into='baby', count=3, spread=80, speed=2.0)], pos=POS, key='split_boss')
    enc = encounter(boss, world_=world(maze=open_maze(open_everywhere=False, spot=(11.0, 22.0)),
                                       command_recorder=CommandRecorder()))
    enc.kill(boss)
    assert [c.get_pos() for c in children_of(enc, boss)] == [(11.0, 22.0)] * 3


def test_an_unknown_child_kind_is_rejected():
    with pytest.raises(ValueError):
        SplitsOnDeath.from_params({'into': 'nosuch', 'count': 2, 'spread': 80, 'speed': 2.0})


def test_a_mother_lays_on_her_first_frame_and_then_every_interval():
    mother = creature([LaysEggs(interval=180)], pos=POS, key='mother_boss')
    enc = encounter(mother, world_=world(maze=open_maze(), command_recorder=CommandRecorder()))
    laid_on = []
    for frame in range(1, 201):
        before = len(enc.roster.all())
        enc.step(1.0)
        if len(enc.roster.all()) > before:
            laid_on.append(frame)
    assert laid_on == [1, 181]
    assert all(isinstance(e, Creature) and e.type == 'egg' for e in children_of(enc, mother))


def test_a_dead_mother_lays_no_more():
    mother = creature([LaysEggs(interval=10)], pos=POS, key='mother_boss')
    enc = encounter(mother, world_=world(maze=open_maze(), command_recorder=CommandRecorder()))
    enc.step(1.0)
    enc.kill(mother)
    for _ in range(50):
        enc.step(1.0)
    assert len(children_of(enc, mother)) == 1
