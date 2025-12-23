"""Reusable menu UI components.

This module provides reusable UI components for menus including buttons,
controller icons, animated backgrounds, and neon text rendering.
"""

import pygame
import math
from typing import Tuple, Optional, Callable
import config
from rendering.visual_effects import draw_neon_text, draw_button_glow, Starfield, MenuParticleSystem


class ControllerIcon:
    """Renders controller button icons."""
    
    @staticmethod
    def draw_a_button(
        screen: pygame.Surface,
        position: Tuple[int, int],
        size: int = 30,
        selected: bool = False
    ) -> None:
        """Draw A button icon.
        
        Args:
            screen: The pygame Surface to draw on.
            position: (x, y) center position.
            size: Icon size in pixels.
            selected: If True, adds pulsing glow effect.
        """
        x, y = position
        color = config.COLOR_BUTTON_A
        
        # Draw glow if selected
        if selected:
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 200.0)
            glow_intensity = 0.4 + 0.3 * pulse
            glow_radius = size * 0.6
            for layer in range(5):
                layer_radius = glow_radius - layer
                alpha = int(255 * glow_intensity * (1.0 - layer / 5))
                if alpha > 0 and layer_radius > 0:
                    glow_color = (*color, alpha)
                    glow_surf = pygame.Surface((int(layer_radius * 2) + 4, int(layer_radius * 2) + 4), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, glow_color, (int(layer_radius) + 2, int(layer_radius) + 2), int(layer_radius))
                    screen.blit(glow_surf, (x - int(layer_radius) - 2, y - int(layer_radius) - 2))
        
        # Draw button circle
        pygame.draw.circle(screen, color, (x, y), size)
        pygame.draw.circle(screen, (255, 255, 255), (x, y), size, 2)
        
        # Draw "A" text
        font = pygame.font.Font(None, size)
        text = font.render("A", True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y))
        screen.blit(text, text_rect)
    
    @staticmethod
    def draw_b_button(
        screen: pygame.Surface,
        position: Tuple[int, int],
        size: int = 30,
        selected: bool = False
    ) -> None:
        """Draw B button icon.
        
        Args:
            screen: The pygame Surface to draw on.
            position: (x, y) center position.
            size: Icon size in pixels.
            selected: If True, adds pulsing glow effect.
        """
        x, y = position
        color = config.COLOR_BUTTON_B
        
        # Draw glow if selected
        if selected:
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 200.0)
            glow_intensity = 0.4 + 0.3 * pulse
            glow_radius = size * 0.6
            for layer in range(5):
                layer_radius = glow_radius - layer
                alpha = int(255 * glow_intensity * (1.0 - layer / 5))
                if alpha > 0 and layer_radius > 0:
                    glow_color = (*color, alpha)
                    glow_surf = pygame.Surface((int(layer_radius * 2) + 4, int(layer_radius * 2) + 4), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, glow_color, (int(layer_radius) + 2, int(layer_radius) + 2), int(layer_radius))
                    screen.blit(glow_surf, (x - int(layer_radius) - 2, y - int(layer_radius) - 2))
        
        # Draw button circle
        pygame.draw.circle(screen, color, (x, y), size)
        pygame.draw.circle(screen, (255, 255, 255), (x, y), size, 2)
        
        # Draw "B" text
        font = pygame.font.Font(None, size)
        text = font.render("B", True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y))
        screen.blit(text, text_rect)


