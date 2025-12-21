"""Unit tests for ship physics and behavior."""

import pytest
import math
from entities.ship import Ship
import config
from utils import normalize_angle, angle_to_radians


class TestShipRotation:
    """Tests for ship rotation."""
    
    def test_rotate_left(self):
        """Rotating left should decrease angle (or wrap around)."""
        ship = Ship((100, 100))
        initial_angle = ship.angle
        ship.rotate_left()
        # Angle should be normalized and decreased (or wrapped if near 0)
        expected_angle = normalize_angle(initial_angle - config.SHIP_ROTATION_SPEED)
        assert ship.angle == expected_angle
    
    def test_rotate_right(self):
        """Rotating right should increase angle."""
        ship = Ship((100, 100))
        initial_angle = ship.angle
        ship.rotate_right()
        assert ship.angle > initial_angle
        assert ship.angle == normalize_angle(initial_angle + config.SHIP_ROTATION_SPEED)
    
    def test_rotate_wraps_around(self):
        """Rotation should wrap around 360 degrees."""
        ship = Ship((100, 100))
        ship.angle = 359.0
        ship.rotate_right()
        # Should wrap to near 0 (or 2 degrees)
        assert ship.angle < 10.0 or ship.angle > 350.0
        
        ship.angle = 1.0
        ship.rotate_left()
        # Should wrap to near 360
        assert ship.angle > 350.0 or ship.angle < 10.0


class TestShipThrust:
    """Tests for ship thrust mechanics."""
    
    def test_apply_thrust_with_fuel(self):
        """Thrust should work when fuel is available."""
        ship = Ship((100, 100))
        initial_vx = ship.vx
        initial_vy = ship.vy
        initial_fuel = ship.fuel
        
        result = ship.apply_thrust()
        
        assert result is True
        assert ship.vx != initial_vx or ship.vy != initial_vy  # Velocity changed
        assert ship.fuel < initial_fuel  # Fuel consumed
        assert ship.thrusting is True  # Thrusting flag set
    
    def test_apply_thrust_no_fuel(self):
        """Thrust should fail when out of fuel."""
        ship = Ship((100, 100))
        ship.fuel = 0
        
        result = ship.apply_thrust()
        
        assert result is False
        assert ship.vx == 0.0
        assert ship.vy == 0.0
        assert ship.fuel == 0
    
    def test_apply_thrust_direction(self):
        """Thrust should apply in ship's facing direction."""
        ship = Ship((100, 100))
        ship.angle = 0.0  # Facing right
        
        ship.apply_thrust()
        
        # Should have positive x velocity
        assert ship.vx > 0
        # Should have near-zero y velocity (0 degrees)
        assert abs(ship.vy) < 0.1
    
    def test_apply_thrust_max_speed_limit(self):
        """Thrust should not exceed max speed."""
        ship = Ship((100, 100))
        # Apply many thrusts
        for _ in range(100):
            ship.apply_thrust()
        
        speed = math.sqrt(ship.vx * ship.vx + ship.vy * ship.vy)
        assert speed <= config.SHIP_MAX_SPEED + 0.1  # Allow small floating point error
    
    def test_thrust_consumes_fuel(self):
        """Each thrust should consume fuel."""
        ship = Ship((100, 100))
        initial_fuel = ship.fuel
        
        ship.apply_thrust()
        
        assert ship.fuel == initial_fuel - config.FUEL_CONSUMPTION_PER_THRUST


class TestShipUpdate:
    """Tests for ship update mechanics."""
    
    def test_update_clears_thrusting_flag(self):
        """Update should clear thrusting flag."""
        ship = Ship((100, 100))
        ship.apply_thrust()
        assert ship.thrusting is True
        
        ship.update(0.016)
        
        assert ship.thrusting is False
    
    def test_update_creates_thrust_particles(self):
        """Update should create particles when was_thrusting."""
        ship = Ship((100, 100))
        ship.apply_thrust()
        ship.vx = 5.0  # Give it some velocity
        ship.vy = 0.0
        
        ship.update(0.016)
        
        # Should have created some particles
        assert len(ship.thrust_particles) > 0


class TestShipCollision:
    """Tests for ship collision detection."""
    
    def test_check_circle_collision_overlapping(self):
        """Ship should detect collision with overlapping circle."""
        ship = Ship((100, 100))
        # Enemy at same position
        assert ship.check_circle_collision((100, 100), 5) is True
    
    def test_check_circle_collision_not_touching(self):
        """Ship should not detect collision when not touching."""
        ship = Ship((100, 100))
        # Enemy far away
        assert ship.check_circle_collision((200, 200), 5) is False
    
    def test_check_circle_collision_causes_damage(self):
        """Collision should set damaged state."""
        ship = Ship((100, 100))
        ship.check_circle_collision((100, 100), 5)
        
        assert ship.damaged is True
        assert ship.damage_timer > 0


class TestShipFire:
    """Tests for ship projectile firing."""
    
    def test_fire_with_ammo(self):
        """Firing with ammo should create projectile."""
        ship = Ship((100, 100))
        initial_ammo = ship.ammo
        
        projectile = ship.fire()
        
        assert projectile is not None
        assert ship.ammo < initial_ammo
        assert ship.ammo == initial_ammo - config.AMMO_CONSUMPTION_PER_SHOT
    
    def test_fire_no_ammo(self):
        """Firing without ammo should return None."""
        ship = Ship((100, 100))
        ship.ammo = 0
        
        projectile = ship.fire()
        
        assert projectile is None
        assert ship.ammo == 0
    
    def test_fire_projectile_position(self):
        """Projectile should be created ahead of ship."""
        ship = Ship((100, 100))
        ship.angle = 0.0  # Facing right
        
        projectiles = ship.fire()
        
        assert projectiles is not None
        assert len(projectiles) > 0
        projectile = projectiles[0]  # Get first projectile
        # Projectile should be to the right of ship (higher x)
        assert projectile.x > ship.x
        # Projectile should be at similar y
        assert abs(projectile.y - ship.y) < 10

