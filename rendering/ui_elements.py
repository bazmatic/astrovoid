"""UI element rendering utilities.

This module provides helper functions for rendering UI elements like
star ratings, text, and other interface components.
"""

import pygame
import math
from typing import Tuple, List, Optional, Callable
import config


class UIElementRenderer:
    """Utility class for rendering UI elements."""
    
    @staticmethod
    def draw_star_rating(
        screen: pygame.Surface,
        score_percentage: float,
        x: int,
        y: int,
        star_size: int = 18,
        star_spacing: int = 24,
        star_color_full: Tuple[int, int, int] = (255, 215, 0),
        star_color_empty: Tuple[int, int, int] = (80, 80, 80)
    ) -> None:
        """Draw 5 stars that fill/drain based on score percentage.
        
        Args:
            screen: The pygame Surface to draw on.
            score_percentage: Score as percentage (0.0 to 1.0+).
            x: X coordinate for first star.
            y: Y coordinate for stars.
            star_size: Size of each star in pixels.
            star_spacing: Spacing between stars in pixels.
            star_color_full: RGB color for filled stars.
            star_color_empty: RGB color for empty stars.
        """
        # Cap percentage at 1.0 (100%) for star display (5 stars max)
        display_percentage = min(1.0, score_percentage)
        
        for i in range(5):
            star_x = x + i * star_spacing
            
            # Each star represents 20% of the score (0-20%, 20-40%, etc.)
            star_min = i * 0.2
            star_max = (i + 1) * 0.2
            star_fill = 0.0
            
            if display_percentage >= star_max:
                # Star is completely full
                star_fill = 1.0
            elif display_percentage > star_min:
                # Star is partially filled
                star_fill = (display_percentage - star_min) / 0.2
            
            # Draw star
            UIElementRenderer._draw_star(
                screen, star_x, y, star_size, star_fill,
                star_color_full, star_color_empty
            )
    
    @staticmethod
    def _draw_star(
        screen: pygame.Surface,
        x: int,
        y: int,
        size: int,
        fill: float,
        fill_color: Tuple[int, int, int],
        empty_color: Tuple[int, int, int]
    ) -> None:
        """Draw a star with fill percentage.
        
        Args:
            screen: The pygame Surface to draw on.
            x: X coordinate of star center.
            y: Y coordinate of star center.
            size: Size of the star.
            fill: Fill percentage (0.0 to 1.0).
            fill_color: RGB color for filled portion.
            empty_color: RGB color for outline.
        """
        outer_radius = size // 2
        inner_radius = outer_radius * 0.4
        num_points = 5
        
        # Generate star points
        points = []
        for i in range(num_points * 2):
            angle = (i * math.pi) / num_points - math.pi / 2
            if i % 2 == 0:
                radius = outer_radius
            else:
                radius = inner_radius
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        # Draw star outline
        if len(points) > 2:
            pygame.draw.polygon(screen, empty_color, points, 2)
        
        # Draw filled portion
        if fill > 0.01:  # Only draw if there's meaningful fill
            if fill >= 0.99:
                # Fully filled
                pygame.draw.polygon(screen, fill_color, points)
            else:
                # Partially filled - draw with reduced opacity
                # Create a surface with alpha
                star_surface = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
                offset_points = [(p[0] - x + size * 1.5, p[1] - y + size * 1.5) for p in points]
                
                # Draw filled star with alpha based on fill percentage
                alpha = int(255 * fill)
                fill_color_alpha = (*fill_color, alpha)
                pygame.draw.polygon(star_surface, fill_color_alpha, offset_points)
                
                # Also draw a solid outline for the filled portion
                pygame.draw.polygon(star_surface, fill_color, offset_points, 1)
                
                screen.blit(star_surface, (x - size * 1.5, y - size * 1.5))
    
    @staticmethod
    def _draw_twinkling_star(
        screen: pygame.Surface,
        x: int,
        y: int,
        size: int,
        fill: float,
        fill_color: Tuple[int, int, int],
        empty_color: Tuple[int, int, int],
        twinkle_phase: float,
        scale: float = 1.0
    ) -> None:
        """Draw a star with twinkling effect.
        
        Args:
            screen: The pygame Surface to draw on.
            x: X coordinate of star center.
            y: Y coordinate of star center.
            size: Base size of the star.
            fill: Fill percentage (0.0 to 1.0).
            fill_color: RGB color for filled portion.
            empty_color: RGB color for outline.
            twinkle_phase: Phase for twinkling animation (in radians).
            scale: Scale factor for appearance animation (0.0 to 1.0).
        """
        # Calculate twinkling brightness variation
        twinkle_factor = 1.0 + config.STAR_TWINKLE_INTENSITY * math.sin(twinkle_phase)
        twinkle_factor = max(0.0, min(2.0, twinkle_factor))  # Clamp to reasonable range
        
        # Apply scale for appearance animation
        current_size = int(size * scale)
        if current_size <= 0:
            return
        
        # Adjust colors based on twinkling
        twinkled_fill = tuple(min(255, int(c * twinkle_factor)) for c in fill_color)
        twinkled_empty = tuple(min(255, int(c * (0.5 + 0.5 * twinkle_factor))) for c in empty_color)
        
        outer_radius = current_size // 2
        inner_radius = outer_radius * 0.4
        num_points = 5
        
        # Generate star points
        points = []
        for i in range(num_points * 2):
            angle = (i * math.pi) / num_points - math.pi / 2
            if i % 2 == 0:
                radius = outer_radius
            else:
                radius = inner_radius
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        # Draw star outline
        if len(points) > 2:
            pygame.draw.polygon(screen, twinkled_empty, points, 2)
        
        # Draw filled portion
        if fill > 0.01:  # Only draw if there's meaningful fill
            if fill >= 0.99:
                # Fully filled
                pygame.draw.polygon(screen, twinkled_fill, points)
            else:
                # Partially filled - draw with reduced opacity
                star_surface = pygame.Surface((current_size * 3, current_size * 3), pygame.SRCALPHA)
                offset_points = [(p[0] - x + current_size * 1.5, p[1] - y + current_size * 1.5) for p in points]
                
                # Draw filled star with alpha based on fill percentage
                alpha = int(255 * fill)
                fill_color_alpha = (*twinkled_fill, alpha)
                pygame.draw.polygon(star_surface, fill_color_alpha, offset_points)
                
                # Also draw a solid outline for the filled portion
                pygame.draw.polygon(star_surface, twinkled_fill, offset_points, 1)
                
                screen.blit(star_surface, (x - current_size * 1.5, y - current_size * 1.5))


