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
from rendering import visual_effects


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
        
        # Animation state
        self.pulse_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.is_alert = False  # Alert state for aggressive enemies
    
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
        
        # Update pulse animation
        pulse_speed = config.ENEMY_PULSE_SPEED
        if self.is_alert:
            pulse_speed *= 2.0  # Faster pulse when alert
        self.pulse_phase += pulse_speed
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
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
        """Draw the enemy on screen with enhanced visuals.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Calculate pulsing radius and color intensity
        pulse_factor = 1.0 + config.ENEMY_PULSE_AMPLITUDE * math.sin(self.pulse_phase)
        current_radius = self.radius * pulse_factor
        
        # Base color
        base_color = config.COLOR_ENEMY_STATIC if self.type == "static" else config.COLOR_ENEMY_DYNAMIC
        
        # Adjust color based on pulse and alert state
        color_intensity = 0.8 + 0.2 * (math.sin(self.pulse_phase) * 0.5 + 0.5)
        if self.is_alert:
            # Brighter and more intense when alert
            color_intensity = 1.0
            base_color = tuple(min(255, int(c * 1.3)) for c in base_color)
        
        color = tuple(int(c * color_intensity) for c in base_color)
        
        # Draw glow effect (more intense when alert)
        glow_intensity = 0.2
        if self.is_alert:
            glow_intensity = 0.5
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), current_radius, color,
            glow_radius=current_radius * 0.3, intensity=glow_intensity
        )
        
        # Draw main circle
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), int(current_radius))
        
        # Draw border (flashing when alert)
        border_color = (255, 255, 255)
        if self.is_alert:
            # Flashing border
            flash = int(255 * (math.sin(self.pulse_phase * 2) * 0.5 + 0.5))
            border_color = (flash, flash // 2, flash // 2)
        pygame.draw.circle(screen, border_color, (int(self.x), int(self.y)), int(current_radius), 2)
        
        # Type-specific visuals
        if self.type == "static":
            # Angular/spiky pattern - draw radial spikes
            num_spikes = 8
            for i in range(num_spikes):
                spike_angle = (i * 360 / num_spikes) + self.pulse_phase * 10
                spike_rad = angle_to_radians(spike_angle)
                spike_length = current_radius * 0.6
                spike_x = self.x + math.cos(spike_rad) * spike_length
                spike_y = self.y + math.sin(spike_rad) * spike_length
                pygame.draw.line(screen, (255, 150, 150),
                               (int(self.x), int(self.y)),
                               (int(spike_x), int(spike_y)), 2)
        
        elif self.type == "patrol":
            # Smooth circle with concentric pattern
            # Draw inner circle
            inner_radius = current_radius * 0.5
            pygame.draw.circle(screen, tuple(min(255, c + 30) for c in color),
                             (int(self.x), int(self.y)), int(inner_radius), 1)
            # Draw radial lines
            num_lines = 4
            for i in range(num_lines):
                line_angle = (i * 360 / num_lines) + self.pulse_phase * 20
                line_rad = angle_to_radians(line_angle)
                line_x = self.x + math.cos(line_rad) * current_radius * 0.7
                line_y = self.y + math.sin(line_rad) * current_radius * 0.7
                pygame.draw.line(screen, tuple(min(255, c + 20) for c in color),
                               (int(self.x), int(self.y)),
                               (int(line_x), int(line_y)), 1)
        
        elif self.type == "aggressive":
            # Jagged/warning appearance - draw warning stripes
            num_stripes = 6
            for i in range(num_stripes):
                stripe_angle = (i * 360 / num_stripes) + self.pulse_phase * 15
                stripe_rad = angle_to_radians(stripe_angle)
                stripe_x1 = self.x + math.cos(stripe_rad) * current_radius * 0.3
                stripe_y1 = self.y + math.sin(stripe_rad) * current_radius * 0.3
                stripe_x2 = self.x + math.cos(stripe_rad) * current_radius * 0.9
                stripe_y2 = self.y + math.sin(stripe_rad) * current_radius * 0.9
                # Alternate colors for warning effect
                if i % 2 == 0:
                    stripe_color = (255, 200, 100)
                else:
                    stripe_color = (255, 100, 50)
                pygame.draw.line(screen, stripe_color,
                               (int(stripe_x1), int(stripe_y1)),
                               (int(stripe_x2), int(stripe_y2)), 2)
        
        # Draw geometric patterns
        # Radial lines from center (all types)
        num_radial = 6
        for i in range(num_radial):
            radial_angle = (i * 360 / num_radial) + self.pulse_phase * 5
            radial_rad = angle_to_radians(radial_angle)
            radial_x = self.x + math.cos(radial_rad) * current_radius * 0.4
            radial_y = self.y + math.sin(radial_rad) * current_radius * 0.4
            pattern_color = tuple(max(0, c - 40) for c in color)
            pygame.draw.line(screen, pattern_color,
                           (int(self.x), int(self.y)),
                           (int(radial_x), int(radial_y)), 1)
        
        # Draw direction indicator for dynamic enemies
        if self.type != "static":
            angle_rad = angle_to_radians(self.angle)
            indicator_x = self.x + math.cos(angle_rad) * current_radius
            indicator_y = self.y + math.sin(angle_rad) * current_radius
            indicator_color = (255, 255, 255)
            if self.is_alert:
                indicator_color = (255, 200, 100)  # Brighter when alert
            pygame.draw.line(
                screen, indicator_color,
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

