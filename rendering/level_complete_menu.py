"""Level complete menu rendering.

This module handles the rendering of the level complete/failed screen.
"""

import pygame
from typing import Optional, Dict
import config
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon
from rendering.ui_elements import AnimatedStarRating
from rendering.number_sprite import NumberSprite


class LevelCompleteMenu:
    """Handles level complete/failed screen rendering."""
    
    def __init__(self, screen: pygame.Surface):
        """Initialize level complete menu.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        self.level_complete_background: Optional[AnimatedBackground] = None
        self.level_complete_image: Optional[pygame.Surface] = None
        self.level_complete_rect: Optional[pygame.Rect] = None
        self.level_failed_image: Optional[pygame.Surface] = None
        self.level_failed_rect: Optional[pygame.Rect] = None
        self.menu_pulse_phase = 0.0
        self.small_font = pygame.font.Font(None, 24)
        self.number_sprite = NumberSprite()
        self.menu_options: list[str] = []
        self.menu_buttons: list[Button] = []
        self.menu_selected_index = 0
        self._initialize()
    
    def set_options(self, level_succeeded: bool) -> None:
        """Set menu options based on level success status.
        
        Args:
            level_succeeded: True if level was completed successfully.
        """
        if level_succeeded:
            self.menu_options = ["CONTINUE", "MAIN MENU"]
        else:
            self.menu_options = ["RETRY LEVEL", "MAIN MENU"]
        self.menu_selected_index = 0
        self._create_buttons()
    
    def _create_buttons(self) -> None:
        """Create buttons for current menu options."""
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        self.menu_buttons = []
        
        button_y = config.SCREEN_HEIGHT // 2 + 150
        button_spacing = 80
        
        for i, option_text in enumerate(self.menu_options):
            button = Button(
                option_text,
                (config.SCREEN_WIDTH // 2, button_y + i * button_spacing),
                button_font,
                width=350,
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
        if not self.menu_options:
            return ""
        return self.menu_options[self.menu_selected_index]
    
    def _initialize(self) -> None:
        """Initialize level complete and failed graphics."""
        # Load level complete image
        try:
            self.level_complete_image = pygame.image.load("assets/level_complete.png").convert_alpha()
            # Scale image to 1/3 size (maintain aspect ratio)
            original_width = self.level_complete_image.get_width()
            original_height = self.level_complete_image.get_height()
            image_width = original_width // 3
            image_height = original_height // 3
            self.level_complete_image = pygame.transform.scale(self.level_complete_image, (image_width, image_height))
            self.level_complete_rect = self.level_complete_image.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
        except (pygame.error, FileNotFoundError):
            self.level_complete_image = None
            self.level_complete_rect = None
        
        # Load level failed image
        try:
            self.level_failed_image = pygame.image.load("assets/level_failed.png").convert_alpha()
            original_width = self.level_failed_image.get_width()
            original_height = self.level_failed_image.get_height()
            image_width = original_width * .4
            image_height = original_height * .4
            self.level_failed_image = pygame.transform.scale(self.level_failed_image, (image_width, image_height))
            self.level_failed_rect = self.level_failed_image.get_rect(center=(config.SCREEN_WIDTH // 2, 200))
        except (pygame.error, FileNotFoundError):
            self.level_failed_image = None
            self.level_failed_rect = None
    
    def update(self, dt: float) -> None:
        """Update menu animations.
        
        Args:
            dt: Delta time since last update.
        """
        if self.level_complete_background:
            self.level_complete_background.update(dt)
        # Update pulse phase for button glow
        self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
        if self.menu_pulse_phase >= 2 * 3.14159:
            self.menu_pulse_phase -= 2 * 3.14159
    
    def draw(
        self,
        level: int,
        level_succeeded: bool,
        completion_time_seconds: float,
        level_score_breakdown: Dict,
        star_animation: Optional[AnimatedStarRating],
        show_quit_confirmation: bool,
        draw_quit_confirmation_callback
    ) -> None:
        """Draw level complete or failed screen.
        
        Args:
            level: Current level number.
            level_succeeded: True if level was completed successfully.
            completion_time_seconds: Time taken to complete the level.
            level_score_breakdown: Score breakdown dictionary.
            star_animation: Optional animated star rating.
            show_quit_confirmation: Whether to show quit confirmation overlay.
            draw_quit_confirmation_callback: Callback to draw quit confirmation.
        """
        # Initialize background if needed
        if not self.level_complete_background:
            self.level_complete_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        # Draw animated background
        if self.level_complete_background:
            self.level_complete_background.draw(self.screen)
        
        # Show different title based on success/failure
        if level_succeeded:
            # Draw level complete graphic or fallback to text
            if self.level_complete_image is not None:
                self.screen.blit(self.level_complete_image, self.level_complete_rect)
                # Draw level number below the level complete image
                level_number_y = self.level_complete_rect.bottom + 30
                # Scale the number to be appropriately sized
                # Digit files are 216px tall, scale to about 1/4 of level complete image height
                number_scale = (self.level_complete_image.get_height() * 0.25) / 216.0
                self.number_sprite.draw_number(
                    self.screen,
                    level,
                    (config.SCREEN_WIDTH // 2, level_number_y),
                    scale=number_scale,
                    center=True
                )
            else:
                # Fallback to text if image not found
                title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
                title_text = f"LEVEL {level} COMPLETE"
                title = NeonText(
                    title_text,
                    title_font,
                    (config.SCREEN_WIDTH // 2, 150),
                    config.COLOR_NEON_ASTER_START,
                    config.COLOR_NEON_VOID_END,
                    center=True
                )
                title.pulse_phase = self.menu_pulse_phase
                title.draw(self.screen)
        else:
            # Level failed - show graphic or fallback to text
            if self.level_failed_image is not None:
                self.screen.blit(self.level_failed_image, self.level_failed_rect)
                # Draw level number below the level failed image
                level_number_y = self.level_failed_rect.bottom + 30
                # Scale the number to be appropriately sized
                # Digit files are 216px tall, scale to about 1/4 of level failed image height
                number_scale = (self.level_failed_image.get_height() * 0.25) / 216.0
                self.number_sprite.draw_number(
                    self.screen,
                    level,
                    (config.SCREEN_WIDTH // 2, level_number_y),
                    scale=number_scale,
                    center=True
                )
            else:
                # Fallback to text if image not found
                title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
                title_text = "LEVEL FAILED"
                title = title_font.render(title_text, True, (255, 100, 100))
                title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
                self.screen.blit(title, title_rect)
        
        # Format time as MM:SS.{tenths} (only show if level succeeded)
        if level_succeeded:
            minutes = int(completion_time_seconds // 60)
            remaining_seconds = completion_time_seconds % 60
            seconds = int(remaining_seconds)
            tenths = int((remaining_seconds - seconds) * 10)
            time_text = self.small_font.render(
                f"Time: {minutes:02d}:{seconds:02d}.{tenths}",
                True, config.COLOR_TEXT
            )
            time_rect = time_text.get_rect(center=(config.SCREEN_WIDTH // 2, 190))
            self.screen.blit(time_text, time_rect)
        
        # Draw animated star rating (centered, large)
        if star_animation:
            star_animation.draw(self.screen)
        
        # Draw total score
        total_score = int(level_score_breakdown.get('total_score', 0))
        score_text = self.small_font.render(
            f"Total Score: {total_score}",
            True, config.COLOR_TEXT
        )
        score_rect = score_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 80))
        self.screen.blit(score_text, score_rect)
        
        # Set menu options based on level success status
        # Check if we need to update (options might be empty or from previous state)
        expected_options = ["CONTINUE", "MAIN MENU"] if level_succeeded else ["RETRY LEVEL", "MAIN MENU"]
        if not self.menu_options or self.menu_options != expected_options:
            self.set_options(level_succeeded)
        
        # Draw buttons with controller icons
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        
        for i, button in enumerate(self.menu_buttons):
            button.selected = (i == self.menu_selected_index)
            button.draw(self.screen, self.menu_pulse_phase)
            
            # Draw controller icon next to selected button
            if button.selected:
                icon_x = button.position[0] - button.width // 2 - 58
                icon_y = button.position[1]
                ControllerIcon.draw_a_button(self.screen, (icon_x, icon_y), size=35, selected=True)
        
        # Draw hints below buttons (dynamic based on selected option)
        last_button_y = self.menu_buttons[-1].position[1] if self.menu_buttons else config.SCREEN_HEIGHT // 2 + 150
        hint_y = last_button_y + 70
        
        selected_option = self.get_selected_option()
        if selected_option == "CONTINUE":
            hint_text = "Press SPACE or A Button to Continue"
        elif selected_option == "RETRY LEVEL":
            hint_text = "Press SPACE or A Button to Retry"
        else:  # MAIN MENU
            hint_text = "Press SPACE or A Button to Return to Main Menu"
        
        hint = hint_font.render(hint_text, True, config.COLOR_TEXT)
        hint_rect = hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
        self.screen.blit(hint, hint_rect)
        
        # Navigation hint
        nav_hint = hint_font.render("Use Arrow Keys or D-Pad to Navigate", True, config.COLOR_TEXT)
        nav_hint_rect = nav_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
        self.screen.blit(nav_hint, nav_hint_rect)
        
        # Draw quit confirmation overlay if active
        if show_quit_confirmation:
            draw_quit_confirmation_callback()