class AnimatedStarRating:
    """Animated star rating component with sequential appearance and twinkling.
    
    Stars appear one by one with tinkling sounds, then continue twinkling.
    Designed for reuse in any UI context.
    """
    
    def __init__(
        self,
        score_percentage: float,
        x: int,
        y: int,
        star_size: int = config.LEVEL_COMPLETE_STAR_SIZE,
        star_spacing: int = None
    ):
        """Initialize animated star rating.
        
        Args:
            score_percentage: Score as percentage (0.0 to 1.0+).
            x: X coordinate for first star center.
            y: Y coordinate for stars center.
            star_size: Size of each star in pixels.
            star_spacing: Spacing between stars (defaults to star_size * 1.2).
        """
        self.score_percentage = min(1.0, score_percentage)
        self.x = x
        self.y = y
        self.star_size = star_size
        self.star_spacing = star_spacing if star_spacing is not None else int(star_size * 1.2)
        
        # Calculate number of stars earned
        self.num_stars = int(self.score_percentage * 5)
        if self.score_percentage >= 1.0:
            self.num_stars = 5
        
        # Animation state for each star
        self.star_timers: List[float] = [0.0] * 5  # Time since each star started appearing
        self.twinkle_phases: List[float] = [0.0] * 5  # Twinkling phase for each star
        self.stars_visible: List[bool] = [False] * 5  # Whether each star has appeared
        
        # Sound callback (set by game to play tinkling sounds)
        self.sound_callback: Optional[Callable[[float], None]] = None
        
        # Colors
        self.star_color_full = (255, 215, 0)  # Gold
        self.star_color_empty = (80, 80, 80)  # Dark gray
    
    def set_sound_callback(self, callback: Callable[[float], None]) -> None:
        """Set callback function to play tinkling sounds.
        
        Args:
            callback: Function that takes pitch (float) and plays sound.
        """
        self.sound_callback = callback
    
    def update(self, dt: float) -> None:
        """Update animation state.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        # Convert dt to seconds (assuming dt is normalized to 60fps)
        dt_seconds = dt / 60.0
        
        for i in range(5):
            # Calculate when this star should start appearing
            start_time = i * config.STAR_APPEAR_DURATION
            
            # Update timer
            if not self.stars_visible[i]:
                # Star hasn't appeared yet - check if it's time
                if self.star_timers[i] >= start_time:
                    # Time to appear - start animation
                    self.stars_visible[i] = True
                    # Play tinkling sound
                    if self.sound_callback and i < self.num_stars:
                        pitch = config.STAR_TINKLE_BASE_PITCH + (i * config.STAR_TINKLE_PITCH_INCREMENT)
                        self.sound_callback(pitch)
            
            # Update timer for this star
            if i < self.num_stars:
                self.star_timers[i] += dt_seconds
            else:
                # Star not earned - don't animate
                continue
            
            # Update twinkle phase for visible stars
            if self.stars_visible[i]:
                self.twinkle_phases[i] += config.STAR_TWINKLE_SPEED * dt_seconds
                if self.twinkle_phases[i] >= 2 * math.pi:
                    self.twinkle_phases[i] -= 2 * math.pi
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw animated stars.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        for i in range(5):
            star_x = self.x + i * self.star_spacing
            
            # Calculate scale for appearance animation
            if not self.stars_visible[i] or i >= self.num_stars:
                scale = 0.0
            else:
                # Calculate progress through appearance animation
                appearance_progress = min(1.0, self.star_timers[i] / config.STAR_APPEAR_DURATION)
                # Ease-out scaling
                scale = 1.0 - (1.0 - appearance_progress) ** 3
            
            # Determine if star is earned
            if i < self.num_stars:
                fill = 1.0  # Fully filled
            else:
                fill = 0.0  # Empty
            
            # Draw star with twinkling
            if scale > 0.0:
                UIElementRenderer._draw_twinkling_star(
                    screen,
                    star_x,
                    self.y,
                    self.star_size,
                    fill,
                    self.star_color_full,
                    self.star_color_empty,
                    self.twinkle_phases[i],
                    scale
                )
    
    def is_complete(self) -> bool:
        """Check if all stars have finished appearing.
        
        Returns:
            True if all earned stars have completed their appearance animation.
        """
        if self.num_stars == 0:
            return True
        
        # Check if the last star has finished appearing
        last_star_index = self.num_stars - 1
        if not self.stars_visible[last_star_index]:
            return False
        
        # Check if appearance animation is complete
        appearance_progress = self.star_timers[last_star_index] / config.STAR_APPEAR_DURATION
        return appearance_progress >= 1.0


