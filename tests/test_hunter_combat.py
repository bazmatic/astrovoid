from unittest.mock import Mock
from entities.projectile import Projectile
from entities.enemy import Enemy
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
        enemy = Enemy((200,200), 'patrol', 1)
        bullet = Projectile((200,200), 0, source=source)
        assert handler.handle_projectile_enemy_collisions(bullet, [enemy], [], [], [], [], [], [], [], [])
        assert not enemy.active
    assert scoring.record_enemy_destroyed.call_count == 1


def test_hostile_bullets_consumed_even_during_immunity_and_no_friendly_fire():
    from entities.hunter_ship import HunterShip
    scoring = Mock()
    handler = CollisionHandler(Mock(),scoring,Mock())
    hunter = HunterShip((200,200), HunterSettings(indestructible=False))
    for source in ('player','hunter'):
        assert not handler.handle_projectile_hunter_collision(Projectile((200,200),0,source=source),hunter)
    for _ in range(2):
        bullet = Projectile((hunter.x,hunter.y),0,is_enemy=True)
        assert handler.handle_projectile_hunter_collision(bullet,hunter)
        assert not bullet.active
    assert hunter.health == 2
    assert not scoring.mock_calls


def test_hunter_boss_kill_still_spawns_children():
    import config
    from entities.split_boss import SplitBoss
    from entities.command_recorder import CommandRecorder
    boss = SplitBoss((200,200),CommandRecorder())
    boss.hit_points = 1
    babies = []
    scoring = Mock()
    handler = CollisionHandler(Mock(),scoring,CommandRecorder())
    assert handler.handle_projectile_enemy_collisions(
        Projectile((200,200),0,source='hunter'), [], babies, [], [], [boss], [], [], [], [])
    assert not boss.active
    assert len(babies) == config.SPLIT_BOSS_CHILD_COUNT
    scoring.record_enemy_destroyed.assert_not_called()


def test_friendly_contact_bounces_without_damage_and_hostile_contact_hurts():
    from entities.hunter_ship import HunterShip
    from entities.ship import Ship
    hunter = HunterShip((300,300), HunterSettings(indestructible=False))
    player = Ship((301,300))
    handler = CollisionHandler(Mock(),Mock(),Mock())
    handler.handle_hunter_contacts(hunter,player,[])
    assert hunter.health == 3
    enemy = Enemy((hunter.x,hunter.y),'patrol',1)
    handler.handle_hunter_contacts(hunter,None,[enemy])
    assert hunter.health == 2
