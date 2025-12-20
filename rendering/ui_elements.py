"""UI element rendering utilities.

This module provides helper functions for rendering UI elements like
star ratings, text, and other interface components.
"""

import pygame
import math
from typing import Tuple


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


