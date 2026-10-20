"""The Squiddler Boss and the Mother as Creatures: big squids that split into Squidlets when they die."""
from unittest.mock import Mock

import pytest

import config
import creatures
import enemy_kinds
from entities.command_recorder import CommandRecorder
from entities.projectile import Projectile
from entities.squid import Squid
from game_handlers.collision_handler import CollisionHandler
from tests.creature_parts import encounter, target, world

POS = (400.0, 300.0)
CHILDREN = dict(enemy_kinds.kind('split_boss').traits)['splitsOnDeath']['count']


@pytest.mark.parametrize('kind, radius, hit_points', [('split_boss', 30, 8), ('mother_boss', 45, 20)])
def test_the_catalogue_builds_both_bosses(kind, radius, hit_points):
    boss = creatures.build(kind, POS, 1, CommandRecorder())
    encounter(boss, world_=world(ship=target((POS[0] + 2000.0, POS[1])))).step(1.0)
    assert isinstance(boss.body, Squid) and boss.radius == radius and boss.max_hit_points == hit_points


@pytest.mark.parametrize('kind', ['split_boss', 'mother_boss'])
def test_a_boss_killed_by_the_hunter_still_splits(kind):
    scoring = Mock()
    handler = CollisionHandler(Mock(), scoring, CommandRecorder())
    boss = creatures.build(kind, POS, 1, CommandRecorder())
    stand_in = world(collision_handler=handler, scoring=scoring, sound_manager=handler.sound_manager,
                     command_recorder=handler.command_recorder, maze=None)
    enc = encounter(boss, world_=stand_in)
    enc.step(1.0)
    boss.hit_points = 1
    drop = Mock(wraps=handler.drop_pickup)
    handler.drop_pickup = drop
    assert enc.shoot(Projectile(POS, 0, source='hunter'))
    assert not boss.active
    children = [e for e in enc.roster.all() if e.type == 'baby']
    assert len(children) == CHILDREN
    scoring.record_enemy_destroyed.assert_not_called()
    drop.assert_called_once()


def test_the_mothers_shots_glow_and_fly_faster():
    shots = {}
    for kind in ('replay', 'mother_boss'):
        squid = creatures.build(kind, POS, 1, CommandRecorder())
        squid.angle = 0.0
        stand_in = world(ship=target((POS[0] + 200.0, POS[1])))
        encounter(squid, world_=stand_in).step(1.0)
        [shots[kind]] = [p for p in stand_in.projectiles if p.is_enemy]
    assert shots['mother_boss'].vx == pytest.approx(shots['replay'].vx * 1.6)
    assert shots['mother_boss'].glow_color == (255, 160, 100)
