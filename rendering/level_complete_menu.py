"""Level complete menu rendering.

This module handles the rendering of the level complete/failed screen.
"""

import pygame
from typing import Optional, Dict
import config
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon
from rendering.ui_elements import AnimatedStarRating


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
        self.menu_pulse_phase = 0.0
        self.small_font = pygame.font.Font(None, 24)
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize level complete graphic."""
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
            # Level failed - show text
            title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
            title_text = "LEVEL FAILED"
            title = title_font.render(title_text, True, (255, 100, 100))
            title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
            self.screen.blit(title, title_rect)
        
        # Format time as minutes:seconds with one decimal place
        minutes = int(completion_time_seconds // 60)
        seconds_with_decimal = completion_time_seconds % 60
        time_text = self.small_font.render(
            f"Time: {minutes}:{seconds_with_decimal:05.1f}",
            True, config.COLOR_TEXT
        )
        time_rect = time_text.get_rect(center=(config.SCREEN_WIDTH // 2, 220))
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
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = config.SCREEN_HEIGHT // 2 + 150
        
        if level_succeeded:
            # Continue button
            continue_button = Button(
                "CONTINUE",
                (config.SCREEN_WIDTH // 2, button_y),
                button_font,
                width=350,
                height=60
            )
            continue_button.selected = True
            continue_button.draw(self.screen, self.menu_pulse_phase)
            
            # Controller icon
            icon_x = continue_button.position[0] - continue_button.width // 2 - 50
            ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=35, selected=True)
            
            # Hints
            hint_y = button_y + 70
            continue_hint = hint_font.render("Press SPACE/ENTER or A Button", True, config.COLOR_TEXT)
            continue_hint_rect = continue_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
            self.screen.blit(continue_hint, continue_hint_rect)
            
            back_hint = hint_font.render("Press ESC/Q or B Button to Return to Menu", True, config.COLOR_TEXT)
            back_hint_rect = back_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
            self.screen.blit(back_hint, back_hint_rect)
        else:
            # Retry button
            retry_button = Button(
                "RETRY LEVEL",
                (config.SCREEN_WIDTH // 2, button_y),
                button_font,
                width=350,
                height=60
            )
            retry_button.selected = True
            retry_button.draw(self.screen, self.menu_pulse_phase)
            
            # Controller icon
            icon_x = retry_button.position[0] - retry_button.width // 2 - 50
            ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=35, selected=True)
            
            # Hints
            hint_y = button_y + 70
            retry_hint = hint_font.render("Press SPACE/ENTER or A Button", True, config.COLOR_TEXT)
            retry_hint_rect = retry_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
            self.screen.blit(retry_hint, retry_hint_rect)
            
            back_hint = hint_font.render("Press ESC/Q or B Button to Return to Menu", True, config.COLOR_TEXT)
            back_hint_rect = back_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
            self.screen.blit(back_hint, back_hint_rect)
        
        # Draw quit confirmation overlay if active
        if show_quit_confirmation:
            draw_quit_confirmation_callback()

