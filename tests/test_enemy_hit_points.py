"""Squids and flighthouses soak up several shots; babies still pop in one."""
from unittest.mock import Mock

import config
from entities.baby import Baby
from entities.command_recorder import CommandRecorder
from entities.flighthouse_enemy import FlighthouseEnemy
from entities.projectile import Projectile
from entities.replay_enemy_ship import ReplayEnemyShip
from game_handlers.collision_handler import CollisionHandler

POS = (400.0, 300.0)


def shoot(handler, squid, crystals=None):
    projectile = Projectile(POS, 0.0)
    projectile.source = 'player'
    hit = handler.handle_projectile_enemy_collisions(
        projectile, [], [squid], [], [], [], [], [], [], crystals if crystals is not None else []
    )
    return hit


def make_handler():
    return CollisionHandler(Mock(), Mock(), CommandRecorder())


def test_squid_takes_several_hits():
    assert config.REPLAY_ENEMY_HIT_POINTS == 3
    squid = ReplayEnemyShip(POS, CommandRecorder())
    assert squid.hit_points == squid.max_hit_points == config.REPLAY_ENEMY_HIT_POINTS


def test_squid_survives_until_its_last_hit_point():
    handler = make_handler()
    squid = ReplayEnemyShip(POS, CommandRecorder())
    for _ in range(config.REPLAY_ENEMY_HIT_POINTS - 1):
        assert shoot(handler, squid)  # The shot is still used up
        assert squid.active
        assert not squid.is_dying
    assert shoot(handler, squid)
    assert not squid.active
    assert squid.is_dying


def test_kill_is_only_credited_on_the_final_hit(monkeypatch):
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
    handler = make_handler()
    squid = ReplayEnemyShip(POS, CommandRecorder())
    crystals = []
    for _ in range(config.REPLAY_ENEMY_HIT_POINTS - 1):
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
    squid = ReplayEnemyShip(POS, CommandRecorder())
    assert squid.get_damage_fraction() == 0.0
    squid.is_blinking = False
    shoot(handler, squid)
    assert squid.is_blinking
    assert 0.0 < squid.get_damage_fraction() < 1.0
    wounded = squid.get_damage_fraction()
    shoot(handler, squid)
    assert squid.get_damage_fraction() > wounded


def test_baby_among_the_squids_still_dies_in_one_hit():
    # Bosses release their babies into the squid list
    handler = make_handler()
    baby = Baby(POS, CommandRecorder())
    assert baby.hit_points == 1
    shoot(handler, baby)
    assert not baby.active


def test_flighthouse_takes_five_hits():
    assert config.FLIGHTHOUSE_ENEMY_HIT_POINTS == 5
    flighthouse = FlighthouseEnemy(POS)
    assert [flighthouse.take_damage() for _ in range(5)] == [False, False, False, False, True]
