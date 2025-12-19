"""Enemy behavior strategies.

This module implements the Strategy pattern for enemy behaviors, allowing
new enemy types to be added without modifying the Enemy class (Open/Closed Principle).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, List
import math
import config
from utils import (
    angle_to_radians,
    circle_line_collision,
    get_angle_to_point
)


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
        
        angle_rad = angle_to_radians(enemy.angle)
        dx = math.cos(angle_rad) * enemy.speed * dt
        dy = math.sin(angle_rad) * enemy.speed * dt
        
        new_x = enemy.x + dx
        new_y = enemy.y + dy
        
        # Check wall collision
        hit_wall = False
        if walls:
            for wall in walls:
                if circle_line_collision((new_x, new_y), enemy.radius, wall[0], wall[1]):
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


class AggressiveEnemyStrategy(EnemyStrategy):
    """Strategy for enemies that chase the player."""
    
    def update(
        self,
        enemy: 'Enemy',
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        walls: Optional[List]
    ) -> None:
        """Update aggressive enemy to chase player."""
        if not player_pos:
            return
        
        # Calculate angle to player
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
                if circle_line_collision((new_x, new_y), enemy.radius, wall[0], wall[1]):
                    can_move = False
                    break
        
        if can_move:
            enemy.x = new_x
            enemy.y = new_y

