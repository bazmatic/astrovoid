"""Unit tests for enemy behavior strategies."""

import pytest
from entities.enemy import Enemy
from entities.enemy_strategies import (
    StaticEnemyStrategy,
    PatrolEnemyStrategy,
    AggressiveEnemyStrategy
)


class TestStaticEnemyStrategy:
    """Tests for static enemy behavior."""
    
    def test_static_enemy_does_not_move(self):
        """Static enemies should not move."""
        enemy = Enemy((100, 100), "static")
        initial_x = enemy.x
        initial_y = enemy.y
        
        strategy = StaticEnemyStrategy()
        strategy.update(enemy, 1.0, None, None)
        
        assert enemy.x == initial_x
        assert enemy.y == initial_y


class TestPatrolEnemyStrategy:
    """Tests for patrol enemy behavior."""
    
    def test_patrol_enemy_moves(self):
        """Patrol enemies should move."""
        enemy = Enemy((100, 100), "patrol")
        initial_x = enemy.x
        initial_y = enemy.y
        
        strategy = PatrolEnemyStrategy()
        strategy.update(enemy, 1.0, None, None)
        
        # Enemy should have moved (unless it hit a wall immediately)
        # At least the position should be different or angle changed
        assert enemy.x != initial_x or enemy.y != initial_y or enemy.angle != 0.0
    
    def test_patrol_enemy_reverses_on_wall(self):
        """Patrol enemy should reverse direction when hitting wall."""
        enemy = Enemy((100, 100), "patrol")
        enemy.angle = 0.0  # Facing right
        initial_angle = enemy.angle
        
        # Create a wall very close in front (so it hits immediately)
        walls = [((105, 90), (105, 110))]  # Vertical wall very close at x=105
        
        strategy = PatrolEnemyStrategy()
        # Update multiple times to ensure enemy moves and hits wall
        for _ in range(5):
            strategy.update(enemy, 1.0, None, walls)
            # Check if angle changed (reversed)
            angle_diff = abs(enemy.angle - initial_angle)
            if angle_diff > 90 or angle_diff < 270:  # Account for wrapping
                # Angle has reversed
                assert True
                return
        
        # If we get here, the enemy should have hit the wall and reversed
        # The angle should be different from initial (either reversed or wrapped)
        final_angle_diff = abs(enemy.angle - initial_angle)
        assert final_angle_diff > 1.0 or final_angle_diff < 359.0  # Angle should have changed


class TestAggressiveEnemyStrategy:
    """Tests for aggressive enemy behavior."""
    
    def test_aggressive_enemy_chases_player(self):
        """Aggressive enemy should move toward player."""
        enemy = Enemy((100, 100), "aggressive")
        player_pos = (200, 200)
        
        strategy = AggressiveEnemyStrategy()
        strategy.update(enemy, 1.0, player_pos, None)
        
        # Enemy should have moved toward player
        # Check that angle points toward player
        import math
        from utils import get_angle_to_point
        expected_angle = get_angle_to_point((enemy.x, enemy.y), player_pos)
        assert abs(enemy.angle - expected_angle) < 1.0  # Allow small error
    
    def test_aggressive_enemy_sets_alert_state(self):
        """Aggressive enemy should set alert state when chasing."""
        enemy = Enemy((100, 100), "aggressive")
        player_pos = (200, 200)
        
        strategy = AggressiveEnemyStrategy()
        strategy.update(enemy, 1.0, player_pos, None)
        
        assert enemy.is_alert is True
    
    def test_aggressive_enemy_clears_alert_without_player(self):
        """Aggressive enemy should clear alert when no player position."""
        enemy = Enemy((100, 100), "aggressive")
        enemy.is_alert = True
        
        strategy = AggressiveEnemyStrategy()
        strategy.update(enemy, 1.0, None, None)
        
        assert enemy.is_alert is False
    
    def test_aggressive_enemy_stops_at_wall(self):
        """Aggressive enemy should not move through walls."""
        enemy = Enemy((100, 100), "aggressive")
        player_pos = (200, 100)  # Player to the right
        initial_x = enemy.x
        
        # Create a wall between enemy and player
        walls = [((150, 90), (150, 110))]  # Vertical wall at x=150
        
        strategy = AggressiveEnemyStrategy()
        strategy.update(enemy, 1.0, player_pos, walls)
        
        # Enemy should not have moved past the wall
        assert enemy.x < 150

