"""Wall segment implementation.

This module provides the WallSegment class for representing destructible wall segments
with hit points tracking.
"""

from typing import Tuple


class WallSegment:
    """Represents a single wall segment with hit points.
    
    Attributes:
        start: Start point of the wall segment (x, y).
        end: End point of the wall segment (x, y).
        hit_points: Current hit points remaining.
        active: Whether the wall segment is still active (not destroyed).
    """
    
    def __init__(self, start: Tuple[float, float], end: Tuple[float, float], hit_points: int):
        """Initialize wall segment.
        
        Args:
            start: Start point of the wall segment (x, y).
            end: End point of the wall segment (x, y).
            hit_points: Initial hit points for the wall segment.
        """
        self.start = start
        self.end = end
        self.hit_points = hit_points
        self.active = True
    
    def damage(self) -> bool:
        """Damage the wall segment by reducing hit points.
        
        Returns:
            True if wall was destroyed (hit points reached 0), False otherwise.
        """
        self.hit_points -= 1
        if self.hit_points <= 0:
            self.active = False
            return True
        return False
    
    def get_segment(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get the wall segment as a tuple for collision detection.
        
        Returns:
            Tuple of (start, end) points for backward compatibility.
        """
        return (self.start, self.end)
    
    def __eq__(self, other) -> bool:
        """Equality comparison for set operations.
        
        Args:
            other: Another WallSegment or tuple to compare with.
            
        Returns:
            True if segments are equal, False otherwise.
        """
        if isinstance(other, WallSegment):
            return self.start == other.start and self.end == other.end
        elif isinstance(other, tuple) and len(other) == 2:
            return self.start == other[0] and self.end == other[1]
        return False
    
    def __hash__(self) -> int:
        """Hash for set operations.
        
        Returns:
            Hash value based on start and end points.
        """
        return hash((self.start, self.end))

