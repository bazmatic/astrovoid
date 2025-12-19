"""Backward compatibility wrapper for Enemy.

This module provides backward compatibility by re-exporting Enemy from the new location.
"""

from entities.enemy import Enemy, create_enemies

__all__ = ['Enemy', 'create_enemies']
