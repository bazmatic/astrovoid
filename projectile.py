"""Projectile system for weapons."""

import pygame
import math
from typing import Tuple
import config
import utils


class Projectile:
    """Represents a projectile fired from the ship."""
    
    def __init__(self, start_pos: Tuple[float, float], angle: float):
        """Initialize projectile at position with given angle."""
        self.x, self.y = start_pos
        self.angle = angle
        
        # Calculate velocity from angle
        angle_rad = utils.angle_to_radians(angle)
        self.vx = math.cos(angle_rad) * config.PROJECTILE_SPEED
        self.vy = math.sin(angle_rad) * config.PROJECTILE_SPEED
        
        self.lifetime = config.PROJECTILE_LIFETIME
        self.active = True
        self.radius = config.PROJECTILE_SIZE
    
    def update(self, dt: float) -> None:
        """Update projectile position and lifetime."""
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
    
    def check_wall_collision(self, walls: list) -> bool:
        """Check collision with walls. Returns True if collision occurred."""
        for wall in walls:
            if utils.circle_line_collision(
                (self.x, self.y), self.radius,
                wall[0], wall[1]
            ):
                self.active = False
                return True
        return False
    
    def check_enemy_collision(self, enemy_pos: Tuple[float, float], enemy_radius: float) -> bool:
        """Check collision with enemy. Returns True if collision occurred."""
        if utils.circle_circle_collision(
            (self.x, self.y), self.radius,
            enemy_pos, enemy_radius
        ):
            self.active = False
            return True
        return False
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the projectile."""
        if not self.active:
            return
        
        pygame.draw.circle(screen, config.COLOR_PROJECTILE, (int(self.x), int(self.y)), self.radius)
        # Add a small glow effect
        pygame.draw.circle(screen, config.COLOR_PROJECTILE, (int(self.x), int(self.y)), self.radius // 2)

