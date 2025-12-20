"""Projectile entity implementation.

This module implements the Projectile class for weapons fired by the ship.
"""

import pygame
import math
from typing import Tuple, List, Optional
import config
from utils import (
    angle_to_radians,
    circle_line_collision,
    circle_circle_collision
)
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable


class Projectile(GameEntity, Collidable, Drawable):
    """Represents a projectile fired from the ship or enemy.
    
    Attributes:
        angle: Firing angle in degrees.
        lifetime: Remaining lifetime in frames.
        is_enemy: Whether this is an enemy projectile.
    """
    
    def __init__(self, start_pos: Tuple[float, float], angle: float, is_enemy: bool = False):
        """Initialize projectile at position with given angle.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            angle: Firing angle in degrees.
            is_enemy: Whether this is an enemy projectile (default: False).
        """
        # Calculate velocity from angle
        angle_rad = angle_to_radians(angle)
        vx = math.cos(angle_rad) * config.PROJECTILE_SPEED
        vy = math.sin(angle_rad) * config.PROJECTILE_SPEED
        
        super().__init__(start_pos, config.PROJECTILE_SIZE, vx, vy)
        self.angle = angle
        self.lifetime = config.PROJECTILE_LIFETIME
        self.is_enemy = is_enemy
    
    def update(self, dt: float) -> None:
        """Update projectile position and lifetime.
        
        Args:
            dt: Delta time since last update.
        """
        if not self.active:
            return
        
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.lifetime -= 1
        
        # Deactivate if lifetime expired or out of bounds
        if self.lifetime <= 0:
            self.active = False
        elif (self.x < -100 or self.x > config.SCREEN_WIDTH + 100 or
              self.y < -100 or self.y > config.SCREEN_HEIGHT + 100):
            self.active = False
    
    def check_wall_collision(
        self,
        walls: List,
        spatial_grid=None
    ) -> Optional:
        """Check collision with walls.
        
        Args:
            walls: List of wall segments (WallSegment instances or tuples).
            spatial_grid: Optional spatial grid for optimized collision detection.
            
        Returns:
            The wall segment that was hit, or None if no collision.
        """
        # Use spatial grid if available, otherwise check all walls
        walls_to_check = walls
        if spatial_grid is not None:
            walls_to_check = spatial_grid.get_nearby_walls(
                (self.x, self.y), self.radius * 2.0
            )
        
        for wall in walls_to_check:
            # Handle both WallSegment and tuple formats
            if hasattr(wall, 'get_segment'):
                # WallSegment instance
                if not wall.active:
                    continue
                segment = wall.get_segment()
            else:
                # Tuple format (backward compatibility)
                segment = wall
            
            if circle_line_collision(
                (self.x, self.y), self.radius,
                segment[0], segment[1]
            ):
                self.active = False
                return wall
        return None
    
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
        if circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        ):
            self.active = False
            return True
        return False
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the projectile as a line pointing in the direction of travel.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Use different color for enemy projectiles
        color = config.COLOR_ENEMY_PROJECTILE if self.is_enemy else config.COLOR_PROJECTILE
        
        # Calculate direction of travel from velocity vector
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > 0:
            # Normalize velocity to get direction
            dir_x = self.vx / speed
            dir_y = self.vy / speed
        else:
            # Fallback to angle if velocity is zero (shouldn't happen, but safe)
            angle_rad = angle_to_radians(self.angle)
            dir_x = math.cos(angle_rad)
            dir_y = math.sin(angle_rad)
        
        # Line length (2-3 times the radius for visibility)
        line_length = self.radius * 2.5
        
        # Calculate line endpoints
        start_x = self.x - dir_x * line_length * 0.5
        start_y = self.y - dir_y * line_length * 0.5
        end_x = self.x + dir_x * line_length * 0.5
        end_y = self.y + dir_y * line_length * 0.5
        
        # Draw the line with a width of 2 pixels
        pygame.draw.line(
            screen,
            color,
            (int(start_x), int(start_y)),
            (int(end_x), int(end_y)),
            2
        )

