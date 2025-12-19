"""Projectile entity implementation.

This module implements the Projectile class for weapons fired by the ship.
"""

import pygame
import math
from typing import Tuple, List
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
    """Represents a projectile fired from the ship.
    
    Attributes:
        angle: Firing angle in degrees.
        lifetime: Remaining lifetime in frames.
    """
    
    def __init__(self, start_pos: Tuple[float, float], angle: float):
        """Initialize projectile at position with given angle.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            angle: Firing angle in degrees.
        """
        # Calculate velocity from angle
        angle_rad = angle_to_radians(angle)
        vx = math.cos(angle_rad) * config.PROJECTILE_SPEED
        vy = math.sin(angle_rad) * config.PROJECTILE_SPEED
        
        super().__init__(start_pos, config.PROJECTILE_SIZE, vx, vy)
        self.angle = angle
        self.lifetime = config.PROJECTILE_LIFETIME
    
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
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> bool:
        """Check collision with walls.
        
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
                self.active = False
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
        if circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        ):
            self.active = False
            return True
        return False
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the projectile.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        pygame.draw.circle(screen, config.COLOR_PROJECTILE, (int(self.x), int(self.y)), self.radius)
        # Add a small glow effect
        pygame.draw.circle(screen, config.COLOR_PROJECTILE, (int(self.x), int(self.y)), self.radius // 2)

