"""Enemy update handler for unified enemy update logic.

This module provides a unified interface for updating all enemy types,
eliminating code duplication in the main game loop.
"""

from game_handlers.combat_targets import nearest_friendly_pos

import math
import config
from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.flighthouse_enemy import FlighthouseEnemy
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
    
    def update_flighthouses(
        self,
        flighthouses: List['FlighthouseEnemy'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        flockers: List
    ) -> None:
        """Update flighthouse enemies and append any spawned flockers."""
        for flighthouse in flighthouses:
            if not flighthouse.active:
                continue

            spawned = flighthouse.update(dt, player_pos, maze.walls, maze.spatial_grid, maze.gate_segments)
            if spawned:
                flockers.extend(spawned)

            # Check flighthouse-wall collision (ignored; remains stationary)
            flighthouse.check_wall_collision(maze.walls, maze.spatial_grid)

            # Check flighthouse-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(flighthouse.get_pos(), flighthouse.radius, flighthouse):
                    scoring.record_enemy_collision()
