"""Egg enemy that grows and spawns Replay Enemies when it pops.

This module implements an Egg enemy that grows over time and spawns 1-3
Replay Enemies when it reaches maximum size, or can be destroyed by bullets
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
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.command_recorder import CommandRecorder


class Egg(GameEntity, Collidable, Drawable):
    """Egg enemy that grows and spawns Replay Enemies when it pops.
    
    The egg grows at a random rate. When it reaches maximum size, it pops
    and spawns 1-3 Replay Enemies. If destroyed by bullets before popping,
    no Replay Enemies are spawned.
    
    Attributes:
        initial_radius: Starting size.
        current_radius: Current size (grows over time).
        max_radius: Maximum size before popping.
        growth_rate: Growth rate per frame.
        has_popped: Flag to track if egg has already popped.
        pulse_phase: Phase for pulsing animation.
    """
    
    def __init__(self, pos: Tuple[float, float]):
        """Initialize egg at position.
        
        Args:
            pos: Initial position as (x, y) tuple.
        """
        self.initial_radius = config.EGG_INITIAL_SIZE
        self.current_radius = self.initial_radius
        self.max_radius = config.EGG_MAX_SIZE
        self.growth_rate = random.uniform(
            config.EGG_GROWTH_RATE_MIN,
            config.EGG_GROWTH_RATE_MAX
        )
        self.has_popped = False
        
        super().__init__(pos, self.current_radius)
        
        # Animation state
        self.pulse_phase = random.uniform(0, 2 * math.pi)
        self.inner_phase = random.uniform(0, 2 * math.pi)  # Phase for inner movement
    
    def update(self, dt: float) -> None:
        """Update egg state.
        
        Args:
            dt: Delta time since last update.
        """
        if not self.active:
            return
        
        # Grow the egg
        self.current_radius += self.growth_rate * dt
        self.radius = self.current_radius
        
        # Update pulse animation
        self.pulse_phase += config.ENEMY_PULSE_SPEED
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
        
        # Update inner movement animation (slower, more organic)
        self.inner_phase += config.ENEMY_PULSE_SPEED * 0.3
        if self.inner_phase >= 2 * math.pi:
            self.inner_phase -= 2 * math.pi
    
    def should_pop(self) -> bool:
        """Check if egg should pop (reached maximum size).
        
        Returns:
            True if egg has reached maximum size, False otherwise.
        """
        return self.current_radius >= self.max_radius and not self.has_popped
    
    def pop(self, command_recorder: 'CommandRecorder', replay_enemies: List['ReplayEnemyShip']) -> None:
        """Pop the egg and spawn Replay Enemies.
        
        Args:
            command_recorder: CommandRecorder instance for spawning Replay Enemies.
            replay_enemies: List to add spawned Replay Enemies to.
        """
        if self.has_popped:
            return
        
        self.has_popped = True
        
        # Spawn 1-3 Replay Enemies
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
            
            # Create new ReplayEnemyShip
            from entities.replay_enemy_ship import ReplayEnemyShip
            spawned_enemy = ReplayEnemyShip((spawn_x, spawn_y), command_recorder)
            spawned_enemy.current_replay_index = 0
            replay_enemies.append(spawned_enemy)
        
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
        """Check collision with wall segments.
        
        Args:
            walls: List of wall segments.
            spatial_grid: Optional spatial grid for optimized collision detection.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        # Eggs are stationary, so wall collision is not critical
        # But we implement it for consistency with other entities
        walls_to_check = walls
        if spatial_grid is not None:
            walls_to_check = spatial_grid.get_nearby_walls(
                (self.x, self.y), self.radius * 2.0
            )
        
        for wall in walls_to_check:
            if hasattr(wall, 'get_segment'):
                if not wall.active:
                    continue
                segment = wall.get_segment()
            else:
                segment = wall
            
            if circle_line_collision(
                (self.x, self.y), self.radius,
                segment[0], segment[1]
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
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the egg on screen as a spherical, shiny, translucent water droplet.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Check if egg is on screen
        screen_margin = 100
        if (self.x < -screen_margin or self.x > config.SCREEN_WIDTH + screen_margin or
            self.y < -screen_margin or self.y > config.SCREEN_HEIGHT + screen_margin):
            return
        
        # Calculate growth progress (0.0 to 1.0)
        growth_progress = (self.current_radius - self.initial_radius) / (
            self.max_radius - self.initial_radius
        )
        growth_progress = max(0.0, min(1.0, growth_progress))
        
        # Calculate pulsing effect
        sin_pulse = math.sin(self.pulse_phase)
        pulse_factor = 1.0 + config.ENEMY_PULSE_AMPLITUDE * sin_pulse
        current_radius = int(self.current_radius * pulse_factor)
        
        # Create translucent surface for the egg
        egg_surface = pygame.Surface((current_radius * 2 + 10, current_radius * 2 + 10), pygame.SRCALPHA)
        center_x = current_radius + 5
        center_y = current_radius + 5
        
        # Base color - water droplet blue/cyan with transparency
        base_color = (150, 200, 255)  # Light blue/cyan
        alpha = 180  # Translucent (0-255)
        
        # Draw outer glow (subtle, like light refraction)
        glow_radius = int(current_radius * 1.15)
        for i in range(3):
            glow_alpha = int(alpha * 0.2 * (1.0 - i / 3.0))
            glow_color = (*base_color, glow_alpha)
            glow_size = int(glow_radius * (1.0 + i * 0.1))
            pygame.draw.circle(egg_surface, glow_color, (center_x, center_y), glow_size)
        
        # Draw main spherical droplet (translucent)
        droplet_color = (*base_color, alpha)
        pygame.draw.circle(egg_surface, droplet_color, (center_x, center_y), current_radius)
        
        # Draw inner content - something moving inside
        inner_radius = int(current_radius * 0.6)
        inner_x = center_x + math.cos(self.inner_phase) * (current_radius * 0.2)
        inner_y = center_y + math.sin(self.inner_phase * 1.3) * (current_radius * 0.15)
        
        # Draw multiple small shapes moving inside (like a creature or particles)
        inner_color = (100, 150, 200, 200)  # Slightly darker, more opaque
        num_inner_shapes = 3
        for i in range(num_inner_shapes):
            shape_phase = self.inner_phase + (i * 2 * math.pi / num_inner_shapes)
            shape_x = inner_x + math.cos(shape_phase) * (inner_radius * 0.3)
            shape_y = inner_y + math.sin(shape_phase) * (inner_radius * 0.3)
            shape_size = int(inner_radius * 0.15)
            pygame.draw.circle(egg_surface, inner_color, (int(shape_x), int(shape_y)), shape_size)
        
        # Draw highlight (shiny reflection like water droplet)
        highlight_offset = current_radius * 0.3
        highlight_x = center_x - highlight_offset
        highlight_y = center_y - highlight_offset
        highlight_size = int(current_radius * 0.4)
        highlight_color = (255, 255, 255, 120)  # White highlight, semi-transparent
        pygame.draw.circle(egg_surface, highlight_color, (int(highlight_x), int(highlight_y)), highlight_size)
        
        # Draw smaller bright highlight
        small_highlight_size = int(current_radius * 0.15)
        small_highlight_color = (255, 255, 255, 180)
        pygame.draw.circle(egg_surface, small_highlight_color, 
                          (int(highlight_x), int(highlight_y)), small_highlight_size)
        
        # Draw border (subtle outline)
        border_color = (200, 220, 255, 150)  # Light border, semi-transparent
        pygame.draw.circle(egg_surface, border_color, (center_x, center_y), current_radius, 2)
        
        # Show stress when close to popping
        if growth_progress > 0.7:
            stress_alpha = int(255 * (sin_pulse * 0.5 + 0.5) * (growth_progress - 0.7) / 0.3)
            stress_color = (255, 100, 100, stress_alpha)
            # Draw stress lines
            num_stress_lines = 4
            for i in range(num_stress_lines):
                stress_angle = (i * 360 / num_stress_lines) + self.pulse_phase * 15
                stress_rad = math.radians(stress_angle)
                stress_length = current_radius * 0.5
                stress_x1 = center_x + math.cos(stress_rad) * (current_radius * 0.3)
                stress_y1 = center_y + math.sin(stress_rad) * (current_radius * 0.3)
                stress_x2 = center_x + math.cos(stress_rad) * stress_length
                stress_y2 = center_y + math.sin(stress_rad) * stress_length
                pygame.draw.line(egg_surface, stress_color,
                               (int(stress_x1), int(stress_y1)),
                               (int(stress_x2), int(stress_y2)), 2)
        
        # Blit the translucent egg surface onto the screen
        screen.blit(egg_surface, (int(self.x - center_x), int(self.y - center_y)))

