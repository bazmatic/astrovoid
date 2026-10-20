"""Squids and flighthouses soak up several shots; babies still pop in one."""
from unittest.mock import Mock

import config
import creatures
import enemy_kinds
from entities.baby import Baby
from entities.command_recorder import CommandRecorder
from entities.flighthouse_enemy import FlighthouseEnemy
from entities.projectile import Projectile
from game_handlers.collision_handler import CollisionHandler
from tests.creature_parts import encounter, world

POS = (400.0, 300.0)
SQUIDDLER_HIT_POINTS = dict(enemy_kinds.kind('replay').traits)['takesHits']['hitPoints']


def shoot_old(handler, enemy, crystals=None):
    """A player's shot through the hit loops of the enemies that are not Creatures yet."""
    projectile = Projectile(POS, 0.0)
    projectile.source = 'player'
    return handler.handle_projectile_enemy_collisions(
        projectile, [enemy], [], [], [], [], [], [], crystals if crystals is not None else []
    )


def shoot(handler, squid, crystals=None):
    """A player's shot at a Creature, through an Encounter whose world reports to `handler`."""
    projectile = Projectile(POS, 0.0)
    projectile.source = 'player'
    stand_in = world(collision_handler=handler, scoring=handler.scoring, sound_manager=handler.sound_manager,
                     powerup_crystals=crystals if crystals is not None else [])
    return encounter(squid, world_=stand_in).shoot(projectile)


def make_handler():
    return CollisionHandler(Mock(), Mock(), CommandRecorder())


def make_squid():
    return creatures.build('replay', POS, 1, CommandRecorder())


def test_squid_takes_several_hits():
    assert SQUIDDLER_HIT_POINTS == 3
    squid = make_squid()
    encounter(squid).step(1.0)
    assert squid.hit_points == squid.max_hit_points == SQUIDDLER_HIT_POINTS


def test_squid_survives_until_its_last_hit_point():
    handler = make_handler()
    squid = make_squid()
    for _ in range(SQUIDDLER_HIT_POINTS - 1):
        assert shoot(handler, squid)  # The shot is still used up
        assert squid.active
        assert not squid.is_dying
    assert shoot(handler, squid)
    assert not squid.active
    assert squid.is_dying


def test_kill_is_only_credited_on_the_final_hit(monkeypatch):
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
    handler = make_handler()
    squid = make_squid()
    crystals = []
    for _ in range(SQUIDDLER_HIT_POINTS - 1):
        shoot(handler, squid, crystals)
    assert handler.sound_manager.play_enemy_destroy.call_count == 0
    assert handler.scoring.record_enemy_destroyed.call_count == 0
    assert crystals == []
    shoot(handler, squid, crystals)
    assert handler.sound_manager.play_enemy_destroy.call_count == 1
    assert handler.scoring.record_enemy_destroyed.call_count == 1
    assert len(crystals) == 1


def test_wounded_squid_flinches_and_shows_its_damage():
    handler = make_handler()
    squid = make_squid()
    encounter(squid).step(1.0)
    assert squid.body.get_damage_fraction() == 0.0
    squid.body.is_blinking = False
    shoot(handler, squid)
    assert squid.body.is_blinking
    assert 0.0 < squid.body.get_damage_fraction() < 1.0
    wounded = squid.body.get_damage_fraction()
    shoot(handler, squid)
    assert squid.body.get_damage_fraction() > wounded


def test_baby_among_the_squids_still_dies_in_one_hit():
    # Bosses release their babies into the squid list
    handler = make_handler()
    baby = Baby(POS, CommandRecorder())
    assert baby.hit_points == 1
    shoot_old(handler, baby)
    assert not baby.active


def test_flighthouse_takes_five_hits():
    assert config.FLIGHTHOUSE_ENEMY_HIT_POINTS == 5
    flighthouse = FlighthouseEnemy(POS)
    assert [flighthouse.take_damage() for _ in range(5)] == [False, False, False, False, True]
