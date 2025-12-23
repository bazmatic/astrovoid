"""Quit confirmation menu rendering.

This module handles the rendering of quit confirmation dialogs.
"""

import pygame
import config
from rendering.menu_components import Button, ControllerIcon
from rendering.visual_effects import draw_button_glow


class QuitConfirmationMenu:
    """Handles quit confirmation dialog rendering."""
    
    def __init__(self, screen: pygame.Surface):
        """Initialize quit confirmation menu.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        self.small_font = pygame.font.Font(None, 24)
    
    def draw_level_complete_quit_confirmation(self, menu_pulse_phase: float) -> None:
        """Draw quit confirmation dialog overlay for level complete screen.
        
        Args:
            menu_pulse_phase: Current pulse phase for button glow animation.
        """
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box with glow
        dialog_width = 550
        dialog_height = 280
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
        
        # Draw glow effect
        draw_button_glow(
            self.screen,
            dialog_rect,
            config.COLOR_BUTTON_GLOW,
            config.BUTTON_GLOW_INTENSITY * 1.5,
            menu_pulse_phase
        )
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, dialog_rect)
        pygame.draw.rect(self.screen, config.COLOR_BUTTON_GLOW, dialog_rect, 3)
        
        # Title
        title_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        title = title_font.render("Quit to Menu?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 50))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Progress will be saved.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 100))
        self.screen.blit(message, message_rect)
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = dialog_y + 150
        
        # Yes button
        yes_button = Button(
            "YES",
            (config.SCREEN_WIDTH // 2 - 120, button_y),
            button_font,
            width=180,
            height=50
        )
        yes_button.selected = True
        yes_button.draw(self.screen, menu_pulse_phase)
        
        # A button icon for Yes
        icon_x = yes_button.position[0] - yes_button.width // 2 - 43
        ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=30, selected=True)
        
        # No button
        no_button = Button(
            "NO",
            (config.SCREEN_WIDTH // 2 + 120, button_y),
            button_font,
            width=180,
            height=50
        )
        no_button.draw(self.screen, menu_pulse_phase)
        
        # B button icon for No
        icon_x = no_button.position[0] + no_button.width // 2 + 35
        ControllerIcon.draw_b_button(self.screen, (icon_x, button_y), size=30, selected=False)
        
        # Button hints
        yes_hint = hint_font.render("Y/Enter/A", True, config.COLOR_TEXT)
        no_hint = hint_font.render("N/ESC/B", True, config.COLOR_TEXT)
        
        yes_hint_rect = yes_hint.get_rect(center=(config.SCREEN_WIDTH // 2 - 120, button_y + 50))
        no_hint_rect = no_hint.get_rect(center=(config.SCREEN_WIDTH // 2 + 120, button_y + 50))
        
        self.screen.blit(yes_hint, yes_hint_rect)
        self.screen.blit(no_hint, no_hint_rect)
    
    def draw_quit_confirmation(self, menu_pulse_phase: float) -> None:
        """Draw quit confirmation dialog overlay with modern design.
        
        Args:
            menu_pulse_phase: Current pulse phase for button glow animation.
        """
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box with glow
        dialog_width = 600
        dialog_height = 360
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
        
        # Draw glow effect
        draw_button_glow(
            self.screen,
            dialog_rect,
            config.COLOR_BUTTON_GLOW,
            config.BUTTON_GLOW_INTENSITY * 1.5,
            menu_pulse_phase
        )
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, dialog_rect)
        pygame.draw.rect(self.screen, config.COLOR_BUTTON_GLOW, dialog_rect, 3)
        
        # Title
        title_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        title = title_font.render("Quit Level?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 40))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Are you sure you want to quit? Progress will be lost.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 90))
        self.screen.blit(message, message_rect)
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = dialog_y + 150
        
        # Return to menu button
        return_button = Button(
            "RETURN TO MENU",
            (config.SCREEN_WIDTH // 2, button_y),
            button_font,
            width=400,
            height=50
        )
        return_button.selected = True
        return_button.draw(self.screen, menu_pulse_phase)
        
        # A button icon
        icon_x = return_button.position[0] - return_button.width // 2 - 43
        ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=30, selected=True)
        
        # Return button hint
        return_hint = hint_font.render("Y/Enter/A Button", True, config.COLOR_TEXT)
        return_hint_rect = return_hint.get_rect(center=(config.SCREEN_WIDTH // 2, button_y + 40))
        self.screen.blit(return_hint, return_hint_rect)
        
        # Cancel button
        cancel_button = Button(
            "CANCEL",
            (config.SCREEN_WIDTH // 2, button_y + 100),
            button_font,
            width=400,
            height=50
        )
        cancel_button.draw(self.screen, menu_pulse_phase)
        
        # B button icon
        icon_x = cancel_button.position[0] - cancel_button.width // 2 - 35
        ControllerIcon.draw_b_button(self.screen, (icon_x, button_y + 100), size=30, selected=False)
        
        # Cancel button hint
        cancel_hint = hint_font.render("N/ESC/B Button", True, config.COLOR_TEXT)
        cancel_hint_rect = cancel_hint.get_rect(center=(config.SCREEN_WIDTH // 2, button_y + 140))
        self.screen.blit(cancel_hint, cancel_hint_rect)


