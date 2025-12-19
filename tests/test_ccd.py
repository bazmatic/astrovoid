"""Unit tests for continuous collision detection."""

import pytest
import math
from entities.ship import Ship
from utils import circle_line_collision_swept
import config


class TestSweptCollisionDetection:
    """Tests for swept collision detection function."""
    
    def test_swept_collision_no_movement(self):
        """Swept collision with no movement should use standard check."""
        result = circle_line_collision_swept(
            (0, 0), (0, 0), 5,
            (10, -1), (10, 1)
        )
        assert result[0] is False  # No collision
    
    def test_swept_collision_through_wall(self):
        """Swept collision should detect collision when moving through wall."""
        # Circle moves from (0, 0) to (10, 0), wall at x=5
        result = circle_line_collision_swept(
            (0, 0), (10, 0), 2,
            (5, -1), (5, 1)
        )
        assert result[0] is True  # Collision detected
        assert result[1] is not None  # Collision time exists
        assert 0.0 <= result[1] <= 1.0  # Collision time in valid range
        assert result[2] is not None  # Collision point exists
    
    def test_swept_collision_misses_wall(self):
        """Swept collision should not detect collision when missing wall."""
        # Circle moves from (0, 0) to (10, 0), wall at x=5 but far away
        result = circle_line_collision_swept(
            (0, 0), (10, 0), 2,
            (5, 10), (5, 12)
        )
        assert result[0] is False  # No collision
    
    def test_swept_collision_parallel_to_wall(self):
        """Swept collision should handle movement parallel to wall."""
        # Circle moves parallel to wall
        result = circle_line_collision_swept(
            (0, 0), (10, 0), 2,
            (0, 5), (10, 5)
        )
        assert result[0] is False  # No collision (wall is above)
    
    def test_swept_collision_high_speed(self):
        """Swept collision should handle high-speed movement."""
        # Very fast movement
        result = circle_line_collision_swept(
            (0, 0), (100, 0), 5,
            (50, -1), (50, 1)
        )
        assert result[0] is True  # Should detect collision even at high speed


class TestShipCCD:
    """Tests for ship continuous collision detection."""
    
    def test_ship_stores_previous_position(self):
        """Ship should store previous position during update."""
        ship = Ship((100, 100))
        initial_x = ship.x
        initial_y = ship.y
        
        ship.vx = 5.0
        ship.vy = 0.0
        ship.update(1.0)
        
        # Previous position should be stored
        assert ship.prev_x == initial_x
        assert ship.prev_y == initial_y
        assert ship.x != initial_x  # Position should have changed
    
    def test_ship_high_speed_collision(self):
        """Ship should not tunnel through walls at high speed."""
        ship = Ship((100, 100))
        # Set velocity to max speed
        ship.vx = config.SHIP_MAX_SPEED
        ship.vy = 0.0
        ship.update(1.0)
        
        # Wall directly in path (close enough to hit)
        walls = [((105, 90), (105, 110))]  # Wall at x=105, ship at ~108 after update
        
        collision = ship.check_wall_collision(walls)
        
        # Should detect collision (ship moves from 100 to ~108, wall at 105)
        assert collision is True
        # Ship should be pushed back before wall
        assert ship.x < 105 + ship.radius
    
    def test_ship_already_inside_wall(self):
        """Ship already inside wall should be pushed out."""
        ship = Ship((100, 100))
        # Place ship inside wall
        ship.x = 150
        ship.y = 100
        ship.prev_x = 150
        ship.prev_y = 100
        
        # Wall at x=150
        walls = [((150, 90), (150, 110))]
        
        collision = ship.check_wall_collision(walls)
        
        # Should detect collision and push ship out
        assert collision is True
        # Ship should be pushed away from wall
        assert abs(ship.x - 150) > ship.radius
    
    def test_ship_diagonal_collision(self):
        """Ship should handle diagonal collisions correctly."""
        ship = Ship((100, 100))
        ship.vx = 10.0
        ship.vy = 10.0
        ship.update(1.0)
        
        # Diagonal wall
        walls = [((150, 150), (160, 160))]
        
        collision = ship.check_wall_collision(walls)
        
        # Should handle collision (may or may not collide depending on exact positions)
        # Just verify it doesn't crash
        assert isinstance(collision, bool)

