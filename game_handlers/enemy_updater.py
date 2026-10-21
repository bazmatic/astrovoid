"""Enemy update handler for unified enemy update logic.

This module provides a unified interface for updating all enemy types,
eliminating code duplication in the main game loop.
"""

from game_handlers.combat_targets import nearest_friendly_pos

import math
import config
from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.ship import Ship
    from entities.projectile import Projectile
    from entities.rotating_thruster_ship import RotatingThrusterShip
    from entities.base import GameEntity
    from maze.generator import Maze
    from scoring.system import ScoringSystem
    from entities.command_recorder import CommandRecorder
    from sounds.sound_manager import SoundManager


class EnemyUpdater:
    """Handles updating all enemy types with unified logic."""
