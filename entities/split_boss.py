"""SplitBoss enemy that splits into two ReplayEnemyShip instances when destroyed.

This module implements a SplitBoss enemy that is a double-size ReplayEnemyShip
with multiple hit points. When destroyed, it spawns two regular ReplayEnemyShip
instances.
"""

from typing import Tuple, List
import config
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.command_recorder import CommandRecorder


class SplitBoss(ReplayEnemyShip):
    """Boss enemy that splits into two ReplayEnemyShip instances when destroyed.
    
    This is a double-size ReplayEnemyShip with multiple hit points. When hit
    points reach zero, it spawns two regular ReplayEnemyShip instances.
    
    Attributes:
        hit_points: Current hit points remaining.
        max_hit_points: Maximum hit points (for visual feedback if needed).
    """
    
    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize SplitBoss enemy.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            command_recorder: CommandRecorder instance to replay commands from.
        """
        # Call parent constructor first to properly initialize all attributes
        super().__init__(start_pos, command_recorder)
        # Override radius to double size after parent initialization
        self.radius = config.REPLAY_ENEMY_SIZE * config.SPLIT_BOSS_SIZE_MULTIPLIER
        # Add hit points system
        self.hit_points = config.SPLIT_BOSS_HIT_POINTS
        self.max_hit_points = config.SPLIT_BOSS_HIT_POINTS
    
    def take_damage(self) -> bool:
        """Take damage from a projectile hit.
        
        Decrements hit points by 1. Returns True if the boss should be destroyed
        (hit points reached 0), False otherwise.
        
        Returns:
            True if hit points reached 0, False otherwise.
        """
        self.hit_points -= 1
        return self.hit_points <= 0

