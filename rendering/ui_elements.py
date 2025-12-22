"""UI element rendering utilities.

This module provides helper functions for rendering UI elements like
star ratings, text, and other interface components.
"""

import pygame
import math
import os
from typing import Tuple, List, Optional, Callable, Dict
import config
from rendering.number_sprite import NumberSprite


class GaugeFrame:
    """Handles loading and rendering the gauge frame template image.
    
    Loads gauge.png once and provides scaled versions for different gauge sizes.
    Follows the NumberSprite pattern for consistency.
    """
    
    def __init__(self, image_path: str = "assets/gauge.png"):
        """Initialize gauge frame loader.
        
        Args:
            image_path: Path to the gauge frame image file.
        """
        self.image_path = image_path
        self.original_image: Optional[pygame.Surface] = None
        self.scaled_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self._load_image()
    
    def _load_image(self) -> None:
        """Load the gauge frame image file."""
        try:
            if not os.path.exists(self.image_path):
                print(f"Warning: Gauge frame file not found: {self.image_path}")
                self.original_image = None
                return
            
            # Load with alpha channel preserved
            self.original_image = pygame.image.load(self.image_path).convert_alpha()
            print(f"Gauge frame loaded successfully: {self.image_path}, size: {self.original_image.get_size()}")
        except (pygame.error, FileNotFoundError) as e:
            print(f"Warning: Could not load gauge frame from {self.image_path}: {e}")
            self.original_image = None
    
    def get_scaled_frame(self, diameter: int) -> Optional[pygame.Surface]:
        """Get a scaled version of the gauge frame.
        
        Args:
            diameter: Desired diameter of the frame in pixels.
            
        Returns:
            Scaled pygame.Surface, or None if image not available.
        """
        if self.original_image is None:
            return None
        
        # Check cache first
        cache_key = (diameter, diameter)
        if cache_key in self.scaled_cache:
            return self.scaled_cache[cache_key]
        
        # Scale the image while preserving alpha channel
        # Create a new surface with alpha support and scale onto it
        scaled = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        # Use smoothscale to preserve quality and alpha
        scaled_image = pygame.transform.smoothscale(self.original_image, (diameter, diameter))
        scaled.blit(scaled_image, (0, 0))
        self.scaled_cache[cache_key] = scaled
        return scaled
    
    def is_available(self) -> bool:
        """Check if the gauge frame image is available.
        
        Returns:
            True if image is loaded, False otherwise.
        """
        return self.original_image is not None


