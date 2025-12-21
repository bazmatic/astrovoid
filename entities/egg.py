"""Egg enemy that grows and spawns Baby enemies when it pops.

This module implements an Egg enemy that grows over time and spawns 1-3
Baby enemies when it reaches maximum size, or can be destroyed by bullets
to prevent spawning.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional, TYPE_CHECKING
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from utils import circle_line_collision, circle_circle_collision
from rendering import visual_effects

if TYPE_CHECKING:
    from entities.baby import Baby
    from entities.command_recorder import CommandRecorder


class Egg(GameEntity, Collidable, Drawable):
    """Egg enemy that grows and spawns Baby enemies when it pops.
    
    The egg grows at a random rate. When it reaches maximum size, it pops
    and spawns 1-3 Baby enemies. If destroyed by bullets before popping,
    no Baby enemies are spawned.
    
    Attributes:
        initial_radius: Starting size.
        current_radius: Current size (grows over time).
        max_radius: Maximum size before popping.
        growth_rate: Growth rate per frame.
        has_popped: Flag to track if egg has already popped.
        pulse_phase: Phase for pulsing animation.
    """
    
    def __init__(self, pos: Tuple[float, float]):
        """
        Initialize egg enemy.
        
        Args:
            pos: Starting position as (x, y) tuple.
        """
        # Initialize with initial size
        initial_radius = config.EGG_INITIAL_SIZE
        super().__init__(pos, initial_radius, 0.0, 0.0)
        
        self.initial_radius = initial_radius
        self.current_radius = float(initial_radius)
        self.max_radius = config.EGG_MAX_SIZE
        # Random growth rate between min and max
        self.growth_rate = random.uniform(
            config.EGG_GROWTH_RATE_MIN,
            config.EGG_GROWTH_RATE_MAX
        )
        self.has_popped = False
        self.pulse_phase = 0.0
    
    def update(self, dt: float) -> None:
        """Update egg growth and animation.
        
        Args:
            dt: Delta time since last update.
        """
        if not self.active or self.has_popped:
            return
        
        # Grow the egg
        self.current_radius += self.growth_rate
        self.radius = self.current_radius
        
        # Update pulse phase for animation
        self.pulse_phase += dt * 2.0
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
    def should_pop(self) -> bool:
        """Check if egg should pop (reached maximum size).
        
        Returns:
            True if egg has reached maximum size, False otherwise.
        """
        return self.current_radius >= self.max_radius and not self.has_popped
    
    def pop(self, command_recorder: 'CommandRecorder', babies: List['Baby']) -> None:
        """Pop the egg and spawn Baby enemies.
        
        Args:
            command_recorder: CommandRecorder instance for spawning Baby enemies.
            babies: List to add spawned Baby enemies to.
        """
        if self.has_popped:
            return
        
        self.has_popped = True
        
        # Spawn 1-3 Baby enemies
        spawn_count = random.randint(1, 3)
        
        for i in range(spawn_count):
            # Random offset within spawn range
            angle_offset = random.uniform(0, 2 * math.pi)
            distance_offset = random.uniform(
                config.EGG_SPAWN_OFFSET_RANGE * 0.5,
                config.EGG_SPAWN_OFFSET_RANGE
            )
            spawn_x = self.x + math.cos(angle_offset) * distance_offset
            spawn_y = self.y + math.sin(angle_offset) * distance_offset
            
            # Create new Baby enemy
            from entities.baby import Baby
            spawned_baby = Baby((spawn_x, spawn_y), command_recorder)
            spawned_baby.current_replay_index = 0
            babies.append(spawned_baby)
        
        # Deactivate egg after popping
        self.active = False
    
    def destroy(self) -> None:
        """Destroy the egg (called when hit by bullet)."""
        self.active = False
    
    def check_wall_collision(
        self,
        walls: List,
        spatial_grid=None
    ) -> bool:
        """Check collision with walls (eggs are stationary, so this is mostly for consistency).
        
        Args:
            walls: List of wall segments.
            spatial_grid: Optional spatial grid (unused for eggs).
            
        Returns:
            False (eggs don't collide with walls).
        """
        # Eggs are stationary and don't need wall collision
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
            self.get_pos(), self.radius,
            other_pos, other_radius
        )
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the egg as a translucent, spherical water droplet.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Calculate growth progress for visual effects
        growth_progress = (self.current_radius - self.initial_radius) / (self.max_radius - self.initial_radius)
        growth_progress = max(0.0, min(1.0, growth_progress))
        
        # Base color (light blue/cyan)
        color = config.COLOR_EGG
        
        # Draw main circle with transparency
        egg_surface = pygame.Surface((int(self.current_radius * 2), int(self.current_radius * 2)), pygame.SRCALPHA)
        pygame.draw.circle(egg_surface, (color[0], color[1], color[2], 180), (int(self.current_radius), int(self.current_radius)), int(self.current_radius))
        screen.blit(egg_surface, (int(self.x - self.current_radius), int(self.y - self.current_radius)))
        
        # Draw shiny highlight
        highlight_radius = self.current_radius * 0.4
        highlight_pos_x = self.x + math.cos(self.pulse_phase * 0.7) * self.current_radius * 0.3
        highlight_pos_y = self.y + math.sin(self.pulse_phase * 0.7) * self.current_radius * 0.3
        visual_effects.draw_glow_circle(screen, (highlight_pos_x, highlight_pos_y), highlight_radius, (255, 255, 255), glow_radius=highlight_radius * 0.5, intensity=0.8)
        
        # Draw inner moving shapes
        num_inner_shapes = 3
        inner_radius_base = self.current_radius * 0.3
        for i in range(num_inner_shapes):
            inner_angle = (self.pulse_phase * 5 + i * math.pi * 2 / num_inner_shapes) % (2 * math.pi)
            inner_x = self.x + math.cos(inner_angle) * inner_radius_base * (0.8 + 0.2 * math.sin(self.pulse_phase * 3 + i))
            inner_y = self.y + math.sin(inner_angle) * inner_radius_base * (0.8 + 0.2 * math.cos(self.pulse_phase * 3 + i))
            inner_size = max(1, int(self.current_radius * 0.1 * (0.8 + 0.2 * math.sin(self.pulse_phase * 4 + i))))
            # Use RGB color (no alpha) for pygame.draw.circle
            inner_color = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50))
            pygame.draw.circle(screen, inner_color, (int(inner_x), int(inner_y)), inner_size)
        
        # Draw stress lines when close to popping
        if growth_progress > 0.7:
            num_cracks = 4
            for i in range(num_cracks):
                crack_angle = (i * 360 / num_cracks) + self.pulse_phase * 10
                crack_rad = math.radians(crack_angle)
                crack_length = self.current_radius * (0.5 + 0.4 * (growth_progress - 0.7) / 0.3)
                crack_x = self.x + math.cos(crack_rad) * crack_length
                crack_y = self.y + math.sin(crack_rad) * crack_length
                pygame.draw.line(
                    screen, (255, 100, 50),
                    (int(self.x + math.cos(crack_rad) * self.current_radius * 0.3), int(self.y + math.sin(crack_rad) * self.current_radius * 0.3)),
                    (int(crack_x), int(crack_y)), 1
                )
