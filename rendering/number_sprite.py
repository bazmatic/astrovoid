"""Number sprite rendering utility.

This module provides functionality to load and render numbers using individual
digit image files (digit_0.png through digit_9.png).
"""

import pygame
from typing import Tuple, Dict, Optional
import os


class NumberSprite:
    """Handles loading and rendering numbers from individual digit files."""
    
    def __init__(self, digit_path_prefix: str = "assets/digit_"):
        """Initialize number sprite loader.
        
        Args:
            digit_path_prefix: Path prefix for digit files (e.g., "assets/digit_")
                              Files should be named digit_0.png, digit_1.png, etc.
        """
        self.digit_path_prefix = digit_path_prefix
        self.digit_sprites: Dict[int, Optional[pygame.Surface]] = {}
        self._load_digit_files()
    
    def _load_digit_files(self) -> None:
        """Load all individual digit files."""
        for digit in range(10):
            digit_path = f"{self.digit_path_prefix}{digit}.png"
            try:
                if not os.path.exists(digit_path):
                    print(f"Warning: Digit file not found: {digit_path}")
                    self.digit_sprites[digit] = None
                    continue
                
                digit_surface = pygame.image.load(digit_path).convert_alpha()
                self.digit_sprites[digit] = digit_surface
            except (pygame.error, FileNotFoundError) as e:
                print(f"Warning: Could not load digit {digit} from {digit_path}: {e}")
                self.digit_sprites[digit] = None
    
    def get_digit_sprite(self, digit: int) -> Optional[pygame.Surface]:
        """Get cached sprite for a single digit.
        
        Args:
            digit: Digit to get (0-9).
            
        Returns:
            pygame.Surface for the digit, or None if not available.
        """
        if digit < 0 or digit > 9:
            return None
        return self.digit_sprites.get(digit)
    
    def render_number(
        self,
        number: int,
        scale: float = 1.0
    ) -> Optional[pygame.Surface]:
        """Compose and return a surface with the full number.
        
        Args:
            number: Number to render (non-negative integer).
            scale: Scale factor for the rendered number (1.0 = original size).
            
        Returns:
            pygame.Surface with the composed number, or None if rendering fails.
        """
        if number < 0:
            return None
        
        # Convert number to string to get individual digits
        number_str = str(number)
        if not number_str:
            return None
        
        # Collect digit sprites
        digit_surfaces = []
        total_width = 0
        max_height = 0
        
        for char in number_str:
            digit = int(char)
            digit_sprite = self.get_digit_sprite(digit)
            if digit_sprite is None:
                # If any digit is missing, return None
                return None
            digit_surfaces.append(digit_sprite)
            total_width += digit_sprite.get_width()
            max_height = max(max_height, digit_sprite.get_height())
        
        if not digit_surfaces:
            return None
        
        # Create composite surface
        composite = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        composite.fill((0, 0, 0, 0))  # Transparent background
        
        # Blit all digits horizontally
        x_offset = 0
        for digit_surface in digit_surfaces:
            composite.blit(digit_surface, (x_offset, 0))
            x_offset += digit_surface.get_width()
        
        # Scale if needed
        if scale != 1.0:
            new_width = int(total_width * scale)
            new_height = int(max_height * scale)
            composite = pygame.transform.scale(composite, (new_width, new_height))
        
        return composite
    
    def draw_number(
        self,
        screen: pygame.Surface,
        number: int,
        position: Tuple[int, int],
        scale: float = 1.0,
        center: bool = False
    ) -> bool:
        """Draw number directly to screen.
        
        Args:
            screen: The pygame Surface to draw on.
            number: Number to render (non-negative integer).
            position: (x, y) position or center point if center=True.
            scale: Scale factor for the rendered number (1.0 = original size).
            center: If True, position is treated as center point.
            
        Returns:
            True if number was drawn successfully, False otherwise.
        """
        number_surface = self.render_number(number, scale)
        if number_surface is None:
            return False
        
        if center:
            number_rect = number_surface.get_rect(center=position)
            screen.blit(number_surface, number_rect)
        else:
            screen.blit(number_surface, position)
        
        return True
