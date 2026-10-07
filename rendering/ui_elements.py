"""UI element rendering utilities.

This module provides helper functions for rendering UI elements like
star ratings, text, and other interface components.
"""

import pygame
import math
from typing import Tuple, List, Optional, Callable
import config
from rendering.fonts import get_font
from rendering.dial import draw_dial
from rendering.stars import draw_star, draw_glow, StarBurst
from rendering.number_sprite import NumberSprite


class StarIndicator:
    """Centralized star rating indicator with change detection.
    
    This class encapsulates all star-related logic including:
    - Star count calculation from score percentage
    - Change detection for audio feedback
    - Static and animated rendering
    """
    
    SCORE_THRESHOLDS = (0.20, 0.40, 0.60, 0.80, 0.95)

    @staticmethod
    def calculate_star_count(score_percentage: float) -> int:
        """Award a star only when its score threshold is reached.

        On the 100-point scale, stars require 20, 40, 60, 80 and 95 points.
        Scores below 20 earn no stars; bonuses above 100 still earn at most five.
        """
        return sum(score_percentage >= threshold for threshold in StarIndicator.SCORE_THRESHOLDS)

    def __init__(
        self,
        score_percentage: float = 0.0,
        on_star_lost: Optional[Callable[[], None]] = None,
        on_star_gained: Optional[Callable[[], None]] = None
    ):
        """Initialize star indicator.
        
        Args:
            score_percentage: Initial score percentage (0.0 to 1.0+).
            on_star_lost: Callback when a star is lost (called once per whole star lost).
            on_star_gained: Callback when a star is gained (called once per whole star gained).
        """
        self._score_percentage = min(1.0, max(0.0, score_percentage))
        self._current_star_count = StarIndicator.calculate_star_count(self._score_percentage)
        self.on_star_lost = on_star_lost
        self.on_star_gained = on_star_gained
        self._has_updated = False  # Track if update() has been called at least once
    
    def update(self, score_percentage: float) -> None:
        """Update star indicator with new score percentage.
        
        Detects whole star changes and triggers callbacks.
        Skips callbacks on the first update after initialization/reset.
        
        Args:
            score_percentage: New score percentage (0.0 to 1.0+).
        """
        new_percentage = min(1.0, max(0.0, score_percentage))
        new_star_count = StarIndicator.calculate_star_count(new_percentage)
        
        # Only trigger callbacks after the first update (to avoid false triggers on initialization)
        if self._has_updated:
            # Detect whole star changes
            if new_star_count < self._current_star_count:
                # Star(s) lost
                stars_lost = self._current_star_count - new_star_count
                if stars_lost >= 1 and self.on_star_lost:
                    self.on_star_lost()
            elif new_star_count > self._current_star_count:
                # Star(s) gained
                stars_gained = new_star_count - self._current_star_count
                if stars_gained >= 1 and self.on_star_gained:
                    self.on_star_gained()
        
        # Update state
        self._score_percentage = new_percentage
        self._current_star_count = new_star_count
        self._has_updated = True
    
    @property
    def score_percentage(self) -> float:
        """Get current score percentage."""
        return self._score_percentage
    
    @property
    def star_count(self) -> int:
        """Get current star count (0-5)."""
        return self._current_star_count
    
    def reset(self, score_percentage: float = 0.0) -> None:
        """Reset indicator to initial state.
        
        Args:
            score_percentage: Initial score percentage (0.0 to 1.0+).
        """
        self._score_percentage = min(1.0, max(0.0, score_percentage))
        self._current_star_count = StarIndicator.calculate_star_count(self._score_percentage)
        self._has_updated = False  # Reset flag so first update doesn't trigger callbacks


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
    def _calculate_percentage_color(
        percentage: float,
        high_color: Tuple[int, int, int],
        medium_color: Tuple[int, int, int],
        low_color: Tuple[int, int, int],
        high_threshold: float = 0.5,
        medium_threshold: float = 0.2
    ) -> Tuple[int, int, int]:
        """Calculate color based on percentage with thresholds.
        
        Args:
            percentage: Percentage value (0.0 to 1.0).
            high_color: Color when percentage > high_threshold.
            medium_color: Color when percentage > medium_threshold.
            low_color: Color when percentage <= medium_threshold.
            high_threshold: Threshold for high color (default 0.5).
            medium_threshold: Threshold for medium color (default 0.2).
            
        Returns:
            RGB color tuple.
        """
        if percentage > high_threshold:
            return high_color
        elif percentage > medium_threshold:
            return medium_color
        else:
            return low_color
    
    @staticmethod
    def draw_circular_gauge(
        screen: pygame.Surface,
        center_x: int,
        center_y: int,
        radius: int,
        percentage: float,
        center_text: str,
        fill_color: Tuple[int, int, int],
        text_color: Tuple[int, int, int] = (255, 255, 255),
        label_text: Optional[str] = None,
        alert: bool = False
    ) -> None:
        """Draw a circular gauge with percentage fill and center text.
        
        Args:
            screen: The pygame Surface to draw on.
            center_x: X coordinate of gauge center.
            center_y: Y coordinate of gauge center.
            radius: Radius of the gauge in pixels.
            percentage: Fill percentage (0.0 to 1.0).
            center_text: Text to display in center of gauge.
            fill_color: RGB color for the rim and the filled portion.
            text_color: RGB color for center text.
            label_text: Optional label to render below the numeric value.
            alert: Pulse the rim to warn that the value is running out.
        """
        draw_dial(
            screen, center_x, center_y, radius, percentage, center_text, fill_color,
            text_color=text_color, label_text=label_text, alert=alert
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
    """Sequential spring arrivals, landing sparks, and a quiet metallic shimmer."""

    MAX_SPARKS = 80

    def __init__(self, score_percentage: float, x: int, y: int,
                 star_size: int = config.LEVEL_COMPLETE_STAR_SIZE,
                 star_spacing: int = None, previous_stars: Optional[int] = None):
        self.score_percentage = min(1.0, max(0.0, score_percentage))
        self.x, self.y = x, y
        self.star_size = star_size
        self.star_spacing = star_spacing if star_spacing is not None else int(star_size * 1.2)
        self.num_stars = StarIndicator.calculate_star_count(self.score_percentage)
        self.previous_stars = previous_stars
        self.elapsed = 0.0
        self.sound_callback = None
        self.bursts = []
        self._landed = 0

    def set_sound_callback(self, callback: Callable[[float], None]) -> None:
        self.sound_callback = callback

    def star_scale(self, index: int) -> float:
        """Current scale of an earned star; zero before its turn."""
        if index >= self.num_stars:
            return 0.0
        progress = self.elapsed / config.STAR_APPEAR_DURATION - index
        if progress < 0:
            return 0.0
        if progress >= 1:
            return 1.0
        # A short damped spring starts at 2.6x, passes just below 1x, and
        # converges exactly to 1x at the end of the existing arrival duration.
        return 1 + 1.6 * (1 - progress) ** 3 * math.cos(progress * math.tau)

    def glow_color(self, index: int) -> Tuple[int, int, int]:
        """Newly earned record stars breathe between the title's cyan and magenta."""
        if self.previous_stars is not None and self.previous_stars <= index < self.num_stars:
            blend = round((math.sin(self.elapsed * 1.5) + 1) * 7.5) / 15
            return tuple(round(a + (b - a) * blend) for a, b in zip((45, 220, 255), (245, 65, 230)))
        return (255, 185, 45)

    @property
    def flash(self) -> float:
        if self.num_stars != 5 or self._landed < 5:
            return 0.0
        since_landing = self.elapsed - 5 * config.STAR_APPEAR_DURATION
        return max(0.0, 1 - since_landing / 0.24)

    def _burst(self, index, count, age, spread=0):
        remaining = self.MAX_SPARKS - sum(len(b.sparks) for b in self.bursts)
        burst = StarBurst(index * self.star_spacing, 0, self.star_size,
                          min(count, remaining), spread, seed=index + count)
        burst.update(age)
        if burst.alive:
            self.bursts.append(burst)

    def update(self, dt: float) -> None:
        """Advance using frame-normalized time; each landing is consumed once."""
        seconds = max(0.0, dt / 60.0)
        self.elapsed += seconds
        for burst in self.bursts:
            burst.update(seconds)
        self.bursts = [b for b in self.bursts if b.alive]
        while self._landed < self.num_stars:
            landing = (self._landed + 1) * config.STAR_APPEAR_DURATION
            if self.elapsed + 1e-9 < landing:
                break
            index = self._landed
            self._landed += 1
            if self.sound_callback:
                self.sound_callback(config.STAR_TINKLE_BASE_PITCH + index * config.STAR_TINKLE_PITCH_INCREMENT)
            self._burst(index, 12, max(0.0, self.elapsed - landing))
            if self._landed == 5:
                self._burst(2, 32, max(0.0, self.elapsed - landing), self.star_spacing * 4)

    def draw(self, screen: pygame.Surface) -> None:
        for i in range(5):
            x = self.x + i * self.star_spacing
            draw_star(screen, x, self.y, self.star_size, filled=False)
            scale = self.star_scale(i)
            if scale == 0:
                continue
            glow = 0.65 + 0.18 * math.sin(self.elapsed * 1.7 + i * 0.3)
            draw_glow(screen, x, self.y, self.star_size * 2.4, self.glow_color(i), glow)
            # The bright band sweeps across the entire row, then rests.
            sweep = (self.elapsed % 4.5) / 1.6
            band = sweep * 7 - i
            shimmer = band if 0 <= band <= 1.4 else None
            draw_star(screen, x, self.y, self.star_size * scale,
                      flash=self.flash, shimmer=shimmer)
        for burst in self.bursts:
            burst.draw(screen, (self.x, self.y))

    def is_complete(self) -> bool:
        return self._landed == self.num_stars


class GameIndicators:
    """Component for rendering game indicators (score, level, time, stars).
    
    Encapsulates all game status indicators in a reusable component.
    """
    
    def __init__(
        self,
        x: int = 20,
        y_start: int = 200,
        line_spacing: int = 60,
        font: Optional[pygame.font.Font] = None,
        level_scale: float = 0.15
    ):
        """Initialize game indicators component.
        
        Args:
            x: X coordinate for all indicators (left-aligned with consistent margin).
            y_start: Y coordinate for first indicator (level).
            line_spacing: Vertical spacing between indicators.
            font: Font to use for text rendering. If None, creates default font.
            level_scale: Scale factor for level number sprites (default 0.15).
        """
        self.x = x
        self.y_start = y_start
        self.line_spacing = line_spacing
        self.font = font if font is not None else get_font(24)
        self.number_sprite = NumberSprite()
        self.level_scale = level_scale
    
    def draw(
        self,
        screen: pygame.Surface,
        level: int,
        time_seconds: float,
        score_percentage: float
    ) -> None:
        """Draw all game indicators.
        
        Args:
            screen: The pygame Surface to draw on.
            level: Current level number.
            time_seconds: Elapsed time in seconds.
            score_percentage: Score percentage (0.0 to 1.0+) for star rating.
        """
        # Level is now shown at top of UI, so skip it here
        # Time is now drawn as a circular gauge in ship.draw_ui()
        # Stars indicator is hidden (removed)