class Button:
    """Reusable button component with hover/selected states and glow effects."""
    
    def __init__(
        self,
        text: str,
        position: Tuple[int, int],
        font: pygame.font.Font,
        callback: Optional[Callable[[], None]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        padding: int = 20
    ):
        """Initialize button.
        
        Args:
            text: Button text.
            position: (x, y) center position.
            font: Font to use for text.
            callback: Optional callback function when button is clicked.
            width: Optional fixed width (auto-calculated if None).
            height: Optional fixed height (auto-calculated if None).
            padding: Padding around text.
        """
        self.text = text
        self.position = position
        self.font = font
        self.callback = callback
        self.padding = padding
        
        # Calculate size
        text_surface = font.render(text, True, (255, 255, 255))
        text_width, text_height = text_surface.get_size()
        self.width = width if width is not None else text_width + padding * 2
        self.height = height if height is not None else text_height + padding * 2
        
        # State
        self.selected = False
        self.hover = False
    
    def get_rect(self) -> pygame.Rect:
        """Get button rectangle.
        
        Returns:
            Button rectangle centered on position.
        """
        return pygame.Rect(
            self.position[0] - self.width // 2,
            self.position[1] - self.height // 2,
            self.width,
            self.height
        )
    
    def contains_point(self, point: Tuple[int, int]) -> bool:
        """Check if point is inside button.
        
        Args:
            point: (x, y) point to check.
            
        Returns:
            True if point is inside button.
        """
        return self.get_rect().collidepoint(point)
    
    def draw(self, screen: pygame.Surface, pulse_phase: float = 0.0) -> None:
        """Draw button.
        
        Args:
            screen: The pygame Surface to draw on.
            pulse_phase: Phase for pulsing animation (0.0 to 2*pi).
        """
        rect = self.get_rect()
        
        # Draw glow if selected
        if self.selected:
            draw_button_glow(
                screen,
                rect,
                config.COLOR_BUTTON_GLOW,
                config.BUTTON_GLOW_INTENSITY,
                pulse_phase
            )
        
        # Draw button background
        bg_color = (40, 40, 60) if not self.selected else (60, 60, 90)
        pygame.draw.rect(screen, bg_color, rect)
        border_color = (100, 100, 100) if not self.selected else config.COLOR_TEXT
        pygame.draw.rect(screen, border_color, rect, 2)
        
        # Draw text (dimmed if not selected)
        text_color = (150, 150, 150) if not self.selected else config.COLOR_TEXT
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.position)
        screen.blit(text_surface, text_rect)
        
        # Draw selection indicator (arrow)
        if self.selected:
            arrow_size = 15
            arrow_x = rect.left - arrow_size - 10
            arrow_y = self.position[1]
            points = [
                (arrow_x, arrow_y),
                (arrow_x + arrow_size, arrow_y - arrow_size // 2),
                (arrow_x + arrow_size, arrow_y + arrow_size // 2)
            ]
            pygame.draw.polygon(screen, config.COLOR_BUTTON_GLOW, points)


class AnimatedBackground:
    """Animated background for menus with starfield and particles."""
    
    def __init__(self, width: int, height: int):
        """Initialize animated background.
        
        Args:
            width: Screen width.
            height: Screen height.
        """
        self.width = width
        self.height = height
        self.starfield = Starfield(width, height)
        self.particles = MenuParticleSystem(width, height)
    
    def update(self, dt: float) -> None:
        """Update background animation.
        
        Args:
            dt: Delta time (normalized to 60fps).
        """
        self.starfield.update(dt)
        self.particles.update(dt)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw background.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        # Draw starfield
        self.starfield.draw(screen)
        # Draw particles
        self.particles.draw(screen)


class NeonText:
    """Text rendering with neon glow effects."""
    
    def __init__(
        self,
        text: str,
        font: pygame.font.Font,
        position: Tuple[int, int],
        color_start: Tuple[int, int, int],
        color_end: Tuple[int, int, int],
        center: bool = True
    ):
        """Initialize neon text.
        
        Args:
            text: Text to render.
            font: Font to use.
            position: (x, y) position or center point if center=True.
            color_start: Start color for gradient.
            color_end: End color for gradient.
            center: If True, position is treated as center point.
        """
        self.text = text
        self.font = font
        self.position = position
        self.color_start = color_start
        self.color_end = color_end
        self.center = center
        self.pulse_phase = 0.0
    
    def update(self, dt: float) -> None:
        """Update animation.
        
        Args:
            dt: Delta time (normalized to 60fps).
        """
        dt_seconds = dt / 60.0
        self.pulse_phase += config.NEON_GLOW_PULSE_SPEED * dt_seconds
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw neon text.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        draw_neon_text(
            screen,
            self.text,
            self.font,
            self.position,
            self.color_start,
            self.color_end,
            config.NEON_GLOW_INTENSITY,
            self.pulse_phase,
            self.center
        )


class ConfirmationDialog:
    """Reusable confirmation dialog component with two-button layout."""
    
    def __init__(
        self,
        screen: pygame.Surface,
        title: str,
        message: str,
        confirm_label: str = "OK",
        cancel_label: str = "Cancel",
        dialog_width: int = 550,
        dialog_height: int = 280,
        button_layout: str = "side_by_side"
    ):
        """Initialize confirmation dialog.
        
        Args:
            screen: The pygame Surface to draw on.
            title: Dialog title text.
            message: Dialog message text.
            confirm_label: Text for confirm button (default: "OK").
            cancel_label: Text for cancel button (default: "Cancel").
            dialog_width: Width of dialog box.
            dialog_height: Height of dialog box.
            button_layout: "side_by_side" or "stacked" button layout.
        """
        self.screen = screen
        self.title = title
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.dialog_width = dialog_width
        self.dialog_height = dialog_height
        self.button_layout = button_layout
        
        self.small_font = pygame.font.Font(None, 24)
        self.title_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        self.button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        self.hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
    
    def draw(
        self,
        menu_pulse_phase: float,
        selection_index: int = 0
    ) -> None:
        """Draw confirmation dialog.
        
        Args:
            menu_pulse_phase: Current pulse phase for button glow animation.
            selection_index: Which button is selected (0 = confirm, 1 = cancel).
        """
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Calculate dialog position (centered)
        dialog_x = (config.SCREEN_WIDTH - self.dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - self.dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, self.dialog_width, self.dialog_height)
        
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
        
        # Draw title
        title_surface = self.title_font.render(self.title, True, config.COLOR_TEXT)
        title_rect = title_surface.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 50))
        self.screen.blit(title_surface, title_rect)
        
        # Draw message
        message_surface = self.small_font.render(self.message, True, config.COLOR_TEXT)
        message_rect = message_surface.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 100))
        self.screen.blit(message_surface, message_rect)
        
        # Draw buttons based on layout
        if self.button_layout == "side_by_side":
            self._draw_side_by_side_buttons(dialog_y, menu_pulse_phase, selection_index)
        else:
            self._draw_stacked_buttons(dialog_y, menu_pulse_phase, selection_index)
    
    def _draw_side_by_side_buttons(
        self,
        dialog_y: int,
        menu_pulse_phase: float,
        selection_index: int
    ) -> None:
        """Draw buttons side by side."""
        button_y = dialog_y + 150
        
        # Confirm button (left)
        confirm_button = Button(
            self.confirm_label,
            (config.SCREEN_WIDTH // 2 - 120, button_y),
            self.button_font,
            width=180,
            height=50
        )
        confirm_button.selected = selection_index == 0
        confirm_button.draw(self.screen, menu_pulse_phase)
        
        # A button icon on the left
        icon_x = confirm_button.position[0] - confirm_button.width // 2 - 43
        ControllerIcon.draw_a_button(
            self.screen,
            (icon_x, button_y),
            size=30,
            selected=selection_index == 0
        )
        
        # Confirm button hint
        confirm_hint = self.hint_font.render("Enter/A", True, config.COLOR_TEXT)
        confirm_hint_rect = confirm_hint.get_rect(
            center=(config.SCREEN_WIDTH // 2 - 120, button_y + 50)
        )
        self.screen.blit(confirm_hint, confirm_hint_rect)
        
        # Cancel button (right)
        cancel_button = Button(
            self.cancel_label,
            (config.SCREEN_WIDTH // 2 + 120, button_y),
            self.button_font,
            width=180,
            height=50
        )
        cancel_button.selected = selection_index == 1
        cancel_button.draw(self.screen, menu_pulse_phase)
        
        # B button icon on the left
        icon_x = cancel_button.position[0] - cancel_button.width // 2 - 43
        ControllerIcon.draw_b_button(
            self.screen,
            (icon_x, button_y),
            size=30,
            selected=selection_index == 1
        )
        
        # Cancel button hint
        cancel_hint = self.hint_font.render("ESC/B", True, config.COLOR_TEXT)
        cancel_hint_rect = cancel_hint.get_rect(
            center=(config.SCREEN_WIDTH // 2 + 120, button_y + 50)
        )
        self.screen.blit(cancel_hint, cancel_hint_rect)
    
    def _draw_stacked_buttons(
        self,
        dialog_y: int,
        menu_pulse_phase: float,
        selection_index: int
    ) -> None:
        """Draw buttons stacked vertically."""
        button_y = dialog_y + 150
        
        # Confirm button (top)
        confirm_button = Button(
            self.confirm_label,
            (config.SCREEN_WIDTH // 2, button_y),
            self.button_font,
            width=400,
            height=50
        )
        confirm_button.selected = selection_index == 0
        confirm_button.draw(self.screen, menu_pulse_phase)
        
        # A button icon on the left
        icon_x = confirm_button.position[0] - confirm_button.width // 2 - 43
        ControllerIcon.draw_a_button(
            self.screen,
            (icon_x, button_y),
            size=30,
            selected=selection_index == 0
        )
        
        # Confirm button hint
        confirm_hint = self.hint_font.render("Enter/A/OK", True, config.COLOR_TEXT)
        confirm_hint_rect = confirm_hint.get_rect(
            center=(config.SCREEN_WIDTH // 2, button_y + 40)
        )
        self.screen.blit(confirm_hint, confirm_hint_rect)
        
        # Cancel button (bottom)
        cancel_button = Button(
            self.cancel_label,
            (config.SCREEN_WIDTH // 2, button_y + 100),
            self.button_font,
            width=400,
            height=50
        )
        cancel_button.selected = selection_index == 1
        cancel_button.draw(self.screen, menu_pulse_phase)
        
        # B button icon on the left
        icon_x = cancel_button.position[0] - cancel_button.width // 2 - 43
        ControllerIcon.draw_b_button(
            self.screen,
            (icon_x, button_y + 100),
            size=30,
            selected=selection_index == 1
        )
        
        # Cancel button hint
        cancel_hint = self.hint_font.render("ESC/B/Cancel", True, config.COLOR_TEXT)
        cancel_hint_rect = cancel_hint.get_rect(
            center=(config.SCREEN_WIDTH // 2, button_y + 140)
        )
        self.screen.blit(cancel_hint, cancel_hint_rect)

