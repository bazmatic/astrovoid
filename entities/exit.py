"""Exit portal entity implementation.

This module implements the ExitPortal class for the maze exit portal that the player
must reach to complete a level.
"""

import pygame
import math
from typing import Tuple, List, Optional
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from utils import circle_circle_collision, distance


class ExitPortal(GameEntity, Collidable, Drawable):
    """Represents the maze exit portal with animated swirly spiral effect.
    
    The exit portal is a stationary object that the player must reach to complete a level.
    It features an animated spiral pattern that rotates and pulses.
    
    Attributes:
        base_radius: Base radius of the exit portal (used for collision and display).
        animation_time: Internal time counter for animations.
        player_nearby: Whether the player is within attraction radius.
    """
    
    def __init__(self, pos: Tuple[float, float], radius: float):
        """Initialize exit at position.
        
        Args:
            pos: Starting position as (x, y) tuple.
            radius: Base radius of the exit.
        """
        super().__init__(pos, radius)
        self.base_radius = radius
        self.animation_time = 0.0
        self.player_nearby = False
        self.is_activated = True  # Portal is active by default
        self.previous_activated = True  # Track previous state to detect changes
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update exit animation state and check player proximity.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
            player_pos: Optional player position (x, y) to check attraction radius.
        """
        if not self.active:
            return
        
        # Update animation time (convert dt to seconds)
        dt_seconds = dt / 60.0
        self.animation_time += dt_seconds
        
        # Check if player is within attraction radius
        if player_pos is not None:
            dist = distance((self.x, self.y), player_pos)
            self.player_nearby = dist <= config.EXIT_PORTAL_ATTRACTION_RADIUS
        else:
            self.player_nearby = False
    
    def check_wall_collision(self, walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> bool:
        """Check collision with walls (exit doesn't collide with walls).
        
        Args:
            walls: List of wall line segments, each as ((x1, y1), (x2, y2)).
            
        Returns:
            Always False (exit doesn't collide with walls).
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
        # Portal doesn't work when not activated (eggs still present)
        if not self.is_activated:
            return False
        
        return circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        )
    
    def get_attraction_force(
        self,
        player_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Get attraction force vector towards the portal.
        
        Args:
            player_pos: Player position (x, y).
            
        Returns:
            Force vector (fx, fy) if player is within attraction radius, None otherwise.
        """
        if not self.active or not self.is_activated:
            return None
        
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        
        if dist > config.EXIT_PORTAL_ATTRACTION_RADIUS or dist == 0:
            return None
        
        # Normalize direction and apply force
        dir_x = dx / dist
        dir_y = dy / dist
        
        # Force strength is 0.5 of ship thruster force, decreases with distance (stronger when closer)
        base_force = config.SHIP_THRUST_FORCE * config.EXIT_PORTAL_ATTRACTION_FORCE_MULTIPLIER
        force_strength = base_force * (1.0 - dist / config.EXIT_PORTAL_ATTRACTION_RADIUS)
        
        return (dir_x * force_strength, dir_y * force_strength)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the exit with animated swirly spiral effect.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        # Animation parameters
        rotation_speed = 1.5  # Rotations per second
        pulse_speed = 2.0  # Pulse cycles per second
        num_spiral_arms = 3  # Number of spiral arms
        spiral_turns = 2.5  # Number of full turns in spiral
        
        # Calculate rotation angle
        rotation_angle = self.animation_time * rotation_speed * 2 * math.pi
        
        # Calculate pulse factor (0.8 to 1.2)
        pulse_factor = 0.8 + 0.4 * (0.5 + 0.5 * math.sin(self.animation_time * pulse_speed * 2 * math.pi))
        
        # Base radius with pulse
        base_radius = self.base_radius * pulse_factor
        
        # Increase size when player is nearby
        if self.player_nearby:
            size_multiplier = config.EXIT_PORTAL_GLOW_MULTIPLIER
        else:
            size_multiplier = 1.0
        
        base_radius *= size_multiplier
        max_radius = base_radius * 1.3
        
        # Center position
        center_x = int(self.x)
        center_y = int(self.y)
        
        # Dim visuals when not activated (eggs present)
        if not self.is_activated:
            dim_factor = 0.35  # Reduce brightness to 35%
            glow_intensity_multiplier = 0.3  # Reduce glow intensity
            base_color = tuple(int(c * dim_factor) for c in config.COLOR_EXIT)
        else:
            dim_factor = 1.0
            glow_intensity_multiplier = 1.0
            base_color = config.COLOR_EXIT
        
        # Draw outer glow layers
        for layer in range(3):
            glow_radius = max_radius + (3 - layer) * config.EXIT_PORTAL_GLOW_LAYER_OFFSET
            alpha = int(80 * (1.0 - layer / 3.0) * glow_intensity_multiplier)
            glow_color = (*base_color, alpha)
            glow_surf = pygame.Surface((glow_radius * 2 + 4, glow_radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, glow_color, 
                             (int(glow_radius) + 2, int(glow_radius) + 2), 
                             int(glow_radius))
            screen.blit(glow_surf, (center_x - int(glow_radius) - 2, center_y - int(glow_radius) - 2))
        
        # Draw spiral arms
        for arm in range(num_spiral_arms):
            arm_angle_offset = (arm * 2 * math.pi) / num_spiral_arms
            
            # Create spiral points
            spiral_points = []
            num_points = 40
            
            for i in range(num_points):
                # Progress along spiral (0 to 1)
                t = i / (num_points - 1)
                
                # Spiral radius increases from center to edge
                spiral_radius = base_radius * 0.3 + (max_radius - base_radius * 0.3) * t
                
                # Angle increases with rotation and spiral turns
                angle = rotation_angle + arm_angle_offset + t * spiral_turns * 2 * math.pi
                
                # Calculate point position
                x = center_x + spiral_radius * math.cos(angle)
                y = center_y + spiral_radius * math.sin(angle)
                
                spiral_points.append((x, y))
            
            # Draw spiral line with gradient color
            for i in range(len(spiral_points) - 1):
                # Color intensity increases from center to edge
                intensity = i / (len(spiral_points) - 1)
                
                # Interpolate between exit color and brighter version
                # Use dimmed base_color if not activated
                bright_color = (
                    min(255, base_color[0] + int(100 * dim_factor)),
                    min(255, base_color[1] + int(50 * dim_factor)),
                    min(255, base_color[2] + int(50 * dim_factor))
                )
                
                # Blend colors based on intensity
                r = int(base_color[0] * (1 - intensity) + bright_color[0] * intensity)
                g = int(base_color[1] * (1 - intensity) + bright_color[1] * intensity)
                b = int(base_color[2] * (1 - intensity) + bright_color[2] * intensity)
                
                # Line thickness increases towards edge
                thickness = max(1, int(2 + intensity * 3))
                
                pygame.draw.line(
                    screen,
                    (r, g, b),
                    (int(spiral_points[i][0]), int(spiral_points[i][1])),
                    (int(spiral_points[i + 1][0]), int(spiral_points[i + 1][1])),
                    thickness
                )
        
        # Draw central core with pulsing effect
        core_pulse = 0.7 + 0.3 * math.sin(self.animation_time * pulse_speed * 2 * math.pi)
        core_radius = base_radius * 0.4 * core_pulse
        
        # Draw core with gradient
        for i in range(3):
            radius = core_radius * (1.0 - i * 0.3)
            alpha = int((255 - i * 60) * dim_factor)
            core_color = (
                min(255, base_color[0] + int(i * 30 * dim_factor)),
                min(255, base_color[1] + int(i * 20 * dim_factor)),
                min(255, base_color[2] + int(i * 20 * dim_factor))
            )
            core_surf = pygame.Surface((int(radius * 2) + 4, int(radius * 2) + 4), pygame.SRCALPHA)
            pygame.draw.circle(core_surf, (*core_color, alpha),
                             (int(radius) + 2, int(radius) + 2),
                             int(radius))
            screen.blit(core_surf, (center_x - int(radius) - 2, center_y - int(radius) - 2))
        
        # Draw outer ring
        ring_radius = max_radius * 0.95
        ring_thickness = 2
        pygame.draw.circle(screen, base_color,
                         (center_x, center_y),
                         int(ring_radius), ring_thickness)
    
    def set_activated(self, activated: bool, sound_manager=None) -> None:
        """Set the activation state of the exit portal.
        
        When deactivated (eggs present), the portal is dimmed and non-functional.
        When activated (no eggs), the portal is fully functional.
        
        Args:
            activated: True to activate portal, False to deactivate.
            sound_manager: Optional sound manager to play activation/deactivation sounds.
        """
        # Only play sound if state actually changed
        if self.previous_activated != activated:
            if sound_manager:
                if activated:
                    sound_manager.play_portal_power_up()
                else:
                    sound_manager.play_portal_power_down()
        
        self.previous_activated = self.is_activated
        self.is_activated = activated

