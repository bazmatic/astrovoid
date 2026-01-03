"""Baby enemy that is a small, fast version of Replay Enemy.

This module implements a Baby enemy that inherits from ReplayEnemyShip
but is smaller and faster.
"""

from typing import Tuple
import config
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.command_recorder import CommandRecorder


class Baby(ReplayEnemyShip):
    """Baby enemy - a small, fast version of Replay Enemy.
    
    This is a smaller and faster ReplayEnemyShip. Babies spawn when Eggs hatch.
    
    Attributes:
        Inherits all attributes from ReplayEnemyShip.
    """
    
    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize Baby enemy.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            command_recorder: CommandRecorder instance to replay commands from.
        """
        # Call parent constructor first
        super().__init__(start_pos, command_recorder)
        # Override radius to be smaller
        self.radius = config.BABY_SIZE
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the baby enemy (faster than regular Replay Enemy)."""
        return config.SHIP_MAX_SPEED / 2 # * config.BABY_SPEED_MULTIPLIER



