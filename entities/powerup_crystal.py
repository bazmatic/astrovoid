"""Powerup crystal entity implementation.

This module implements the PowerupCrystal class for collectible powerup items
that drop from destroyed enemies.
"""

import pygame
import math
from typing import Tuple
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from rendering import visual_effects
from utils import circle_circle_collision


class PowerupCrystal(GameEntity, Collidable, Drawable):
    """Represents a collectible powerup crystal that upgrades the player's guns.
    
    Attributes:
        rotation_angle: Current rotation angle in degrees.
        pulse_phase: Phase for pulsing animation (in radians).
    """
    
    def __init__(self, pos: Tuple[float, float]):
        """Initialize powerup crystal at position.
        
        Args:
            pos: Starting position as (x, y) tuple.
        """
        super().__init__(pos, config.POWERUP_CRYSTAL_SIZE)
        self.rotation_angle = 0.0
        self.pulse_phase = 0.0
    
    def update(self, dt: float) -> None:
        """Update crystal rotation and animation.
        
        Args:
            dt: Delta time since last update.
        """
        if not self.active:
            return
        
        # Rotate crystal
        self.rotation_angle += config.POWERUP_CRYSTAL_ROTATION_SPEED * dt
        if self.rotation_angle >= 360.0:
            self.rotation_angle -= 360.0
        
        # Update pulse animation
        self.pulse_phase += 0.1 * dt
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
    def check_wall_collision(self, walls: list, spatial_grid=None) -> bool:
        """Check collision with walls (crystals don't collide with walls).
        
        Args:
            walls: List of wall segments (unused).
            spatial_grid: Optional spatial grid (unused).
            
        Returns:
            Always False (crystals don't collide with walls).
        """
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float
    ) -> bool:
        """Check collision with another circular entity (ship).
        
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
        """Draw the crystal with rotation and glow effects.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Calculate pulse size (varies between 0.8x and 1.2x)
        pulse_factor = 0.8 + 0.4 * (1.0 + math.sin(self.pulse_phase)) / 2.0
        current_radius = self.radius * pulse_factor
        
        # Calculate glow intensity (pulses)
        glow_intensity = config.POWERUP_CRYSTAL_GLOW_INTENSITY * (0.7 + 0.3 * math.sin(self.pulse_phase * 2))
        
        # Draw glow effect
        visual_effects.draw_glow_circle(
            screen,
            (self.x, self.y),
            current_radius,
            config.COLOR_POWERUP_CRYSTAL,
            glow_radius=current_radius * 1.5,
            intensity=glow_intensity
        )
        
        # Draw crystal shape (diamond/octagon)
        angle_rad = math.radians(self.rotation_angle)
        num_points = 8
        vertices = []
        
        for i in range(num_points):
            point_angle = angle_rad + (2 * math.pi * i / num_points)
            px = self.x + math.cos(point_angle) * current_radius
            py = self.y + math.sin(point_angle) * current_radius
            vertices.append((px, py))
        
        # Draw filled crystal
        pygame.draw.polygon(screen, config.COLOR_POWERUP_CRYSTAL, vertices)
        
        # Draw outline
        pygame.draw.polygon(screen, (255, 255, 255), vertices, 2)
        
        # Draw inner highlight
        inner_radius = current_radius * 0.5
        inner_vertices = []
        for i in range(num_points):
            point_angle = angle_rad + (2 * math.pi * i / num_points)
            px = self.x + math.cos(point_angle) * inner_radius
            py = self.y + math.sin(point_angle) * inner_radius
            inner_vertices.append((px, py))
        pygame.draw.polygon(screen, (200, 150, 255), inner_vertices)

