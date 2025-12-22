"""Centralized renderer for game graphics.

This module provides a centralized rendering system to reduce duplication
and provide consistent rendering interfaces.
"""

import pygame
from typing import Tuple, Optional
import config
from rendering.ui_elements import UIElementRenderer


class Renderer:
    """Centralized renderer for game graphics.
    
    Provides common rendering operations to reduce code duplication
    and ensure consistent visual presentation.
    """
    
    def __init__(self, screen: pygame.Surface):
        """Initialize renderer with screen surface.
        
        Args:
            screen: The pygame Surface to render to.
        """
        self.screen = screen
    
    def clear(self) -> None:
        """Clear the screen with background color."""
        self.screen.fill(config.COLOR_BACKGROUND)
    
    def draw_text(
        self,
        text: str,
        position: Tuple[int, int],
        font: pygame.font.Font,
        color: Tuple[int, int, int] = config.COLOR_TEXT,
        center: bool = False
    ) -> None:
        """Draw text on screen.
        
        Args:
            text: Text string to render.
            position: (x, y) position or center point if center=True.
            font: Font to use for rendering.
            color: RGB color tuple. Defaults to config.COLOR_TEXT.
            center: If True, position is treated as center point.
        """
        text_surface = font.render(text, True, color)
        if center:
            text_rect = text_surface.get_rect(center=position)
            self.screen.blit(text_surface, text_rect)
        else:
            self.screen.blit(text_surface, position)
    
    def draw_star_rating(
        self,
        score_percentage: float,
        x: int,
        y: int
    ) -> None:
        """Draw 5-star rating display.
        
        Args:
            score_percentage: Score as percentage (0.0 to 1.0+).
            x: X coordinate for first star.
            y: Y coordinate for stars.
        """
        UIElementRenderer.draw_star_rating(self.screen, score_percentage, x, y)
    
    def draw_progress_bar(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        max_value: float,
        fill_color: Tuple[int, int, int],
        empty_color: Tuple[int, int, int] = (50, 50, 50),
        border_color: Optional[Tuple[int, int, int]] = None
    ) -> None:
        """Draw a progress bar.
        
        Args:
            x: X coordinate of bar.
            y: Y coordinate of bar.
            width: Width of bar in pixels.
            height: Height of bar in pixels.
            value: Current value.
            max_value: Maximum value.
            fill_color: RGB color for filled portion.
            empty_color: RGB color for empty portion.
            border_color: RGB color for border. If None, no border.
        """
        percent = max(0, min(1, value / max_value)) if max_value > 0 else 0
        
        # Background
        pygame.draw.rect(self.screen, empty_color, (x, y, width, height))
        # Filled portion
        pygame.draw.rect(self.screen, fill_color, (x, y, int(width * percent), height))
        # Border
        if border_color:
            pygame.draw.rect(self.screen, border_color, (x, y, width, height), 2)



