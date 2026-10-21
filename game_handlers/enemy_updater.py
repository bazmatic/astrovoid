"""Enemy update handler for unified enemy update logic.

This module provides a unified interface for updating all enemy types,
eliminating code duplication in the main game loop.
"""

from game_handlers.combat_targets import nearest_friendly_pos

import math
import config
from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.flocker_enemy_ship import FlockerEnemyShip
    from entities.flighthouse_enemy import FlighthouseEnemy
    from entities.flocker_neighbor_cache import FlockerNeighborCache
    from entities.anemone import Anemone
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
    
    def update_flockers(
        self,
        flockers: List['FlockerEnemyShip'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        sound_manager: Optional['SoundManager'] = None,
        hunter=None
    ) -> None:
        """Update flocker enemy ships with optimized neighbor caching.

        Args:
            flockers: List of FlockerEnemyShip instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
            sound_manager: Sound manager for playing tweet sounds.
        """
        # Create and update shared neighbor cache for efficient flocking
        from entities.flocker_neighbor_cache import FlockerNeighborCache
        neighbor_cache = FlockerNeighborCache()
        neighbor_cache.update(flockers)

        targets = {}

        # First pass: update all flockers (this resets just_fired flags)
        for idx, flocker in enumerate(flockers):
            if not flocker.active:
                continue
            target_pos = nearest_friendly_pos(flocker, ship, hunter)
            targets[idx] = target_pos

            # Update flocker with cached neighbors for optimal performance
            flocker.update(dt, target_pos, None, neighbor_cache, idx, sound_manager)

        # Second pass: check for firing (allows neighbors to see each other's firing state)
        for idx, flocker in enumerate(flockers):
            if not flocker.active:
                continue
            target_pos = targets.get(idx)

            # Check if flocker fired a projectile
            fired_projectile = flocker.get_fired_projectile(
                target_pos, neighbor_cache, idx, flockers
            )
            if fired_projectile:
                projectiles.append(fired_projectile)

            # Check flocker-wall collision
            flocker.check_wall_collision(maze.walls, maze.spatial_grid)

            # Check flocker-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(flocker.get_pos(), flocker.radius, flocker):
                    scoring.record_enemy_collision()

    def update_flighthouses(
        self,
        flighthouses: List['FlighthouseEnemy'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        flockers: List['FlockerEnemyShip']
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
    
    def update_anemones(
        self,
        anemones: List['Anemone'],
        dt: float,
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem'
    ) -> None:
        """Update anemones: pull the ship, and sting and fling it on contact."""
        from entities.anemone import apply_pull
        
        # However many have hold of the ship, together they never pull harder
        # than one at full strength, so a straight burn can always break free
        pull_x = pull_y = 0.0
        for anemone in anemones:
            if not anemone.active:
                continue
            anemone.update(dt)
            ax, ay = anemone.reach_for(ship, maze)
            pull_x += ax
            pull_y += ay
        strength = math.hypot(pull_x, pull_y)
        peak = config.ANEMONE_PULL_THRUST_FRACTION * config.SHIP_THRUST_FORCE
        if strength > peak:
            pull_x, pull_y = pull_x / strength * peak, pull_y / strength * peak
        if strength > 0.0:
            apply_pull(ship, pull_x, pull_y)

        for anemone in anemones:
            if not anemone.active:
                continue

            # Check anemone-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(anemone.get_pos(), anemone.radius, anemone):
                    scoring.record_enemy_collision()
                    anemone.fling(ship)
