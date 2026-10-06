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
        death_timer: Frames left in the death animation (0.0 when not dying).
    """
    
    # Frames the death animation lasts. Subclasses that override draw_death()
    # set this above 0.0; otherwise the entity vanishes the moment it dies.
    DEATH_DURATION = 0.0
    
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
        self.death_timer = 0.0
    
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
    
    def die(self) -> None:
        """Kill the entity and start its death animation.
        
        The entity is inactive at once, so it no longer collides, acts or
        counts as alive. While is_dying is true the game keeps calling
        update_death() and draw_death() so it can play an animation.
        """
        self.active = False
        self.death_timer = float(self.DEATH_DURATION)
    
    @property
    def is_dying(self) -> bool:
        """Whether the entity is dead but still playing its death animation."""
        return not self.active and self.death_timer > 0.0
    
    @property
    def death_progress(self) -> float:
        """Progress through the death animation (0.0 just died or alive, 1.0 finished)."""
        if self.active or self.DEATH_DURATION <= 0.0:
            return 0.0
        return 1.0 - max(0.0, self.death_timer) / self.DEATH_DURATION
    
    def update_death(self, dt: float) -> None:
        """Advance the death animation. Override to animate, calling super().
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        self.death_timer = max(0.0, self.death_timer - dt)
    
    def draw_death(self, screen: 'pygame.Surface') -> None:
        """Draw the death animation. Does nothing by default.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        pass
    
    def apply_friction_and_update_position(self, friction: float, dt: float) -> None:
        """Apply friction to velocity and update position.
        
        This is a common pattern used by many entities. Extracted to avoid duplication.
        
        Args:
            friction: Friction coefficient to apply (0.0-1.0).
            dt: Delta time since last update.
        """
        self.vx *= friction
        self.vy *= friction
        self.x += self.vx * dt
        self.y += self.vy * dt
    
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




