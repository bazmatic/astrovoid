from unittest.mock import Mock
from entities.projectile import Projectile
from entities.enemy import Enemy
from game_handlers.collision_handler import CollisionHandler


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
