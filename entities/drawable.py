"""Drawable interface for game entities.

This module defines the Drawable interface that all renderable game entities
must implement.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class Drawable(ABC):
    """Interface for objects that can be drawn on screen.
    
    All game entities that need to be rendered should implement this interface.
    This ensures a consistent drawing interface across all entities.
    """
    
    @abstractmethod
    def draw(self, screen: 'pygame.Surface') -> None:
        """Draw the entity on the given screen surface.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        pass

