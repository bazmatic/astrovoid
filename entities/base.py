"""Base game entity class.

This module provides the GameEntity base class that all game entities inherit from.
It provides common functionality for position, velocity, and basic game entity behavior.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class GameEntity(ABC):
    """Abstract base class for all game entities.
    
    Provides common properties and methods for all game entities including
    position, velocity, active state, and basic update/draw functionality.
    
    Attributes:
        x: X coordinate position.
        y: Y coordinate position.
        vx: X component of velocity.
        vy: Y component of velocity.
        radius: Collision radius of the entity.
        active: Whether the entity is currently active in the game.
    """
    
    def __init__(
        self,
        pos: Tuple[float, float],
        radius: float,
        vx: float = 0.0,
        vy: float = 0.0
    ):
        """Initialize game entity.
        
        Args:
            pos: Initial position as (x, y) tuple.
            radius: Collision radius of the entity.
            vx: Initial X velocity. Defaults to 0.0.
            vy: Initial Y velocity. Defaults to 0.0.
        """
        self.x, self.y = pos
        self.vx = vx
        self.vy = vy
        self.radius = radius
        self.active = True
    
    def get_pos(self) -> Tuple[float, float]:
        """Get the current position of the entity.
        
        Returns:
            Tuple of (x, y) coordinates.
        """
        return (self.x, self.y)
    
    def get_radius(self) -> float:
        """Get the collision radius.
        
        Returns:
            The collision radius.
        """
        return self.radius
    
    @abstractmethod
    def update(self, dt: float) -> None:
        """Update entity state.
        
        This method should be called every frame to update the entity's
        position, velocity, and other state.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        pass
    
    @abstractmethod
    def draw(self, screen: 'pygame.Surface') -> None:
        """Draw the entity on screen.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        pass


