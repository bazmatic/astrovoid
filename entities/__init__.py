"""Game entities module.

This module contains all game entities including the base classes,
interfaces, and concrete implementations for ships, enemies, and projectiles.
"""

from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from entities.exit import ExitPortal

__all__ = ['GameEntity', 'Collidable', 'Drawable', 'ExitPortal']


