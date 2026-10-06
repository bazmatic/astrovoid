"""Enemy update handler for unified enemy update logic.

This module provides a unified interface for updating all enemy types,
eliminating code duplication in the main game loop.
"""

from game_handlers.combat_targets import nearest_friendly

from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.flocker_enemy_ship import FlockerEnemyShip
    from entities.flighthouse_enemy import FlighthouseEnemy
    from entities.flocker_neighbor_cache import FlockerNeighborCache
    from entities.split_boss import SplitBoss
    from entities.mother_boss import MotherBoss
    from entities.baby import Baby
    from entities.egg import Egg
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
    
    def update_enemies(
        self,
        enemies: List['Enemy'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        hunter=None
    ) -> None:
        """Update regular enemies.
        
        Args:
            enemies: List of Enemy instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
        """
        for enemy in enemies:
            if not enemy.active:
                continue
            target = nearest_friendly(enemy, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
            
            enemy.update(dt, target_pos, maze.walls)
            
            # Check enemy-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(enemy.get_pos(), enemy.radius, enemy):
                    scoring.record_enemy_collision()
            
            # Check if enemy fired a projectile
            fired_projectile = enemy.get_fired_projectile(target_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
    def update_replay_enemies(
        self,
        replay_enemies: List['ReplayEnemyShip'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        hunter=None
    ) -> None:
        """Update replay enemy ships.
        
        Args:
            replay_enemies: List of ReplayEnemyShip instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
        """
        for replay_enemy in replay_enemies:
            if not replay_enemy.active:
                continue
            target = nearest_friendly(replay_enemy, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
            
            replay_enemy.update(dt, target_pos)
            
            # Check replay enemy-wall collision
            # This uses the replay enemy's own state and is completely independent
            # from the player ship's collisions.
            wall_collision = replay_enemy.check_wall_collision(maze.walls, maze.spatial_grid)
            if wall_collision:
                replay_enemy.trigger_blink()
            
            # Check replay enemy-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(replay_enemy.get_pos(), replay_enemy.radius, replay_enemy):
                    scoring.record_enemy_collision()
                    replay_enemy.trigger_blink()
            
            # Check if replay enemy fired a projectile
            fired_projectile = replay_enemy.get_fired_projectile(target_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
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
            target = nearest_friendly(flocker, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
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

            spawned = flighthouse.update(dt, player_pos, maze.walls, maze.spatial_grid)
            if spawned:
                flockers.extend(spawned)

            # Check flighthouse-wall collision (ignored; remains stationary)
            flighthouse.check_wall_collision(maze.walls, maze.spatial_grid)

            # Check flighthouse-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(flighthouse.get_pos(), flighthouse.radius, flighthouse):
                    scoring.record_enemy_collision()
    
    def update_split_bosses(
        self,
        split_bosses: List['SplitBoss'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        hunter=None
    ) -> None:
        """Update SplitBoss enemies.
        
        Args:
            split_bosses: List of SplitBoss instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
        """
        for split_boss in split_bosses:
            if not split_boss.active:
                continue
            target = nearest_friendly(split_boss, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
            
            split_boss.update(dt, target_pos)
            
            # Check SplitBoss-wall collision
            split_boss.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check SplitBoss-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(split_boss.get_pos(), split_boss.radius, split_boss):
                    scoring.record_enemy_collision()
            
            # Check if SplitBoss fired a projectile
            fired_projectile = split_boss.get_fired_projectile(target_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
    def update_babies(
        self,
        babies: List['Baby'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        hunter=None
    ) -> None:
        """Update Baby enemies.
        
        Args:
            babies: List of Baby instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
        """
        for baby in babies:
            if not baby.active:
                continue
            target = nearest_friendly(baby, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
            
            baby.update(dt, target_pos)
            
            # Check baby-wall collision
            baby.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check baby-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(baby.get_pos(), baby.radius, baby):
                    scoring.record_enemy_collision()
            
            # Check if baby fired a projectile
            fired_projectile = baby.get_fired_projectile(target_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
    def update_eggs(
        self,
        eggs: List['Egg'],
        dt: float,
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        command_recorder: 'CommandRecorder',
        babies: List['Baby']
    ) -> None:
        """Update egg enemies.
        
        Args:
            eggs: List of Egg instances.
            dt: Delta time since last update.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            command_recorder: Command recorder for spawning Baby enemies.
            babies: List to add spawned Baby enemies to.
        """
        for egg in eggs:
            if not egg.active:
                continue
            
            egg.update(dt)
            
            # Check if egg should pop
            if egg.should_pop():
                egg.pop(command_recorder, babies)
                continue
            
            # Check egg-wall collision (eggs are stationary, but check for consistency)
            egg.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check egg-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(egg.get_pos(), egg.radius, egg):
                    scoring.record_enemy_collision()
    
    def update_mother_bosses(
        self,
        mother_bosses: List['MotherBoss'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile'],
        eggs: List['Egg'],
        hunter=None
    ) -> None:
        """Update Mother Boss enemies.
        
        Args:
            mother_bosses: List of MotherBoss instances.
            dt: Delta time since last update.
            player_pos: Current player position.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            projectiles: List to add fired projectiles to.
            eggs: List to add laid eggs to.
        """
        for mother_boss in mother_bosses:
            if not mother_boss.active:
                continue
            target = nearest_friendly(mother_boss, ship, hunter)
            target_pos = target.get_pos() if target is not None else None
            
            mother_boss.update(dt, target_pos)
            
            # Try to lay an egg
            mother_boss.lay_egg(eggs)
            
            # Check Mother Boss-wall collision
            mother_boss.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check Mother Boss-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(mother_boss.get_pos(), mother_boss.radius, mother_boss):
                    scoring.record_enemy_collision()
            
            # Check if Mother Boss fired a projectile
            fired_projectile = mother_boss.get_fired_projectile(target_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
    def handle_enemy_to_enemy_avoidance(
        self,
        replay_enemies: List['ReplayEnemyShip'],
        flockers: List['FlockerEnemyShip'],
        split_bosses: List['SplitBoss'],
        mother_bosses: List['MotherBoss'],
        babies: List['Baby']
    ) -> None:
        """Handle enemy-to-enemy avoidance for all enemy ships.
        
        Collects all enemy ships (RotatingThrusterShip instances that are enemies)
        and calls avoid_enemy_ships() for each one to prevent collisions.
        
        Args:
            replay_enemies: List of ReplayEnemyShip instances.
            flockers: List of FlockerEnemyShip instances.
            split_bosses: List of SplitBoss instances.
            mother_bosses: List of MotherBoss instances.
            babies: List of Baby instances.
        """
        # Collect all enemy ships (RotatingThrusterShip instances that are enemies)
        all_enemy_ships: List['RotatingThrusterShip'] = []
        all_enemy_ships.extend(replay_enemies)
        all_enemy_ships.extend(flockers)
        all_enemy_ships.extend(split_bosses)
        all_enemy_ships.extend(mother_bosses)
        all_enemy_ships.extend(babies)
        
        # Filter to only active enemy ships
        active_enemy_ships = [ship for ship in all_enemy_ships if ship.active and ship.is_enemy_ship()]
        
        # For each enemy ship, avoid all other enemy ships
        for enemy_ship in active_enemy_ships:
            # Create list of other enemy ships (excluding self)
            other_enemy_ships = [other for other in active_enemy_ships if other is not enemy_ship]
            enemy_ship.avoid_enemy_ships(other_enemy_ships)

