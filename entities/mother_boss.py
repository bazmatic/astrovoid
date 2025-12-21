"""Mother Boss enemy that lays Eggs constantly.

This module implements a Mother Boss enemy that is larger than SplitBoss
and continuously lays Egg enemies.
"""

from typing import Tuple, List
import config
from entities.split_boss import SplitBoss
from entities.command_recorder import CommandRecorder


class MotherBoss(SplitBoss):
    """Boss enemy that is larger than SplitBoss and lays Eggs constantly.
    
    This is a triple-size ReplayEnemyShip with multiple hit points. It continuously
    lays Egg enemies that can grow and spawn Replay Enemies. When destroyed, it
    spawns two regular ReplayEnemyShip instances (like SplitBoss).
    
    Attributes:
        egg_lay_cooldown: Frames remaining until next egg can be laid.
        egg_lay_interval: Frames between egg laying.
    """
    
    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize Mother Boss enemy.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            command_recorder: CommandRecorder instance to replay commands from.
        """
        # Call parent constructor first to properly initialize all attributes
        super().__init__(start_pos, command_recorder)
        # Override radius to be larger than SplitBoss
        self.radius = config.REPLAY_ENEMY_SIZE * config.MOTHER_BOSS_SIZE_MULTIPLIER
        # Override hit points (Mother Boss has more hit points)
        self.hit_points = config.MOTHER_BOSS_HIT_POINTS
        self.max_hit_points = config.MOTHER_BOSS_HIT_POINTS
        # Egg laying system
        self.egg_lay_cooldown = 0
        self.egg_lay_interval = config.MOTHER_BOSS_EGG_LAY_INTERVAL
    
    def update(self, dt: float, player_pos: Tuple[float, float] = None) -> None:
        """Update Mother Boss state and egg laying.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position (unused but required by parent).
        """
        # Update parent (handles movement, replay commands, etc.)
        super().update(dt, player_pos)
        
        # Update egg laying cooldown
        if self.egg_lay_cooldown > 0:
            self.egg_lay_cooldown -= 1
    
    def can_lay_egg(self) -> bool:
        """Check if Mother Boss can lay an egg.
        
        Returns:
            True if cooldown has expired and egg can be laid, False otherwise.
        """
        return self.egg_lay_cooldown <= 0
    
    def lay_egg(self, eggs: List['Egg']) -> bool:
        """Lay an egg at the Mother Boss's position.
        
        Args:
            eggs: List to add the spawned egg to.
            
        Returns:
            True if egg was laid, False if cooldown not ready.
        """
        if not self.can_lay_egg():
            return False
        
        from entities.egg import Egg
        
        # Lay egg at Mother Boss position with small random offset
        import random
        import math
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.uniform(0, self.radius * 0.5)
        egg_x = self.x + math.cos(offset_angle) * offset_distance
        egg_y = self.y + math.sin(offset_angle) * offset_distance
        
        egg = Egg((egg_x, egg_y))
        eggs.append(egg)
        
        # Reset cooldown
        self.egg_lay_cooldown = self.egg_lay_interval
        
        return True

