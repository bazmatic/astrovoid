"""The traits that decide how a creature is hurt, pushed, bounced and rewarded for."""
from unittest.mock import Mock

import config
from creatures.traits.brains import Still
from creatures.traits.combat import (BouncesOffWalls, DropsPickup, FlinchesWhenHit, RamsShip, ShovedByShots, TakesHits,
                                     flinch)
from creatures.traits.propulsion import Coasts
from entities.projectile import Projectile
from tests.creature_parts import creature, encounter, world


def shot_at(c, angle=0.0):
    return Projectile(c.get_pos(), angle, source='player')


def test_takes_hits_kills_on_the_last_hit_and_not_before():
    urchin = creature([TakesHits(hitPoints=3)])
    enc = encounter(urchin)
    enc.step(1.0)
    for _ in range(2):
        assert enc.shoot(shot_at(urchin))
        assert urchin.active
    assert urchin.body.events == ['hit', 'hit']
    assert enc.shoot(shot_at(urchin))
    assert not urchin.active


def test_a_shot_before_the_first_frame_finds_the_creature_ready():
    urchin = creature([TakesHits(hitPoints=3)])
    enc = encounter(urchin)
    enc.shoot(shot_at(urchin))
    assert urchin.active and urchin.hit_points == 2


def test_a_shove_moves_a_still_creature_and_friction_stops_it():
    urchin = creature([Still(), Coasts(), ShovedByShots(), TakesHits(hitPoints=10)])
    enc = encounter(urchin)
    enc.step(1.0)
    start = urchin.get_pos()
    enc.shoot(shot_at(urchin, angle=0.0))
    assert urchin.vx > 0 and urchin.vy == 0
    for _ in range(600):
        enc.step(1.0)
    assert urchin.x > start[0] + 5
    assert (urchin.vx, urchin.vy) == (0.0, 0.0)
    resting = urchin.get_pos()
    enc.step(1.0)
    assert urchin.get_pos() == resting


def test_bounces_only_while_moving():
    wall = ((90.0, 0.0), (90.0, 400.0))             # just left of the creature, inside its radius
    walls = world(maze=Mock(walls=[wall], spatial_grid=None))
    still = creature([Coasts(), BouncesOffWalls()], pos=(95.0, 100.0))
    encounter(still, world_=walls).step(1.0)
    assert still.get_pos() == (95.0, 100.0)
    assert 'hit_wall' not in still.body.events

    moving = creature([Coasts(), BouncesOffWalls()], pos=(95.0, 100.0))
    moving.vx = -2.0
    encounter(moving, world_=walls).step(1.0)
    assert moving.vx > 0
    assert moving.x > 95.0
    assert 'hit_wall' in moving.body.events


def test_ramming_costs_the_player_only_without_a_shield():
    for shield, cost in ((False, 1), (True, 0)):
        ship = Mock(active=True, x=100.0, y=100.0, observer=False)
        ship.get_pos.return_value = (100.0, 100.0)
        ship.is_shield_active.return_value = shield
        ship.check_circle_collision.return_value = True
        stand_in = world(ship=ship)
        rammer = creature([RamsShip()])
        encounter(rammer, world_=stand_in).step(1.0)
        assert stand_in.scoring.record_enemy_collision.call_count == cost
        assert rammer.body.events == (['rammed'] if cost else [])


def test_a_kill_drops_one_pickup_roll():
    stand_in = world()
    crab = creature([TakesHits(hitPoints=1), DropsPickup()])
    enc = encounter(crab, world_=stand_in)
    enc.step(1.0)
    enc.shoot(shot_at(crab))
    enc.shoot(shot_at(crab))
    enc.kill(crab)
    stand_in.collision_handler.drop_pickup.assert_called_once()
    assert stand_in.collision_handler.drop_pickup.call_args.args[0] == crab.get_pos()
    stand_in.collision_handler.record_kill.assert_called_once()
    stand_in.sound_manager.play_enemy_destroy.assert_called_once()


def test_a_flinch_lasts_its_frames_and_a_new_one_never_shortens_it():
    jelly = creature([FlinchesWhenHit(frames=90), TakesHits(hitPoints=9)])
    enc = encounter(jelly)
    enc.step(1.0)
    enc.shoot(shot_at(jelly))
    for _ in range(60):
        enc.step(1.0)
    flinch(jelly, 10, enc)
    assert jelly.flinch_timer == 30
    for _ in range(30):
        enc.step(1.0)
    assert jelly.flinch_timer == 0


def test_it_flinches_only_on_its_events():
    urchin = creature([FlinchesWhenHit(frames=30, on=['hit_wall']), TakesHits(hitPoints=9)])
    enc = encounter(urchin)
    enc.step(1.0)
    enc.shoot(shot_at(urchin))
    assert 'flinch' not in urchin.body.events and urchin.flinch_timer == 0
    urchin.emit('hit_wall', enc)
    assert urchin.body.events[-1] == 'flinch' and urchin.flinch_timer == 30


def test_a_squid_blinks_when_it_flinches():
    import creatures
    from entities.command_recorder import CommandRecorder
    blinks = {}
    for kind in ('replay', 'baby'):
        squid = creatures.build(kind, (100.0, 100.0), 1, CommandRecorder())
        ship = Mock(active=True, x=100.0, y=100.0, observer=False)
        ship.get_pos.return_value = (100.0, 100.0)
        ship.is_shield_active.return_value = False
        ship.check_circle_collision.return_value = True
        encounter(squid, world_=world(ship=ship)).step(1.0)
        blinks[kind] = squid.body.is_blinking
    assert blinks == {'replay': True, 'baby': False}
