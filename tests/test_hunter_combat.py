from unittest.mock import Mock
from entities.projectile import Projectile
import creatures
from tests.creature_parts import encounter, world
from game_handlers.collision_handler import CollisionHandler
from hunter.model import HunterSettings


def test_projectile_source_preserves_existing_calls():
    assert Projectile((100,100), 0).source == 'player'
    assert Projectile((100,100), 0, is_enemy=True).source == 'enemy'
    assert not Projectile((100,100), 0, source='hunter').is_enemy


def test_hunter_kill_does_not_award_player_points():
    scoring = Mock()
    handler = CollisionHandler(Mock(), scoring, Mock())
    for source in ('hunter', 'player'):
        enemy = creatures.build('patrol', (200,200), 1)
        bullet = Projectile((200,200), 0, source=source)
        assert encounter(enemy, world_=world(collision_handler=handler, scoring=scoring)).shoot(bullet)
        assert not enemy.active
    assert scoring.record_enemy_destroyed.call_count == 1


def test_hostile_bullets_consumed_even_during_immunity_and_no_friendly_fire():
    from tests.hunter_fixture import HunterRig
    scoring = Mock()
    handler = CollisionHandler(Mock(),scoring,Mock())
    hunter = HunterRig((200,200), HunterSettings(indestructible=False))
    for source in ('player','hunter'):
        assert not handler.handle_projectile_hunter_collision(Projectile((200,200),0,source=source),hunter)
    for _ in range(2):
        bullet = Projectile((hunter.x,hunter.y),0,is_enemy=True)
        assert handler.handle_projectile_hunter_collision(bullet,hunter)
        assert not bullet.active
    assert hunter.health == 2
    assert not scoring.mock_calls


def test_hunter_boss_kill_still_spawns_children():
    import enemy_kinds
    from entities.command_recorder import CommandRecorder
    boss = creatures.build('split_boss', (200, 200), 1, CommandRecorder())
    scoring = Mock()
    handler = CollisionHandler(Mock(), scoring, CommandRecorder())
    enc = encounter(boss, world_=world(collision_handler=handler, scoring=scoring,
                                       command_recorder=handler.command_recorder, maze=None))
    enc.step(1.0)
    boss.hit_points = 1
    assert enc.shoot(Projectile((200, 200), 0, source='hunter'))
    assert not boss.active
    babies = [e for e in enc.roster.all() if e.type == 'baby']
    assert len(babies) == dict(enemy_kinds.kind('split_boss').traits)['splitsOnDeath']['count']
    scoring.record_enemy_destroyed.assert_not_called()


def test_friendly_contact_bounces_without_damage_and_hostile_contact_hurts():
    from tests.hunter_fixture import HunterRig
    from entities.ship import Ship
    hunter = HunterRig((300,300), HunterSettings(indestructible=False))
    player = Ship((301,300))
    handler = CollisionHandler(Mock(),Mock(),Mock())
    handler.handle_hunter_contacts(hunter,player,[])
    assert hunter.health == 3
    enemy = creatures.build('patrol', (hunter.x,hunter.y),1)
    handler.handle_hunter_contacts(hunter,None,[enemy])
    assert hunter.health == 2
