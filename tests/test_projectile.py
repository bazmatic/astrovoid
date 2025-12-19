"""Unit tests for projectile behavior."""

import pytest
import math
from entities.projectile import Projectile
import config
from utils import angle_to_radians


class TestProjectileMovement:
    """Tests for projectile movement."""
    
    def test_projectile_moves(self):
        """Projectile should move when updated."""
        projectile = Projectile((100, 100), 0.0)  # Facing right
        initial_x = projectile.x
        
        projectile.update(1.0)  # 1 second
        
        assert projectile.x > initial_x  # Should have moved right
    
    def test_projectile_moves_in_direction(self):
        """Projectile should move in its firing direction."""
        projectile = Projectile((100, 100), 90.0)  # Facing down
        initial_y = projectile.y
        
        projectile.update(1.0)
        
        assert projectile.y > initial_y  # Should have moved down
    
    def test_projectile_lifetime_decreases(self):
        """Projectile lifetime should decrease on update."""
        projectile = Projectile((100, 100), 0.0)
        initial_lifetime = projectile.lifetime
        
        projectile.update(1.0)
        
        assert projectile.lifetime < initial_lifetime
        assert projectile.lifetime == initial_lifetime - 1
    
    def test_projectile_deactivates_when_lifetime_expires(self):
        """Projectile should deactivate when lifetime expires."""
        projectile = Projectile((100, 100), 0.0)
        projectile.lifetime = 1
        
        projectile.update(1.0)
        
        assert projectile.active is False
    
    def test_projectile_deactivates_out_of_bounds(self):
        """Projectile should deactivate when out of bounds."""
        projectile = Projectile((-200, 100), 0.0)  # Way off screen
        
        projectile.update(1.0)
        
        assert projectile.active is False


class TestProjectileCollision:
    """Tests for projectile collision detection."""
    
    def test_projectile_collides_with_wall(self):
        """Projectile should detect wall collision."""
        projectile = Projectile((100, 100), 0.0)  # Moving right
        walls = [((150, 90), (150, 110))]  # Wall at x=150
        
        # Move projectile to wall
        for _ in range(10):
            projectile.update(1.0)
            if projectile.check_wall_collision(walls):
                break
        
        # Should have collided and deactivated
        assert projectile.active is False
    
    def test_projectile_collides_with_enemy(self):
        """Projectile should detect enemy collision."""
        projectile = Projectile((100, 100), 0.0)
        enemy_pos = (105, 100)  # Close to projectile
        enemy_radius = 10
        
        result = projectile.check_circle_collision(enemy_pos, enemy_radius)
        
        assert result is True
        assert projectile.active is False
    
    def test_projectile_no_collision_when_far(self):
        """Projectile should not collide when far from enemy."""
        projectile = Projectile((100, 100), 0.0)
        enemy_pos = (200, 200)  # Far away
        enemy_radius = 10
        
        result = projectile.check_circle_collision(enemy_pos, enemy_radius)
        
        assert result is False
        assert projectile.active is True

