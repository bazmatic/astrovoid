"""Main menu rendering.

This module handles the rendering of the main menu screen.
"""

import math
import pygame
from typing import List, Optional, Tuple
import config
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon, BUTTON_ACCENT_START
from rendering.visual_effects import create_radial_gradient_surface
from utils.resource_path import resource_path


# Layout is authored for a 1080px-high screen and scaled to the real height.
# REFERENCE_WIDTH is the narrowest screen that layout fits; narrower (e.g.
# portrait) screens scale down by width instead so nothing runs off the sides
REFERENCE_HEIGHT = 1080
REFERENCE_WIDTH = 1200
TITLE_HEIGHT_FRACTION = 0.34
TITLE_CENTER_Y_FRACTION = 0.23
TITLE_FLOAT_SPEED = 0.9

CONTROL_ROWS = [
    ("KEYBOARD", [("ARROWS / WASD", "Move"), ("SPACE", "Fire"), ("DOWN / S", "Shield")]),
    ("CONTROLLER", [("STICKS", "Move"), ("R / ZR / B", "Fire"), ("A", "Shield"), ("L / ZL", "Thrust")]),
]


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
        self.menu_options = ["START GAME", "SELECT PROFILE", "OPTIONS", "QUIT"]
        self.menu_buttons: list[Button] = []
        self.menu_selected_index = 0
        self.menu_pulse_phase = 0.0
        self.profile_name: Optional[str] = None
        self.profile_level: Optional[int] = None
        self.scale = min(config.SCREEN_HEIGHT / REFERENCE_HEIGHT, config.SCREEN_WIDTH / REFERENCE_WIDTH)
        self.profile_font = pygame.font.Font(None, self._scaled(28))
        self.menu_time = 0.0
        self.backdrop: Optional[pygame.Surface] = None
        self.controls_surface: Optional[pygame.Surface] = None
        self.profile_badge: Optional[pygame.Surface] = None
        self._profile_badge_key: Optional[Tuple[Optional[str], Optional[int]]] = None
        self._initialize()
    
    def _scaled(self, value: float) -> int:
        """Scale a reference-layout length to the current screen size."""
        return max(1, int(round(value * self.scale)))
    
    def _initialize(self) -> None:
        """Initialize menu UI components."""
        # Create animated background
        self.menu_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        self.backdrop = self._build_backdrop()
        
        # Load title graphic
        title_center = (config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * TITLE_CENTER_Y_FRACTION))
        try:
            title_image = pygame.image.load(resource_path("assets/title.png")).convert_alpha()
            # Scale title image with the layout (maintain aspect ratio)
            title_height = self._scaled(REFERENCE_HEIGHT * TITLE_HEIGHT_FRACTION)
            title_width = int(title_image.get_width() * title_height / title_image.get_height())
            max_title_width = self._scaled(REFERENCE_WIDTH - 96)
            if title_width > max_title_width:
                title_height = round(title_height * max_title_width / title_width)
                title_width = max_title_width
            self.menu_title_image = pygame.transform.smoothscale(title_image, (title_width, title_height))
            self.menu_title_rect = self.menu_title_image.get_rect(center=title_center)
            # Soft halo behind the title, baked into the static backdrop
            halo = create_radial_gradient_surface(
                (int(title_width * 1.5), int(title_height * 1.5)),
                (110, 60, 220),
                90
            )
            self.backdrop.blit(halo, halo.get_rect(center=title_center))
        except (pygame.error, FileNotFoundError):
            # Fallback to text if image not found
            title_font = pygame.font.Font(None, self._scaled(config.FONT_SIZE_TITLE * 2))
            self.menu_title = NeonText(
                "SQUIDDLER",
                title_font,
                title_center,
                config.COLOR_NEON_ASTER_START,
                config.COLOR_NEON_VOID_END,
                center=True
            )
            self.menu_title_image = None
        
        # Create buttons for all menu options
        button_font = pygame.font.Font(None, self._scaled(40))
        self.menu_buttons = []
        
        # Position buttons in a group beneath the title
        start_y = int(config.SCREEN_HEIGHT * 0.5)
        button_spacing = self._scaled(84)
        
        for i, option_text in enumerate(self.menu_options):
            button = Button(
                option_text,
                (config.SCREEN_WIDTH // 2, start_y + i * button_spacing),
                button_font,
                width=self._scaled(440),
                height=self._scaled(64)
            )
            button.selected = (i == self.menu_selected_index)
            self.menu_buttons.append(button)
        
        self.backdrop = self.backdrop.convert()
        self.controls_surface = self._build_controls_surface()
    
    def _build_backdrop(self) -> pygame.Surface:
        """Build the static backdrop: nebula tint and vignette over the background color."""
        width, height = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        # Composed without an alpha channel and converted afterwards so every
        # pixel is opaque. The display surface can carry alpha, and pygame
        # copies rather than blends per-pixel-alpha surfaces onto pixels whose
        # alpha is 0, which would turn everything drawn on top into solid blocks
        backdrop = pygame.Surface((width, height), 0, 24)
        backdrop.fill(config.COLOR_BACKGROUND)
        
        # Nebula clouds as (color, alpha, center fraction, size fraction)
        clouds = [
            ((90, 40, 170), 70, (0.5, 0.42), (1.1, 1.2)),
            ((30, 90, 190), 45, (0.24, 0.2), (0.8, 0.9)),
            ((190, 50, 150), 40, (0.8, 0.78), (0.8, 0.9)),
        ]
        for color, alpha, center, size in clouds:
            cloud = create_radial_gradient_surface((int(width * size[0]), int(height * size[1])), color, alpha)
            backdrop.blit(cloud, cloud.get_rect(center=(int(width * center[0]), int(height * center[1]))))
        
        vignette = create_radial_gradient_surface((width, height), (0, 0, 0), 0, edge_alpha=150, falloff=0.6)
        backdrop.blit(vignette, (0, 0))
        return backdrop
    
    def _render_pill(
        self,
        text: str,
        text_color: Tuple[int, int, int],
        outline_color: Tuple[int, int, int],
        padding: Tuple[int, int]
    ) -> pygame.Surface:
        """Render text inside an outlined pill."""
        text_surface = self.profile_font.render(text, True, text_color)
        pill = pygame.Surface(
            (text_surface.get_width() + padding[0] * 2, text_surface.get_height() + padding[1] * 2),
            pygame.SRCALPHA
        )
        radius = pill.get_height() // 2
        border = max(1, self._scaled(1.5))
        pygame.draw.rect(pill, (*outline_color, 255), pill.get_rect(), border_radius=radius)
        pygame.draw.rect(pill, (24, 20, 48, 200), pill.get_rect().inflate(-border * 2, -border * 2), border_radius=radius - border)
        pill.blit(text_surface, text_surface.get_rect(center=pill.get_rect().center))
        return pill
    
    def _build_controls_surface(self) -> pygame.Surface:
        """Build the static controls legend: one row of key hints per input device."""
        label_gap = self._scaled(22)
        action_gap = self._scaled(9)
        hint_gap = self._scaled(28)
        row_gap = self._scaled(12)
        key_padding = (self._scaled(10), self._scaled(5))
        
        # Each row is a label followed by (x offset within the row, surface) pieces
        rows: List[Tuple[pygame.Surface, List[Tuple[int, pygame.Surface]]]] = []
        label_width = 0
        hints_width = 0
        row_height = 0
        for label, hints in CONTROL_ROWS:
            label_surface = self.profile_font.render(label, True, (110, 120, 170))
            label_width = max(label_width, label_surface.get_width())
            pieces: List[Tuple[int, pygame.Surface]] = []
            x = 0
            for key_text, action_text in hints:
                key_surface = self._render_pill(key_text, (210, 225, 255), (90, 110, 170), key_padding)
                action_surface = self.profile_font.render(action_text, True, (160, 160, 185))
                pieces.append((x, key_surface))
                x += key_surface.get_width() + action_gap
                pieces.append((x, action_surface))
                x += action_surface.get_width() + hint_gap
                row_height = max(row_height, key_surface.get_height())
            hints_width = max(hints_width, x - hint_gap)
            rows.append((label_surface, pieces))
        
        surface = pygame.Surface(
            (label_width + label_gap + hints_width, row_height * len(rows) + row_gap * (len(rows) - 1)),
            pygame.SRCALPHA
        )
        for i, (label_surface, pieces) in enumerate(rows):
            center_y = i * (row_height + row_gap) + row_height // 2
            # Labels are right-aligned so the key hints share a left edge
            surface.blit(label_surface, label_surface.get_rect(midright=(label_width, center_y)))
            for x, piece in pieces:
                surface.blit(piece, piece.get_rect(midleft=(label_width + label_gap + x, center_y)))
        return surface
    
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
        self.menu_time += dt / 60.0
        # Update pulse phase for button glow
        self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
        if self.menu_pulse_phase >= 2 * 3.14159:
            self.menu_pulse_phase -= 2 * 3.14159
    
    def draw(self) -> None:
        """Draw main menu with animated background and neon effects."""
        # Draw backdrop and animated background
        if self.backdrop:
            self.screen.blit(self.backdrop, (0, 0))
        if self.menu_background:
            self.menu_background.draw(self.screen)
        
        # Draw title graphic (gently floating) or neon text fallback
        if self.menu_title_image is not None:
            float_phase = self.menu_time * TITLE_FLOAT_SPEED
            title_rect = self.menu_title_rect.move(0, int(math.sin(float_phase) * self._scaled(6)))
            self.screen.blit(self.menu_title_image, title_rect)
        elif self.menu_title:
            self.menu_title.draw(self.screen)
        
        # Draw buttons
        for i, button in enumerate(self.menu_buttons):
            button.selected = (i == self.menu_selected_index)
            button.draw(self.screen, self.menu_pulse_phase)
        
        # Draw controls legend at bottom
        controls_rect = self.controls_surface.get_rect(
            midbottom=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT - self._scaled(48))
        )
        self.screen.blit(self.controls_surface, controls_rect)

        # Draw profile badge above controls
        if self.profile_name:
            badge_key = (self.profile_name, self.profile_level)
            if self.profile_badge is None or self._profile_badge_key != badge_key:
                self.profile_badge = self._render_pill(
                    f"{self.profile_name.upper()}   \u00b7   LEVEL {self.profile_level or '-'}",
                    (215, 225, 255),
                    BUTTON_ACCENT_START,
                    (self._scaled(20), self._scaled(8))
                )
                self._profile_badge_key = badge_key
            badge_rect = self.profile_badge.get_rect(
                midbottom=(config.SCREEN_WIDTH // 2, controls_rect.top - self._scaled(24))
            )
            self.screen.blit(self.profile_badge, badge_rect)

    def set_profile_info(self, name: Optional[str], level: Optional[int]) -> None:
        """Update the profile info shown on the menu."""
        self.profile_name = name
        self.profile_level = level

