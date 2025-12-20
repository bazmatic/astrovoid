"""Command recorder for tracking player input commands.

This module provides the CommandRecorder class that records player commands
and maintains a fixed-size window of the last N actions for replay purposes.
"""

from typing import List
from enum import Enum
from collections import deque
import config


class CommandType(Enum):
    """Types of commands that can be recorded."""
    ROTATE_LEFT = "rotate_left"
    ROTATE_RIGHT = "rotate_right"
    APPLY_THRUST = "apply_thrust"
    FIRE = "fire"
    NO_ACTION = "no_action"  # Recorded when player is not providing input


class CommandRecorder:
    """Records player commands in a fixed-size sliding window.
    
    Maintains a rolling buffer of the last N actions (including NO_ACTION),
    where N is configurable via REPLAY_ENEMY_WINDOW_SIZE.
    
    Attributes:
        commands: Deque of CommandType values, maintaining exactly window_size items.
        window_size: Number of actions to store.
    """
    
    def __init__(self, window_size: int = None):
        """Initialize command recorder.
        
        Args:
            window_size: Number of actions to store. Defaults to config value.
        """
        self.window_size = window_size if window_size is not None else config.REPLAY_ENEMY_WINDOW_SIZE
        self.commands: deque = deque(maxlen=self.window_size)
    
    def start_recording(self) -> None:
        """Start recording (clear existing commands)."""
        self.commands.clear()
    
    def record_command(self, command_type: CommandType) -> None:
        """Record a command.
        
        The deque automatically maintains the window size by removing
        the oldest command when the limit is reached.
        
        Args:
            command_type: The type of command to record.
        """
        self.commands.append(command_type)
    
    def get_replay_commands(self) -> List[CommandType]:
        """Get all commands in the window.
        
        Returns:
            List of CommandType values in the window (up to window_size items).
        """
        return list(self.commands)
    
    def get_command_count(self) -> int:
        """Get the number of commands currently stored.
        
        Returns:
            Number of commands in the window.
        """
        return len(self.commands)
    
    def clear(self) -> None:
        """Clear all recorded commands."""
        self.commands.clear()
