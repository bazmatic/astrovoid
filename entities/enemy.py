"""Enemy entity implementation.

This module implements the Enemy class using the Strategy pattern for behaviors,
following the Open/Closed Principle.
"""

import pygame
import random
import math
from typing import Tuple, List, Optional
import config
from utils import (
    angle_to_radians,
    circle_line_collision,
    circle_circle_collision,
    get_angle_to_point
)
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from entities.enemy_strategies import (
    StaticEnemyStrategy,
    PatrolEnemyStrategy,
    AggressiveEnemyStrategy
)


class Enemy(GameEntity, Collidable, Drawable):
    """Enemy entity with configurable behavior strategies.
    
    Uses the Strategy pattern to allow different enemy behaviors without
    modifying the Enemy class itself. This follows the Open/Closed Principle.
    
    Attributes:
        strategy: The behavior strategy for this enemy.
        speed: Movement speed (for dynamic enemies).
        angle: Current facing angle in degrees.
    """
    
    def __init__(self, pos: Tuple[float, float], enemy_type: str = "static"):
        """Initialize enemy at position with specified type.
        
        Args:
            pos: Initial position as (x, y) tuple.
            enemy_type: Type of enemy - "static", "patrol", or "aggressive".
        """
        radius = config.STATIC_ENEMY_SIZE if enemy_type == "static" else config.DYNAMIC_ENEMY_SIZE
        super().__init__(pos, radius)
        
        self.type = enemy_type
        
        # Set strategy based on type
        if enemy_type == "static":
            self.strategy = StaticEnemyStrategy()
            self.speed = 0.0
            self.angle = 0.0
        elif enemy_type == "patrol":
            self.strategy = PatrolEnemyStrategy()
            self.speed = config.ENEMY_PATROL_SPEED
            self.angle = random.uniform(0, 360)
        elif enemy_type == "aggressive":
            self.strategy = AggressiveEnemyStrategy()
            self.speed = config.ENEMY_AGGRESSIVE_SPEED
            self.angle = 0.0
        else:
            raise ValueError(f"Unknown enemy type: {enemy_type}")
    
    def update(
        self,
        dt: float,
        player_pos: Optional[Tuple[float, float]] = None,
        walls: Optional[List] = None
    ) -> None:
        """Update enemy position and behavior using strategy.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position, if available.
            walls: List of wall segments for collision detection.
        """
        if not self.active:
            return
        
        self.strategy.update(self, dt, player_pos, walls)
    
    def check_wall_collision(
        self,
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> bool:
        """Check collision with wall segments.
        
        Args:
            walls: List of wall line segments.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        for wall in walls:
            if circle_line_collision(
                (self.x, self.y), self.radius,
                wall[0], wall[1]
            ):
                return True
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float
    ) -> bool:
        """Check collision with another circular entity.
        
        Args:
            other_pos: Position of the other entity (x, y).
            other_radius: Radius of the other entity.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        return circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        )
    
    def destroy(self) -> None:
        """Destroy the enemy."""
        self.active = False
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the enemy on screen.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        color = config.COLOR_ENEMY_STATIC if self.type == "static" else config.COLOR_ENEMY_DYNAMIC
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 2)
        
        # Draw direction indicator for dynamic enemies
        if self.type != "static":
            angle_rad = angle_to_radians(self.angle)
            indicator_x = self.x + math.cos(angle_rad) * self.radius
            indicator_y = self.y + math.sin(angle_rad) * self.radius
            pygame.draw.line(
                screen, (255, 255, 255),
                (int(self.x), int(self.y)),
                (int(indicator_x), int(indicator_y)), 2
            )


def create_enemies(level: int, spawn_positions: List[Tuple[float, float]]) -> List[Enemy]:
    """Create enemies for a level.
    
    Args:
        level: Current level number.
        spawn_positions: List of valid spawn positions.
        
    Returns:
        List of Enemy instances.
    """
    enemy_count = config.BASE_ENEMY_COUNT + (level - 1) * config.ENEMY_COUNT_INCREMENT
    enemy_count = min(enemy_count, len(spawn_positions))
    
    enemies = []
    used_positions = []
    
    # Determine enemy type distribution
    static_count = max(1, enemy_count // 2)
    dynamic_count = enemy_count - static_count
    
    # Shuffle positions
    available_positions = spawn_positions.copy()
    random.shuffle(available_positions)
    
    # Create static enemies
    for i in range(min(static_count, len(available_positions))):
        pos = available_positions[i]
        enemies.append(Enemy(pos, "static"))
        used_positions.append(pos)
    
    # Create dynamic enemies (patrol and aggressive)
    remaining_positions = [p for p in available_positions if p not in used_positions]
    patrol_count = dynamic_count // 2
    aggressive_count = dynamic_count - patrol_count
    
    for i in range(min(patrol_count, len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "patrol"))
    
    remaining_positions = [p for p in remaining_positions if p not in [e.get_pos() for e in enemies]]
    for i in range(min(aggressive_count, len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "aggressive"))
    
    return enemies

