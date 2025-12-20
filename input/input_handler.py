"""Input handler for processing keyboard input.

This module provides the InputHandler class that processes keyboard input
and maps it to game commands without side effects.
"""

import pygame
from typing import List
from entities.command_recorder import CommandType


class InputHandler:
    """Handles keyboard input and maps keys to commands.
    
    This class processes keyboard input and returns a list of commands
    without executing any game logic, following the Single Responsibility Principle.
    
    Attributes:
        key_mappings: Dictionary mapping key combinations to command types.
    """
    
    def __init__(self):
        """Initialize input handler with key mappings."""
        # Map key combinations to command types
        # Each entry maps a tuple of key codes to a CommandType
        self.key_mappings = {
            (pygame.K_LEFT, pygame.K_a): CommandType.ROTATE_LEFT,
            (pygame.K_RIGHT, pygame.K_d): CommandType.ROTATE_RIGHT,
            (pygame.K_UP, pygame.K_w): CommandType.APPLY_THRUST,
        }
    
    def process_input(self, keys: List[bool]) -> List[CommandType]:
        """Process keyboard input and return detected commands.
        
        Args:
            keys: List of key states from pygame.key.get_pressed().
            
        Returns:
            List of CommandType values detected from current input.
            Returns empty list when no input is detected.
        """
        commands = []
        
        # Check each key mapping
        for key_codes, command_type in self.key_mappings.items():
            # Check if any of the mapped keys are pressed
            if any(keys[key_code] for key_code in key_codes):
                commands.append(command_type)
        
        return commands
