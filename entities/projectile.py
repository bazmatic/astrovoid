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
        is_upgraded: Whether this is an upgraded projectile (larger, faster).
        dynamic_color: Optional dynamic color for enhanced projectiles.
        enhanced_glow_intensity: Glow intensity for enhanced projectiles.
    """
    
    def __init__(
        self,
        start_pos: Tuple[float, float],
        angle: float,
        is_enemy: bool = False,
        is_upgraded: bool = False,
        enhanced_size_multiplier: float = 1.0,
        enhanced_speed_multiplier: float = 1.0,
        dynamic_color: Optional[Tuple[int, int, int]] = None,
        enhanced_glow_intensity: float = 0.4,
        impact_force_multiplier: float = 1.0,
        glow_color: Optional[Tuple[int, int, int]] = None,
        glow_radius_multiplier: float = 1.0,
        glow_intensity: float = 0.0
    ):
        """Initialize projectile at position with given angle.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            angle: Firing angle in degrees.
            is_enemy: Whether this is an enemy projectile (default: False).
            is_upgraded: Whether this is an upgraded projectile (default: False).
            enhanced_size_multiplier: Additional size multiplier for post-level-3 powerups (default: 1.0).
            enhanced_speed_multiplier: Additional speed multiplier for post-level-3 powerups (default: 1.0).
            dynamic_color: Optional dynamic color for enhanced projectiles (default: None).
            enhanced_glow_intensity: Glow intensity for enhanced projectiles (default: 0.4).
        """
        # Calculate base size and speed
        base_size = config.PROJECTILE_SIZE * config.UPGRADED_PROJECTILE_SIZE_MULTIPLIER if is_upgraded else config.PROJECTILE_SIZE
        base_speed = config.PROJECTILE_SPEED * config.UPGRADED_PROJECTILE_SPEED_MULTIPLIER if is_upgraded else config.PROJECTILE_SPEED
        
        # Apply enhanced multipliers for post-level-3 powerups
        size = base_size * enhanced_size_multiplier
        speed = base_speed * enhanced_speed_multiplier
        
        # Calculate velocity from angle
        angle_rad = angle_to_radians(angle)
        vx = math.cos(angle_rad) * speed
        vy = math.sin(angle_rad) * speed
        
        super().__init__(start_pos, size, vx, vy)
        self.angle = angle
        self.lifetime = config.PROJECTILE_LIFETIME
        self.is_enemy = is_enemy
        self.is_upgraded = is_upgraded
        self.dynamic_color = dynamic_color
        self.enhanced_glow_intensity = enhanced_glow_intensity
        self.impact_force_multiplier = impact_force_multiplier
        self.glow_color = glow_color
        self.glow_radius_multiplier = glow_radius_multiplier
        self.glow_intensity = glow_intensity
    
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
        
        # Use different color based on type, with dynamic color taking precedence
        if self.dynamic_color is not None:
            color = self.dynamic_color
        elif self.is_enemy:
            color = config.COLOR_ENEMY_PROJECTILE
        elif self.is_upgraded:
            color = config.COLOR_UPGRADED_PROJECTILE
        else:
            color = config.COLOR_PROJECTILE
        
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
        
        # Draw glowing projectiles if configured
        if self.glow_intensity > 0:
            from rendering import visual_effects
            glow_radius = max(self.radius * self.glow_radius_multiplier, self.radius * 0.5)
            glow_color = self.glow_color or color
            visual_effects.draw_glow_circle(
                screen,
                (self.x, self.y),
                self.radius,
                glow_color,
                glow_radius=glow_radius,
                intensity=self.glow_intensity
            )
        elif self.is_upgraded:
            from rendering import visual_effects
            glow_intensity = self.enhanced_glow_intensity if self.dynamic_color is not None else 0.4
            glow_radius_mult = 1.5 if self.dynamic_color is not None else 1.0
            visual_effects.draw_glow_circle(
                screen,
                (self.x, self.y),
                self.radius * 0.5,
                color,
                glow_radius=self.radius * glow_radius_mult,
                intensity=glow_intensity
            )
        
        # Draw the line with width based on upgrade status
        line_width = 3 if self.is_upgraded else 2
        pygame.draw.line(
            screen,
            color,
            (int(start_x), int(start_y)),
            (int(end_x), int(end_y)),
            line_width
        )