class StarIndicator:
    """Centralized star rating indicator with change detection.
    
    This class encapsulates all star-related logic including:
    - Star count calculation from score percentage
    - Change detection for audio feedback
    - Static and animated rendering
    """
    
    @staticmethod
    def calculate_star_count(score_percentage: float) -> int:
        """Calculate star count (0-5) from score percentage.
        
        A star counts if it's at least partially filled, matching the visual representation.
        For example, 75% shows 4 stars (3 full + 1 partially filled), so returns 4.
        
        Args:
            score_percentage: Score as percentage (0.0 to 1.0+).
            
        Returns:
            Number of stars (0-5). A star counts if it's at least partially filled.
        """
        if score_percentage >= 1.0:
            return 5
        
        # Count stars that are at least partially filled
        # Use math.ceil to round up, so any partial fill counts as a full star
        # This matches the visual representation where a partially filled star is visible
        return min(5, math.ceil(score_percentage * 5))
    
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
    
    # Class-level gauge frame instance (shared across all gauges)
    _gauge_frame = None
    
    @classmethod
    def _get_gauge_frame(cls):
        """Get or create the gauge frame instance (lazy initialization)."""
        if cls._gauge_frame is None:
            cls._gauge_frame = GaugeFrame()
        return cls._gauge_frame
    
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
    def _draw_led_ring(
        screen: pygame.Surface,
        center_x: int,
        center_y: int,
        radius: int,
        percentage: float,
        color: Tuple[int, int, int],
        thickness: int
    ) -> None:
        """Draw a ring of glowing LEDs to indicate percentage.
        
        Args:
            screen: The pygame Surface to draw on.
            center_x: X coordinate of gauge center.
            center_y: Y coordinate of gauge center.
            radius: Radius of the gauge ring.
            percentage: Fill percentage (0.0 to 1.0).
            color: RGB color for the LEDs.
            thickness: Thickness of the ring (used to determine LED size).
        """
        # Use smaller radius for LED ring (closer to center)
        led_ring_radius = int(radius * 0.75)  # 75% of gauge radius
        
        # Calculate number of LEDs with spacing between them
        # Use fewer LEDs with spacing - approximately one LED per 15-20 pixels
        circumference = 2 * math.pi * led_ring_radius
        num_leds = max(12, int(circumference / 18))  # Fewer LEDs with spacing
        
        progress = num_leds * percentage
        led_size = max(2, thickness // 3)  # Smaller LEDs

        # Draw each LED with spacing and glow layers
        for i in range(num_leds):
            strength = progress - i
            if strength <= 0:
                break
            strength = min(1.0, strength)

            angle = math.radians(-90 + (i / num_leds) * 360)
            led_x = center_x + led_ring_radius * math.cos(angle)
            led_y = center_y + led_ring_radius * math.sin(angle)

            # Gradually reduce glow size and brightness as strength falls
            glow_radius = led_size + 1 + int(strength * led_size)
            glow_color = tuple(min(255, int(c + 80 * strength)) for c in color)
            pygame.draw.circle(screen, glow_color, (int(led_x), int(led_y)), glow_radius)

            core_radius = max(1, int(led_size * (0.4 + 0.6 * strength)))
            core_color = tuple(min(255, int(c * (0.6 + 0.4 * strength))) for c in color)
            pygame.draw.circle(screen, core_color, (int(led_x), int(led_y)), core_radius)

            bright_radius = max(1, int(core_radius * 0.5))
            bright_color = tuple(min(255, int(c + 100 * strength)) for c in color)
            pygame.draw.circle(screen, bright_color, (int(led_x), int(led_y)), bright_radius)
    
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
        empty_color: Tuple[int, int, int] = (50, 50, 50),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        thickness: int = 7,
        label_text: Optional[str] = None
    ) -> None:
        """Draw a circular gauge with percentage fill and center text.
        
        Args:
            screen: The pygame Surface to draw on.
            center_x: X coordinate of gauge center.
            center_y: Y coordinate of gauge center.
            radius: Radius of the gauge in pixels.
            percentage: Fill percentage (0.0 to 1.0).
            center_text: Text to display in center of gauge.
            fill_color: RGB color for filled portion.
            empty_color: RGB color for empty/background portion.
            text_color: RGB color for center text.
            thickness: Thickness of the gauge ring in pixels.
            label_text: Optional label to render above the numeric value.
        """
        # Clamp percentage
        percentage = max(0.0, min(1.0, percentage))
        
        # Get gauge frame instance
        gauge_frame = UIElementRenderer._get_gauge_frame()
        
        # Draw gauge frame image first (as background layer)
        # The frame has a transparent center, so arcs will show through
        # Make frame 50% bigger than the gauge radius
        frame_diameter = int(radius * 2 * 1.5)
        frame_image = gauge_frame.get_scaled_frame(frame_diameter)
        if frame_image is not None:
            # Draw the frame image centered at the gauge position
            frame_rect = frame_image.get_rect(center=(center_x, center_y))
            screen.blit(frame_image, frame_rect)
        else:
            # Fallback: Draw background ring (empty portion) - full circle
            pygame.draw.circle(screen, empty_color, (center_x, center_y), radius, thickness)
        
        # Draw filled arc as glowing LEDs if percentage > 0
        if percentage > 0.01:
            UIElementRenderer._draw_led_ring(
                screen,
                center_x,
                center_y,
                radius,
                percentage,
                fill_color,
                thickness
            )
        
        text_y = center_y
        if label_text:
            label_font = pygame.font.Font(None, max(12, radius // 3))
            label_surface = label_font.render(label_text, True, text_color)
            label_rect = label_surface.get_rect(center=(center_x, center_y - radius // 6))
            screen.blit(label_surface, label_rect)
            text_y = center_y + radius // 6

        if center_text:
            font_size = max(16, radius // 2 - 2)
            font = pygame.font.Font(None, font_size)
            text_surface = font.render(center_text, True, text_color)
            text_rect = text_surface.get_rect(center=(center_x, text_y))
            screen.blit(text_surface, text_rect)
    
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
        
        # Calculate number of stars earned using StarIndicator
        self.num_stars = StarIndicator.calculate_star_count(self.score_percentage)
        
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
        self.font = font if font is not None else pygame.font.Font(None, 24)
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


