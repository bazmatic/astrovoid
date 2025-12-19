"""Collidable interface for game entities.

This module defines the Collidable interface for entities that can participate
in collision detection.
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class Collidable(ABC):
    """Interface for objects that can collide with other objects.
    
    Entities implementing this interface can participate in collision detection
    with walls, other entities, and game boundaries.
    """
    
    @abstractmethod
    def get_pos(self) -> Tuple[float, float]:
        """Get the position of the collidable entity.
        
        Returns:
            Tuple of (x, y) coordinates.
        """
        pass
    
    @abstractmethod
    def get_radius(self) -> float:
        """Get the collision radius of the entity.
        
        Returns:
            The radius for collision detection.
        """
        pass
    
    @abstractmethod
    def check_wall_collision(self, walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> bool:
        """Check collision with wall segments.
        
        Args:
            walls: List of wall line segments, each as ((x1, y1), (x2, y2)).
            
        Returns:
            True if collision occurred, False otherwise.
        """
        pass
    
    @abstractmethod
    def check_circle_collision(self, other_pos: Tuple[float, float], other_radius: float) -> bool:
        """Check collision with another circular entity.
        
        Args:
            other_pos: Position of the other entity (x, y).
            other_radius: Radius of the other entity.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        pass

