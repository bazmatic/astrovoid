"""Enemy behavior strategies.

This module implements the Strategy pattern for enemy behaviors, allowing
new enemy types to be added without modifying the Enemy class (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, List
import math
import random
import config
from utils import (
    angle_to_radians,
    circle_line_collision,
    get_angle_to_point,
    distance
)
from entities.projectile import Projectile

# Enemy behavior modes
MODE_SEEK_ENEMY = "seek_enemy"  # Normal chase mode
MODE_ESCAPE_OBSTACLE = "escape_obstacle"  # Escaping from obstacle/wall


class EnemyStrategy(ABC):
    """Abstract base class for enemy movement strategies."""
    
    @abstractmethod
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Update enemy position and behavior based on strategy.
        
        Args:
            enemy: The enemy entity to update.
            dt: Delta time since last update.
            player_pos: Current player position, if available.
            walls: List of wall segments for collision detection.
        """
        pass
    
    def _apply_velocity_based_movement(
        self,
        enemy: 'Enemy',
        target_angle: float,
        dt: float,
        base_blend_factor: float = 0.7
    ) -> Tuple[float, float]:
        """Apply velocity-based movement that respects collision physics.
        
        This method preserves collision bounce effects by only blending when velocities
        are similar. If there's a significant velocity difference (indicating a collision),
        the collision velocity is preserved to maintain the bounce effect.
        
        Args:
            enemy: The enemy entity to update.
            target_angle: Desired movement angle in degrees.
            dt: Delta time since last update.
            base_blend_factor: Base blend factor when velocities are aligned (0.0-1.0).
                              Default 0.7 means 70% desired, 30% existing velocity.
        
        Returns:
            Tuple of (new_x, new_y) position after movement.
        """
        # Calculate desired velocity in target direction
        angle_rad = angle_to_radians(target_angle)
        desired_vx = math.cos(angle_rad) * enemy.speed
        desired_vy = math.sin(angle_rad) * enemy.speed
        
        # Calculate current velocity magnitude and direction
        current_speed = math.sqrt(enemy.vx * enemy.vx + enemy.vy * enemy.vy)
        desired_speed = enemy.speed
        
        # Detect if current velocity is from a collision (based on physics laws)
        # A collision creates velocity that doesn't match desired movement
        if current_speed > 0.01:  # Avoid division by zero
            # Calculate angle difference between current and desired velocity
            current_angle_rad = math.atan2(enemy.vy, enemy.vx)
            desired_angle_rad = angle_rad
            angle_diff = abs(current_angle_rad - desired_angle_rad)
            # Normalize to 0-π range
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            # Calculate speed ratio for collision detection
            speed_ratio = current_speed / max(desired_speed, 0.1)  # Avoid division by zero
            
            # Calculate how aligned current velocity is with desired velocity
            # Dot product of normalized velocity vectors
            if current_speed > 0.0:
                current_vx_norm = enemy.vx / current_speed
                current_vy_norm = enemy.vy / current_speed
                desired_vx_norm = math.cos(desired_angle_rad)
                desired_vy_norm = math.sin(desired_angle_rad)
                alignment_dot = current_vx_norm * desired_vx_norm + current_vy_norm * desired_vy_norm
            else:
                alignment_dot = 0.0
            
            # Detect collision velocity more accurately to avoid interfering with pursuit:
            # Collision velocity is characterized by:
            # 1. Velocity direction is opposite or nearly opposite to desired (alignment < 0)
            # 2. OR velocity is perpendicular AND speed is much higher (bounce effect)
            # Normal pursuit will have velocities that are reasonably aligned, so we allow blending
            is_collision_velocity = False
            if alignment_dot < -0.2:  # Velocities are opposite or nearly opposite (clear collision)
                is_collision_velocity = True
            elif alignment_dot < 0.2 and speed_ratio > 1.5:  # Perpendicular AND speed is 50%+ higher
                # Very misaligned direction AND significantly higher speed (bounce)
                is_collision_velocity = True
            
            if is_collision_velocity:
                # Preserve collision bounce - minimal blending, let physics and friction handle it
                # This maintains the bounce effect based on conservation of momentum
                blend_factor = 0.15  # Small blend to allow gradual recovery while preserving bounce
            else:
                # Velocities are reasonably aligned - blend towards desired movement
                # This allows normal pursuit to work correctly
                if alignment_dot > 0.7:
                    # Well aligned - strong blending towards desired
                    blend_factor = base_blend_factor
                elif alignment_dot > 0.3:
                    # Moderately aligned - moderate blending
                    blend_factor = base_blend_factor * 0.8
                else:
                    # Somewhat misaligned but not collision - still blend to correct course
                    blend_factor = base_blend_factor * 0.5
        else:
            # No current velocity - full blend to desired
            blend_factor = 1.0
        
        # Blend existing velocity (from collisions) with desired velocity
        # This preserves collision bounce while allowing gradual return to desired movement
        enemy.vx = enemy.vx * (1.0 - blend_factor) + desired_vx * blend_factor
        enemy.vy = enemy.vy * (1.0 - blend_factor) + desired_vy * blend_factor
        
        # Apply friction and update position using shared method
        enemy.apply_friction_and_update_position(config.FRICTION_COEFFICIENT, dt)
        
        return (enemy.x, enemy.y)


