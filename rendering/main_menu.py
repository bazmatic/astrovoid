"""Main menu rendering.

This module handles the rendering of the main menu screen.
"""

import pygame
from typing import Optional
import config
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon


class MainMenu:
    """Handles main menu rendering and state."""
    
    def __init__(self, screen: pygame.Surface):
        """Initialize main menu.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        self.menu_background: Optional[AnimatedBackground] = None
        self.menu_title: Optional[NeonText] = None
        self.menu_title_image: Optional[pygame.Surface] = None
        self.menu_title_rect: Optional[pygame.Rect] = None
        self.menu_options = ["START GAME", "OPTIONS", "QUIT"]
        self.menu_buttons: list[Button] = []
        self.menu_selected_index = 0
        self.menu_pulse_phase = 0.0
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize menu UI components."""
        # Create animated background
        self.menu_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        # Load title graphic
        try:
            self.menu_title_image = pygame.image.load("assets/title.png").convert_alpha()
            # Scale title image to half size (maintain aspect ratio)
            original_width = self.menu_title_image.get_width()
            original_height = self.menu_title_image.get_height()
            title_width = original_width // 2
            title_height = original_height // 2
            self.menu_title_image = pygame.transform.scale(self.menu_title_image, (title_width, title_height))
            self.menu_title_rect = self.menu_title_image.get_rect(center=(config.SCREEN_WIDTH // 2, 180))
        except (pygame.error, FileNotFoundError):
            # Fallback to text if image not found
            title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
            self.menu_title = NeonText(
                "ASTRO VOID",
                title_font,
                (config.SCREEN_WIDTH // 2, 180),
                config.COLOR_NEON_ASTER_START,
                config.COLOR_NEON_VOID_END,
                center=True
            )
            self.menu_title_image = None
        
        # Create buttons for all menu options
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        self.menu_buttons = []
        
        # Position buttons vertically centered with 80px spacing
        start_y = config.SCREEN_HEIGHT // 2 + 20
        button_spacing = 80
        
        for i, option_text in enumerate(self.menu_options):
            button = Button(
                option_text,
                (config.SCREEN_WIDTH // 2, start_y + i * button_spacing),
                button_font,
                width=400,
                height=60
            )
            button.selected = (i == self.menu_selected_index)
            self.menu_buttons.append(button)
    
    def navigate_up(self) -> None:
        """Navigate to the previous menu option."""
        if self.menu_selected_index > 0:
            self.menu_selected_index -= 1
    
    def navigate_down(self) -> None:
        """Navigate to the next menu option."""
        if self.menu_selected_index < len(self.menu_options) - 1:
            self.menu_selected_index += 1
    
    def get_selected_option(self) -> str:
        """Get the currently selected menu option.
        
        Returns:
            The text of the currently selected option.
        """
        return self.menu_options[self.menu_selected_index]
    
    def update(self, dt: float) -> None:
        """Update menu animations.
        
        Args:
            dt: Delta time since last update.
        """
        if self.menu_background:
            self.menu_background.update(dt)
        if self.menu_title:
            self.menu_title.update(dt)
        # Update pulse phase for button glow
        self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
        if self.menu_pulse_phase >= 2 * 3.14159:
            self.menu_pulse_phase -= 2 * 3.14159
    
    def draw(self) -> None:
        """Draw main menu with animated background and neon effects."""
        # Draw animated background
        if self.menu_background:
            self.menu_background.draw(self.screen)
        
        # Draw title graphic or neon text fallback
        if self.menu_title_image is not None:
            self.screen.blit(self.menu_title_image, self.menu_title_rect)
        elif self.menu_title:
            self.menu_title.draw(self.screen)
        
        # Draw buttons
        for i, button in enumerate(self.menu_buttons):
            button.selected = (i == self.menu_selected_index)
            button.draw(self.screen, self.menu_pulse_phase)
            
            # Draw controller icon next to selected button
            if button.selected:
                icon_x = button.position[0] - button.width // 2 - 58
                icon_y = button.position[1]
                ControllerIcon.draw_a_button(self.screen, (icon_x, icon_y), size=35, selected=True)
        
        # Draw hints below buttons (dynamic based on selected option)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        last_button_y = self.menu_buttons[-1].position[1] if self.menu_buttons else config.SCREEN_HEIGHT // 2
        hint_y = last_button_y + 80
        
        # Dynamic hint based on selected option
        selected_option = self.get_selected_option()
        if selected_option == "START GAME":
            hint_text = "Press SPACE or A Button to Start"
        elif selected_option == "OPTIONS":
            hint_text = "Press SPACE or A Button (Coming Soon)"
        else:  # QUIT
            hint_text = "Press SPACE or A Button to Quit"
        
        hint = hint_font.render(hint_text, True, config.COLOR_TEXT)
        hint_rect = hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
        self.screen.blit(hint, hint_rect)
        
        # Navigation hint
        nav_hint = hint_font.render("Use Arrow Keys or D-Pad to Navigate | ESC or B Button to Quit", True, config.COLOR_TEXT)
        nav_hint_rect = nav_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
        self.screen.blit(nav_hint, nav_hint_rect)
        
        # Draw controls info at bottom (smaller, less prominent)
        controls_y = config.SCREEN_HEIGHT - 120
        controls_font = pygame.font.Font(None, 20)
        controls_text = [
            "Controls: Arrow Keys/WASD - Move | Space - Fire | Down/S - Shield",
            "Controller: Sticks - Move | R/ZR/B - Fire | A - Shield | L/ZL - Thrust"
        ]
        for i, line in enumerate(controls_text):
            text = controls_font.render(line, True, (150, 150, 150))
            text_rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, controls_y + i * 25))
            self.screen.blit(text, text_rect)

