"""Quit confirmation menu rendering.

This module handles the rendering of quit confirmation dialogs.
"""

import pygame
import config
from rendering.menu_components import ConfirmationDialog


class QuitConfirmationMenu:
    """Handles quit confirmation dialog rendering."""
    
    def __init__(self, screen: pygame.Surface):
        """Initialize quit confirmation menu.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        # Create dialog instances
        self.level_complete_dialog = ConfirmationDialog(
            screen,
            title="Quit to Menu?",
            message="Progress will be saved.",
            confirm_label="OK",
            cancel_label="Cancel",
            dialog_width=550,
            dialog_height=280,
            button_layout="side_by_side"
        )
        self.quit_level_dialog = ConfirmationDialog(
            screen,
            title="Quit Level?",
            message="Are you sure you want to quit? Progress will be lost.",
            confirm_label="OK",
            cancel_label="Cancel",
            dialog_width=600,
            dialog_height=360,
            button_layout="stacked"
        )
    
    def draw_level_complete_quit_confirmation(
        self,
        menu_pulse_phase: float,
        selection_index: int = 0
    ) -> None:
        """Draw quit confirmation dialog overlay for level complete screen.
        
        Args:
            menu_pulse_phase: Current pulse phase for button glow animation.
            selection_index: Which button is selected (0 = OK, 1 = Cancel).
        """
        self.level_complete_dialog.draw(menu_pulse_phase, selection_index)
    
    def draw_quit_confirmation(
        self,
        menu_pulse_phase: float,
        selection_index: int = 0
    ) -> None:
        """Draw quit confirmation dialog overlay with modern design.
        
        Args:
            menu_pulse_phase: Current pulse phase for button glow animation.
            selection_index: Which button is selected (0 = OK, 1 = Cancel).
        """
        self.quit_level_dialog.draw(menu_pulse_phase, selection_index)