class StaticEnemyStrategy(EnemyStrategy):
    """Strategy for static enemies that can move when hit by projectiles."""
    
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Update static enemy position based on momentum and handle wall collisions.
        
        Args:
            enemy: The enemy entity to update.
            dt: Delta time since last update.
            player_pos: Current player position (unused for static enemies).
            walls: List of wall segments for collision detection.
        """
        # Apply velocity to position first (static enemies use momentum from projectiles)
        enemy.x += enemy.vx * dt
        enemy.y += enemy.vy * dt
        
        # Apply friction
        enemy.vx *= config.FRICTION_COEFFICIENT
        enemy.vy *= config.FRICTION_COEFFICIENT
        
        # Stop if velocity is too small
        if abs(enemy.vx) < config.MIN_VELOCITY_THRESHOLD:
            enemy.vx = 0.0
        if abs(enemy.vy) < config.MIN_VELOCITY_THRESHOLD:
            enemy.vy = 0.0
        
        # Check wall collision (handles bouncing)
        if walls:
            enemy.check_wall_collision(walls)


class PatrolEnemyStrategy(EnemyStrategy):
    """Strategy for enemies that patrol in straight lines."""
    
    def __init__(self):
        """Initialize patrol strategy."""
        self.patrol_distance = 0.0
        self.max_patrol_distance = 0.0
        self.initial_angle = 0.0
        self.fire_cooldown: int = 0  # Frames remaining until next shot
        self.next_fire_interval: int = 0  # Random interval for next shot
        self.previous_angle: Optional[float] = None  # Track previous angle to detect reversals
    
    def initialize(self, enemy: 'Enemy') -> None:
        """Initialize patrol parameters for an enemy.
        
        Args:
            enemy: The enemy to initialize patrol behavior for.
        """
        import random
        if self.max_patrol_distance == 0.0:
            self.max_patrol_distance = random.uniform(50, 150)
            self.initial_angle = enemy.angle
    
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Update patrol enemy movement."""
        self.initialize(enemy)
        
        # Decrement fire cooldown
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        # Initialize next fire interval on first call if needed
        if self.next_fire_interval == 0:
            self.next_fire_interval = random.randint(
                enemy.fire_interval_min,
                enemy.fire_interval_max
            )
            self.fire_cooldown = self.next_fire_interval
        
        # Check if direction was reversed (intentional direction change)
        angle_reversed = False
        if self.previous_angle is not None:
            angle_diff = abs(enemy.angle - self.previous_angle)
            # Normalize to 0-180 range
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            # If angle changed by ~180 degrees, it's an intentional reversal
            if angle_diff > 150:  # Allow some tolerance
                angle_reversed = True
        
        # Apply velocity-based movement that respects collision physics
        # For patrol enemies, allow immediate reversal when direction changes
        if angle_reversed:
            # Force immediate velocity change for direction reversal
            angle_rad = angle_to_radians(enemy.angle)
            enemy.vx = math.cos(angle_rad) * enemy.speed
            enemy.vy = math.sin(angle_rad) * enemy.speed
            new_x = enemy.x + enemy.vx * dt
            new_y = enemy.y + enemy.vy * dt
        else:
            new_x, new_y = self._apply_velocity_based_movement(enemy, enemy.angle, dt)
        
        # Check wall collision
        hit_wall = False
        if walls:
            for wall in walls:
                # Handle both WallSegment and tuple formats
                if hasattr(wall, 'get_segment'):
                    if not wall.active:
                        continue
                    segment = wall.get_segment()
                else:
                    segment = wall
                if circle_line_collision((new_x, new_y), enemy.radius, segment[0], segment[1]):
                    hit_wall = True
                    break
        
        if hit_wall or self.patrol_distance >= self.max_patrol_distance:
            # Reverse direction
            enemy.angle = (enemy.angle + 180) % 360
            self.patrol_distance = 0.0
        else:
            enemy.x = new_x
            enemy.y = new_y
            self.patrol_distance += enemy.speed * dt
        
        # Store current angle for next frame
        self.previous_angle = enemy.angle
    
    def fire(self, enemy: 'Enemy', player_pos: Optional[Tuple[float, float]]) -> Optional[Projectile]:
        """Fire a bullet at the player if cooldown expired and player in range.
        
        Args:
            enemy: The enemy entity.
            player_pos: Current player position.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        # Check if cooldown expired and player position is available
        if self.fire_cooldown > 0 or not player_pos:
            return None
        
        # Calculate distance to player
        dist_to_player = distance((enemy.x, enemy.y), player_pos)
        
        # Check if player is within firing range
        if dist_to_player > enemy.fire_range:
            return None
        
        # Calculate angle to player
        angle_to_player = get_angle_to_point((enemy.x, enemy.y), player_pos)
        
        # Create projectile at enemy position aimed at player
        projectile = Projectile((enemy.x, enemy.y), angle_to_player, is_enemy=True)
        
        # Reset cooldown with random interval
        self.next_fire_interval = random.randint(
            enemy.fire_interval_min,
            enemy.fire_interval_max
        )
        self.fire_cooldown = self.next_fire_interval
        
        return projectile


class AggressiveEnemyStrategy(EnemyStrategy):
    """Strategy for enemies that chase the player."""
    
    def __init__(self):
        """Initialize aggressive enemy strategy."""
        self.mode: str = MODE_SEEK_ENEMY  # Current behavior mode
        self.previous_pos: Optional[Tuple[float, float]] = None  # Track previous position
        self.shift_angle: Optional[float] = None  # Current escape angle (None when not escaping)
        self.shift_frames_remaining: int = 0  # Frames remaining in escape mode
    
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Update aggressive enemy to chase player with smart wall avoidance."""
        # Reset mode if player position unavailable
        if not player_pos:
            enemy.is_alert = False
            self.mode = MODE_SEEK_ENEMY
            self.shift_frames_remaining = 0
            self.previous_pos = None
            return
        
        # Store current position for stuck detection
        current_pos = (enemy.x, enemy.y)
        
        # Set alert state when chasing player
        enemy.is_alert = True
        
        # Mode-based behavior
        if self.mode == MODE_SEEK_ENEMY:
            # Normal chase behavior
            target_angle = get_angle_to_point((enemy.x, enemy.y), player_pos)
            enemy.angle = target_angle
            
            # Apply velocity-based movement that respects collision physics
            # This updates velocity and position
            self._apply_velocity_based_movement(enemy, target_angle, dt)
            
            # Check and handle wall collisions (bounces off walls)
            # This must be called after movement to detect collisions
            if walls:
                enemy.check_wall_collision(walls)
            
            # Check if stuck (position hasn't changed significantly)
            if self.previous_pos is not None:
                distance_moved = math.sqrt(
                    (enemy.x - self.previous_pos[0])**2 + 
                    (enemy.y - self.previous_pos[1])**2
                )
                is_stuck = distance_moved < config.ENEMY_STUCK_DETECTION_THRESHOLD
                
                if is_stuck:
                    # Switch to escape mode
                    self.mode = MODE_ESCAPE_OBSTACLE
                    # Calculate angle away from player (180 degrees from player direction)
                    angle_to_player = get_angle_to_point((enemy.x, enemy.y), player_pos)
                    # Move 180 degrees away from player, plus or minus random 45 degrees
                    escape_angle = (angle_to_player + 180 + random.uniform(-45, 45)) % 360
                    enemy.angle = escape_angle
                    # Set random shift duration (10-100 frames)
                    self.shift_frames_remaining = random.randint(
                        config.ENEMY_SHIFT_DURATION_MIN,
                        config.ENEMY_SHIFT_DURATION_MAX
                    )
                    self.shift_angle = escape_angle
            
        elif self.mode == MODE_ESCAPE_OBSTACLE:
            # Escape obstacle mode - move in shifted direction
            # Decrement frames remaining
            self.shift_frames_remaining -= 1
            
            # Apply velocity-based movement that respects collision physics
            # This updates velocity and position
            self._apply_velocity_based_movement(enemy, enemy.angle, dt)
            
            # Check and handle wall collisions (bounces off walls)
            # This must be called after movement to detect collisions
            if walls:
                enemy.check_wall_collision(walls)
            
            # If shift duration expired, switch back to seek mode
            if self.shift_frames_remaining <= 0:
                self.mode = MODE_SEEK_ENEMY
                self.shift_frames_remaining = 0
                self.shift_angle = None
        
        # Update previous position for next frame
        self.previous_pos = current_pos

