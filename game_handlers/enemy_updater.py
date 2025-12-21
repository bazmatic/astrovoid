"""Enemy update handler for unified enemy update logic.

This module provides a unified interface for updating all enemy types,
eliminating code duplication in the main game loop.
"""

from typing import List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.split_boss import SplitBoss
    from entities.egg import Egg
    from entities.ship import Ship
    from entities.projectile import Projectile
    from maze.generator import Maze
    from scoring.system import ScoringSystem
    from entities.command_recorder import CommandRecorder


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
        projectiles: List['Projectile']
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
            
            enemy.update(dt, player_pos, maze.walls)
            
            # Check enemy-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(enemy.get_pos(), enemy.radius, enemy):
                    scoring.record_enemy_collision()
            
            # Check if enemy fired a projectile
            fired_projectile = enemy.get_fired_projectile(player_pos)
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
        projectiles: List['Projectile']
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
            
            replay_enemy.update(dt, player_pos)
            
            # Check replay enemy-wall collision
            # This uses the replay enemy's own state and is completely independent
            # from the player ship's collisions.
            replay_enemy.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check replay enemy-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(replay_enemy.get_pos(), replay_enemy.radius, replay_enemy):
                    scoring.record_enemy_collision()
            
            # Check if replay enemy fired a projectile
            fired_projectile = replay_enemy.get_fired_projectile(player_pos)
            if fired_projectile:
                projectiles.append(fired_projectile)
    
    def update_split_bosses(
        self,
        split_bosses: List['SplitBoss'],
        dt: float,
        player_pos: Optional[Tuple[float, float]],
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        projectiles: List['Projectile']
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
            
            split_boss.update(dt, player_pos)
            
            # Check SplitBoss-wall collision
            split_boss.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check SplitBoss-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(split_boss.get_pos(), split_boss.radius, split_boss):
                    scoring.record_enemy_collision()
            
            # Check if SplitBoss fired a projectile
            fired_projectile = split_boss.get_fired_projectile(player_pos)
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
        replay_enemies: List['ReplayEnemyShip']
    ) -> None:
        """Update egg enemies.
        
        Args:
            eggs: List of Egg instances.
            dt: Delta time since last update.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            command_recorder: Command recorder for spawning Replay Enemies.
            replay_enemies: List to add spawned Replay Enemies to.
        """
        for egg in eggs:
            if not egg.active:
                continue
            
            egg.update(dt)
            
            # Check if egg should pop
            if egg.should_pop():
                egg.pop(command_recorder, replay_enemies)
                continue
            
            # Check egg-wall collision (eggs are stationary, but check for consistency)
            egg.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check egg-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(egg.get_pos(), egg.radius, egg):
                    scoring.record_enemy_collision()
    
    def update_eggs(
        self,
        eggs: List['Egg'],
        dt: float,
        maze: 'Maze',
        ship: 'Ship',
        scoring: 'ScoringSystem',
        command_recorder: 'CommandRecorder',
        replay_enemies: List['ReplayEnemyShip']
    ) -> None:
        """Update egg enemies.
        
        Args:
            eggs: List of Egg instances.
            dt: Delta time since last update.
            maze: Maze instance for wall collision.
            ship: Player ship for collision detection.
            scoring: Scoring system for recording collisions.
            command_recorder: Command recorder for spawning Replay Enemies.
            replay_enemies: List to add spawned Replay Enemies to.
        """
        for egg in eggs:
            if not egg.active:
                continue
            
            egg.update(dt)
            
            # Check if egg should pop
            if egg.should_pop():
                egg.pop(command_recorder, replay_enemies)
                continue
            
            # Check egg-wall collision (eggs are stationary, but check for consistency)
            egg.check_wall_collision(maze.walls, maze.spatial_grid)
            
            # Check egg-ship collision (skip if shield is active)
            if not ship.is_shield_active():
                if ship.check_circle_collision(egg.get_pos(), egg.radius, egg):
                    scoring.record_enemy_collision()

