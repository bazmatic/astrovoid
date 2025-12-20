"""Input handler for processing keyboard and controller input.

This module provides the InputHandler class that processes keyboard and controller
input and maps them to game commands without side effects.
"""

import pygame
from typing import List, Optional
from entities.command_recorder import CommandType
import config


class InputHandler:
    """Handles keyboard and controller input and maps them to commands.
    
    This class processes keyboard and controller input and returns a list of commands
    without executing any game logic, following the Single Responsibility Principle.
    
    Attributes:
        key_mappings: Dictionary mapping key combinations to command types.
        controllers: List of active pygame joystick objects.
    """
    
    def __init__(self):
        """Initialize input handler with key mappings and controller support."""
        # Map key combinations to command types
        # Each entry maps a tuple of key codes to a CommandType
        self.key_mappings = {
            (pygame.K_LEFT, pygame.K_a): CommandType.ROTATE_LEFT,
            (pygame.K_RIGHT, pygame.K_d): CommandType.ROTATE_RIGHT,
            (pygame.K_UP, pygame.K_w): CommandType.APPLY_THRUST,
            (pygame.K_DOWN, pygame.K_s): CommandType.ACTIVATE_SHIELD,
        }
        
        # Track active controllers
        self.controllers: List[pygame.joystick.Joystick] = []
        self._initialize_controllers()
    
    def _initialize_controllers(self) -> None:
        """Initialize all connected controllers."""
        self.controllers = []
        joystick_count = pygame.joystick.get_count()
        for i in range(joystick_count):
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            self.controllers.append(joystick)
    
    def get_controllers(self) -> List[pygame.joystick.Joystick]:
        """Get list of active controllers.
        
        Returns:
            List of active pygame joystick objects.
        """
        return self.controllers
    
    def add_controller(self, joystick_id: int) -> None:
        """Add a newly connected controller.
        
        Args:
            joystick_id: The ID of the joystick to add.
        """
        if joystick_id < pygame.joystick.get_count():
            joystick = pygame.joystick.Joystick(joystick_id)
            joystick.init()
            if joystick not in self.controllers:
                self.controllers.append(joystick)
    
    def remove_controller(self, joystick_id: int) -> None:
        """Remove a disconnected controller.
        
        Args:
            joystick_id: The ID of the joystick to remove.
        """
        self.controllers = [
            ctrl for ctrl in self.controllers 
            if ctrl.get_id() != joystick_id
        ]
    
    def process_controller_input(self) -> List[CommandType]:
        """Process controller input and return detected commands.
        
        Returns:
            List of CommandType values detected from controller input.
            Returns empty list when no controller input is detected.
        """
        commands = []
        
        # Use first connected controller
        if not self.controllers:
            return commands
        
        controller = self.controllers[0]
        
        # Get number of axes and buttons
        num_axes = controller.get_numaxes()
        num_buttons = controller.get_numbuttons()
        
        # Process rotation from analog sticks
        # Left stick X-axis (axis 0) or right stick X-axis (axis 2)
        left_stick_x = controller.get_axis(0) if num_axes > 0 else 0.0
        right_stick_x = controller.get_axis(2) if num_axes > 2 else 0.0
        
        # Use whichever stick has input above deadzone (prioritize left stick if both have input)
        stick_x = 0.0
        if abs(left_stick_x) > config.CONTROLLER_DEADZONE:
            stick_x = left_stick_x
        elif abs(right_stick_x) > config.CONTROLLER_DEADZONE:
            stick_x = right_stick_x
        
        if abs(stick_x) > config.CONTROLLER_DEADZONE:
            if stick_x < 0:
                commands.append(CommandType.ROTATE_LEFT)
            elif stick_x > 0:
                commands.append(CommandType.ROTATE_RIGHT)
        
        # Process thrust: ZR (right trigger/axis 4) OR B button (button 1)
        thrust_active = False
        if num_axes > 4:
            right_trigger = controller.get_axis(4)
            # Triggers may range from -1.0 to 1.0 (unpressed to pressed)
            # or 0.0 to 1.0 (unpressed to pressed)
            # Check for positive values above threshold
            if right_trigger > config.CONTROLLER_TRIGGER_THRESHOLD:
                thrust_active = True
        
        if not thrust_active and num_buttons > 1:
            if controller.get_button(1):  # B button
                thrust_active = True
        
        if thrust_active:
            commands.append(CommandType.APPLY_THRUST)
        
        return commands
    
    def process_input(self, keys: List[bool]) -> List[CommandType]:
        """Process keyboard and controller input and return detected commands.
        
        Args:
            keys: List of key states from pygame.key.get_pressed().
            
        Returns:
            List of CommandType values detected from current input.
            Returns empty list when no input is detected.
        """
        commands = []
        
        # Process keyboard input
        for key_codes, command_type in self.key_mappings.items():
            # Check if any of the mapped keys are pressed
            if any(keys[key_code] for key_code in key_codes):
                commands.append(command_type)
        
        # Process controller input and combine with keyboard
        controller_commands = self.process_controller_input()
        for cmd in controller_commands:
            if cmd not in commands:
                commands.append(cmd)
        
        return commands
    
    def is_controller_fire_pressed(self) -> bool:
        """Check if controller fire button is pressed.
        
        Returns:
            True if fire button is pressed, False otherwise.
        """
        if not self.controllers:
            return False
        
        controller = self.controllers[0]
        num_axes = controller.get_numaxes()
        num_buttons = controller.get_numbuttons()
        
        # Fire: ZL (left trigger/axis 5) OR A button (button 0)
        if num_axes > 5:
            left_trigger = controller.get_axis(5)
            # Triggers may range from -1.0 to 1.0 (unpressed to pressed)
            # or 0.0 to 1.0 (unpressed to pressed)
            # Check for positive values above threshold
            if left_trigger > config.CONTROLLER_TRIGGER_THRESHOLD:
                return True
        
        if num_buttons > 0:
            if controller.get_button(0):  # A button
                return True
        
        return False
    
    def is_controller_shield_pressed(self) -> bool:
        """Check if controller shield button is pressed.
        
        Returns:
            True if shield button is pressed, False otherwise.
        """
        if not self.controllers:
            return False
        
        controller = self.controllers[0]
        num_buttons = controller.get_numbuttons()
        
        # Shield: L (left shoulder/button 4) OR R (right shoulder/button 5)
        if num_buttons > 4:
            if controller.get_button(4):  # L button (left shoulder)
                return True
        
        if num_buttons > 5:
            if controller.get_button(5):  # R button (right shoulder)
                return True
        
        return False
    
    def is_controller_menu_confirm_pressed(self, button: int) -> bool:
        """Check if controller confirm button was pressed.
        
        Args:
            button: Button ID that was pressed.
            
        Returns:
            True if confirm button (A or Start) was pressed, False otherwise.
        """
        if not self.controllers:
            return False
        
        controller = self.controllers[0]
        num_buttons = controller.get_numbuttons()
        
        # Confirm: A button (button 0) or Start button (button 7, typical for Xbox/PlayStation)
        if button == 0:  # A button
            return True
        
        if num_buttons > 7:
            if button == 7:  # Start button
                return True
        
        return False
    
    def is_controller_menu_cancel_pressed(self, button: int) -> bool:
        """Check if controller cancel button was pressed.
        
        Args:
            button: Button ID that was pressed.
            
        Returns:
            True if cancel button (B or Back) was pressed, False otherwise.
        """
        if not self.controllers:
            return False
        
        controller = self.controllers[0]
        num_buttons = controller.get_numbuttons()
        
        # Cancel: B button (button 1) or Back button (button 6, typical for Xbox/PlayStation)
        if button == 1:  # B button
            return True
        
        if num_buttons > 6:
            if button == 6:  # Back button
                return True
        
        return False

