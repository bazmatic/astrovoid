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


class StaticEnemyStrategy(EnemyStrategy):
    """Strategy for static enemies that don't move."""
    
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Static enemies don't move, so no update needed."""
        pass


class PatrolEnemyStrategy(EnemyStrategy):
    """Strategy for enemies that patrol in straight lines."""
    
    def __init__(self):
        """Initialize patrol strategy."""
        self.patrol_distance = 0.0
        self.max_patrol_distance = 0.0
        self.initial_angle = 0.0
        self.fire_cooldown: int = 0  # Frames remaining until next shot
        self.next_fire_interval: int = 0  # Random interval for next shot
    
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
        
        angle_rad = angle_to_radians(enemy.angle)
        dx = math.cos(angle_rad) * enemy.speed * dt
        dy = math.sin(angle_rad) * enemy.speed * dt
        
        new_x = enemy.x + dx
        new_y = enemy.y + dy
        
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
            
            # Move towards player
            angle_rad = angle_to_radians(enemy.angle)
            dx = math.cos(angle_rad) * enemy.speed * dt
            dy = math.sin(angle_rad) * enemy.speed * dt
            
            new_x = enemy.x + dx
            new_y = enemy.y + dy
            
            # Check wall collision
            can_move = True
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
                        can_move = False
                        break
            
            if can_move:
                enemy.x = new_x
                enemy.y = new_y
            
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
            
            # Move in the shifted direction (not toward player)
            angle_rad = angle_to_radians(enemy.angle)
            dx = math.cos(angle_rad) * enemy.speed * dt
            dy = math.sin(angle_rad) * enemy.speed * dt
            
            new_x = enemy.x + dx
            new_y = enemy.y + dy
            
            # Check wall collision
            can_move = True
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
                        can_move = False
                        break
            
            if can_move:
                enemy.x = new_x
                enemy.y = new_y
            
            # If shift duration expired, switch back to seek mode
            if self.shift_frames_remaining <= 0:
                self.mode = MODE_SEEK_ENEMY
                self.shift_frames_remaining = 0
                self.shift_angle = None
        
        # Update previous position for next frame
        self.previous_pos = current_pos

