"""Collision detection and handling for game entities.

This module centralizes all collision detection logic, eliminating duplication
and making collision handling easier to maintain and extend.
"""

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING
import config
from entities.powerup_crystal import PowerupCrystal
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.split_boss import SplitBoss
    from entities.ship import Ship
    from entities.projectile import Projectile
    from maze.generator import Maze
    from scoring.system import ScoringSystem
    from sounds import SoundManager


class CollisionHandler:
    """Handles all collision detection and response in the game."""
    
    def __init__(
        self,
        sound_manager: 'SoundManager',
        scoring: 'ScoringSystem',
        command_recorder
    ):
        """Initialize collision handler.
        
        Args:
            sound_manager: Sound manager for playing collision sounds.
            scoring: Scoring system for recording collisions.
            command_recorder: Command recorder for spawning replay enemies.
        """
        self.sound_manager = sound_manager
        self.scoring = scoring
        self.command_recorder = command_recorder
    
    def handle_projectile_enemy_collisions(
        self,
        projectile: 'Projectile',
        enemies: List['Enemy'],
        replay_enemies: List['ReplayEnemyShip'],
        split_bosses: List['SplitBoss'],
        powerup_crystals: List['PowerupCrystal']
    ) -> bool:
        """Handle collisions between a projectile and enemies.
        
        Args:
            projectile: The projectile to check collisions for.
            enemies: List of regular enemies.
            replay_enemies: List of replay enemies.
            split_bosses: List of SplitBoss enemies.
            powerup_crystals: List to add spawned crystals to.
            
        Returns:
            True if collision occurred and projectile should be deactivated, False otherwise.
        """
        if projectile.is_enemy:
            return False  # Enemy projectiles don't hit enemies
        
        if not projectile.active:
            return False
        
        # Check projectile-enemy collision
        for enemy in enemies:
            if enemy.active and projectile.active:
                if projectile.check_circle_collision(enemy.get_pos(), enemy.radius):
                    enemy_pos = enemy.get_pos()
                    enemy.destroy()
                    self.sound_manager.play_enemy_destroy()
                    self.scoring.record_enemy_destroyed()
                    
                    # Spawn powerup crystal with probability
                    if random.random() < config.POWERUP_CRYSTAL_SPAWN_CHANCE:
                        crystal = PowerupCrystal(enemy_pos)
                        powerup_crystals.append(crystal)
                    
                    return True  # Projectile destroyed
        
        # Check projectile-replay enemy collision
        for replay_enemy in replay_enemies:
            if replay_enemy.active and projectile.active:
                if projectile.check_circle_collision(replay_enemy.get_pos(), replay_enemy.radius):
                    enemy_pos = replay_enemy.get_pos()
                    replay_enemy.active = False
                    self.sound_manager.play_enemy_destroy()
                    self.scoring.record_enemy_destroyed()
                    
                    # Spawn powerup crystal with probability
                    if random.random() < config.POWERUP_CRYSTAL_SPAWN_CHANCE:
                        crystal = PowerupCrystal(enemy_pos)
                        powerup_crystals.append(crystal)
                    
                    return True  # Projectile destroyed
        
        # Check projectile-SplitBoss collision
        for split_boss in split_bosses:
            if split_boss.active and projectile.active:
                if projectile.check_circle_collision(split_boss.get_pos(), split_boss.radius):
                    boss_pos = split_boss.get_pos()
                    boss_velocity = (split_boss.vx, split_boss.vy)
                    
                    # Take damage - returns True if destroyed
                    if split_boss.take_damage():
                        # SplitBoss destroyed - spawn two ReplayEnemyShip instances
                        split_boss.active = False
                        self.sound_manager.play_enemy_destroy()
                        self.scoring.record_enemy_destroyed()
                        
                        # Spawn two ReplayEnemyShip instances at random nearby positions
                        self._spawn_split_boss_children(
                            boss_pos, boss_velocity, replay_enemies, powerup_crystals
                        )
                    # Note: If not destroyed, projectile still hits but boss survives
                    
                    return True  # Projectile destroyed
        
        return False
    
    def _spawn_split_boss_children(
        self,
        boss_pos: Tuple[float, float],
        boss_velocity: Tuple[float, float],
        replay_enemies: List['ReplayEnemyShip'],
        powerup_crystals: List['PowerupCrystal']
    ) -> None:
        """Spawn two ReplayEnemyShip instances when SplitBoss is destroyed.
        
        Args:
            boss_pos: Position where SplitBoss was destroyed.
            boss_velocity: Velocity of the SplitBoss at destruction.
            replay_enemies: List to add spawned enemies to.
            powerup_crystals: List to add spawned crystal to.
        """
        from entities.replay_enemy_ship import ReplayEnemyShip
        
        for i in range(2):
            # Random offset within spawn range
            angle_offset = random.uniform(0, 2 * math.pi)
            distance_offset = random.uniform(
                config.SPLIT_BOSS_SPAWN_OFFSET_RANGE * 0.5,
                config.SPLIT_BOSS_SPAWN_OFFSET_RANGE
            )
            spawn_x = boss_pos[0] + math.cos(angle_offset) * distance_offset
            spawn_y = boss_pos[1] + math.sin(angle_offset) * distance_offset
            
            # Split velocity: one leftward, one rightward
            split_angle = math.atan2(boss_velocity[1], boss_velocity[0])
            if i == 0:
                # First enemy: leftward component
                velocity_angle = split_angle - math.pi / 4  # 45 degrees left
            else:
                # Second enemy: rightward component
                velocity_angle = split_angle + math.pi / 4  # 45 degrees right
            
            spawn_velocity_x = math.cos(velocity_angle) * config.SPLIT_BOSS_SPLIT_VELOCITY_MAGNITUDE
            spawn_velocity_y = math.sin(velocity_angle) * config.SPLIT_BOSS_SPLIT_VELOCITY_MAGNITUDE
            
            # Create new ReplayEnemyShip
            spawned_enemy = ReplayEnemyShip((spawn_x, spawn_y), self.command_recorder)
            spawned_enemy.vx = spawn_velocity_x
            spawned_enemy.vy = spawn_velocity_y
            spawned_enemy.current_replay_index = 0
            replay_enemies.append(spawned_enemy)
        
        # Spawn powerup crystal with probability
        if random.random() < config.POWERUP_CRYSTAL_SPAWN_CHANCE:
            crystal = PowerupCrystal(boss_pos)
            powerup_crystals.append(crystal)
    
    def handle_projectile_ship_collision(
        self,
        projectile: 'Projectile',
        ship: 'Ship',
        scoring: 'ScoringSystem'
    ) -> bool:
        """Handle collision between enemy projectile and ship.
        
        Args:
            projectile: The enemy projectile.
            ship: The player ship.
            scoring: Scoring system for recording collisions.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        if not projectile.is_enemy or not projectile.active:
            return False
        
        if ship.is_shield_active():
            return False
        
        if projectile.check_circle_collision((ship.x, ship.y), ship.radius):
            scoring.record_enemy_collision()
            # Apply small velocity impulse to ship from projectile impact
            ship.vx += projectile.vx * config.PROJECTILE_IMPACT_FORCE
            ship.vy += projectile.vy * config.PROJECTILE_IMPACT_FORCE
            return True
        
        return False
    
    def handle_ship_crystal_collision(
        self,
        ship: 'Ship',
        crystal: 'PowerupCrystal'
    ) -> bool:
        """Handle collision between ship and powerup crystal.
        
        Args:
            ship: The player ship.
            crystal: The powerup crystal.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        if not crystal.active:
            return False
        
        if crystal.check_circle_collision((ship.x, ship.y), ship.radius):
            ship.activate_gun_upgrade()
            return True
        
        return False

