"""UI element rendering utilities.

This module provides helper functions for rendering UI elements like
star ratings, text, and other interface components.
"""

import pygame
import math
from typing import Tuple, List, Optional, Callable, Sequence
import config
from rendering.fonts import get_font
from rendering.dial import draw_dial
from rendering.stars import draw_star, draw_glow, StarBurst


class StarIndicator:
    """Follows the five stars during play and chimes when one lights or goes out.

    The first update after construction or reset() only takes the stars in, with no chime.
    """

    def __init__(
        self,
        on_star_lost: Optional[Callable[[], None]] = None,
        on_star_gained: Optional[Callable[[], None]] = None
    ):
        self.on_star_lost = on_star_lost
        self.on_star_gained = on_star_gained
        self._flags: Tuple[bool, ...] = ()

    def update(self, flags: Sequence[bool]) -> None:
        """Take the stars as they stand now: one callback for each star that changed."""
        flags = tuple(bool(flag) for flag in flags)
        if self._flags:
            for before, now in zip(self._flags, flags):
                if before and not now and self.on_star_lost:
                    self.on_star_lost()
                elif now and not before and self.on_star_gained:
                    self.on_star_gained()
        self._flags = flags

    @property
    def flags(self) -> Tuple[bool, ...]:
        """The stars lit at the last update."""
        return self._flags

    @property
    def star_count(self) -> int:
        """How many stars were lit at the last update."""
        return sum(self._flags)

    def reset(self) -> None:
        """Forget the stars, so the next update doesn't chime."""
        self._flags = ()


class UIElementRenderer:
    """Utility class for rendering UI elements."""
    
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
    def draw_energy_gauge(
        screen: pygame.Surface,
        center_x: int,
        y: int,
        energy: float,
        value_text: str,
        label: str = "HUNTER",
        width: int = 150,
    ) -> pygame.Rect:
        """A small horizontal gauge: a label above, a bar that drains as `energy` (0.0 to 1.0) falls, and a reading.

        It belongs in the HUD, away from the ship it describes: nothing is drawn beside the hunter itself.
        Returns the bar's rectangle.
        """
        energy = max(0.0, min(1.0, energy))
        label_image = get_font(18).render(label, True, (150, 160, 195))
        screen.blit(label_image, label_image.get_rect(midbottom=(center_x, y - 4)))
        bar = pygame.Rect(0, 0, width, 10)
        bar.midtop = (center_x, y)
        pygame.draw.rect(screen, (40, 44, 70), bar)
        color = UIElementRenderer._calculate_percentage_color(
            energy, high_color=(120, 255, 90), medium_color=(255, 190, 70), low_color=(255, 90, 90))
        fill = bar.copy()
        fill.width = int(round(bar.width * energy))
        if fill.width:
            pygame.draw.rect(screen, color, fill)
        pygame.draw.rect(screen, (90, 96, 130), bar, 1)
        reading = get_font(18).render(value_text, True, (235, 242, 255))
        screen.blit(reading, reading.get_rect(midtop=(center_x, bar.bottom + 3)))
        return bar

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


class AnimatedStarRating:
    """Sequential spring arrivals, landing sparks, and a quiet metallic shimmer."""

    MAX_SPARKS = 80

    def __init__(self, earned: Sequence[bool], x: int, y: int,
                 star_size: int = config.LEVEL_COMPLETE_STAR_SIZE,
                 star_spacing: int = None, previous_stars: Optional[int] = None):
        self.earned = tuple(bool(flag) for flag in earned)
        # The earned slots, in the order their stars land
        self.slots = [i for i, flag in enumerate(self.earned) if flag]
        self.x, self.y = x, y
        self.star_size = star_size
        self.star_spacing = star_spacing if star_spacing is not None else int(star_size * 1.2)
        self.num_stars = len(self.slots)
        self.previous_stars = previous_stars
        self.elapsed = 0.0
        self.sound_callback = None
        self.bursts = []
        self._landed = 0

    def set_sound_callback(self, callback: Callable[[float], None]) -> None:
        self.sound_callback = callback

    def star_scale(self, index: int) -> float:
        """Current scale of an earned star; zero before its turn."""
        if index not in self.slots:
            return 0.0
        progress = self.elapsed / config.STAR_APPEAR_DURATION - self.slots.index(index)
        if progress < 0:
            return 0.0
        if progress >= 1:
            return 1.0
        # A short damped spring starts at 2.6x, passes just below 1x, and
        # converges exactly to 1x at the end of the existing arrival duration.
        return 1 + 1.6 * (1 - progress) ** 3 * math.cos(progress * math.tau)

    def glow_color(self, index: int) -> Tuple[int, int, int]:
        """On a record star count, every earned star breathes between the title's cyan and magenta."""
        if (self.previous_stars is not None and self.num_stars > self.previous_stars
                and index in self.slots):
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
            rank = self._landed
            index = self.slots[rank]
            self._landed += 1
            if self.sound_callback:
                self.sound_callback(config.STAR_TINKLE_BASE_PITCH + rank * config.STAR_TINKLE_PITCH_INCREMENT)
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
