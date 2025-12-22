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
        
        # Create buttons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        
        start_button = Button(
            "START GAME",
            (config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 50),
            button_font,
            width=400,
            height=60
        )
        start_button.selected = True
        
        self.menu_buttons = [start_button]
        self.menu_selected_index = 0
    
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
        button_y = config.SCREEN_HEIGHT // 2 + 50
        for i, button in enumerate(self.menu_buttons):
            button.selected = (i == self.menu_selected_index)
            button.draw(self.screen, self.menu_pulse_phase)
            
            # Draw controller icon next to selected button
            if button.selected:
                icon_x = button.position[0] - button.width // 2 - 50
                icon_y = button.position[1]
                ControllerIcon.draw_a_button(self.screen, (icon_x, icon_y), size=35, selected=True)
        
        # Draw hints below buttons
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        hint_y = button_y + 80
        
        # Start hint
        start_hint = hint_font.render("Press SPACE or A Button to Start", True, config.COLOR_TEXT)
        start_hint_rect = start_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
        self.screen.blit(start_hint, start_hint_rect)
        
        # Quit hint
        quit_hint = hint_font.render("Press ESC or B Button to Quit", True, config.COLOR_TEXT)
        quit_hint_rect = quit_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
        self.screen.blit(quit_hint, quit_hint_rect)
        
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

