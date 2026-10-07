"""Controls screen: the key and button mappings, kept off the main menu."""

from typing import Dict, List, Optional, Tuple

import pygame
import config
from rendering.fonts import get_font
from rendering.menu_components import (
    AnimatedBackground, TEXT_DIM, TEXT_LABEL, build_menu_backdrop, build_panel, menu_scale,
    render_hint_row, render_pill, render_title
)

CONTROL_GROUPS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("KEYBOARD", [
        ("ARROWS / WASD", "Move"),
        ("SPACE", "Fire"),
        ("DOWN / S", "Shield"),
        ("ESC", "Quit level"),
        ("R", "Restart level"),
    ]),
    ("CONTROLLER", [
        ("STICKS", "Move"),
        ("R / ZR / B", "Fire"),
        ("A", "Shield"),
        ("L / ZL", "Thrust"),
        ("Y", "Restart level"),
    ]),
]


class ControlsMenu:
    """Shows one panel of mappings per input device."""

    def __init__(self, screen: pygame.Surface):
        """Initialize controls screen.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        self.scale = menu_scale()
        self.menu_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.backdrop = build_menu_backdrop(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.title = render_title(get_font(self._scaled(96)), "CONTROLS")
        self.group_font = get_font(self._scaled(30), bold=True)
        self.row_font = get_font(self._scaled(32), bold=False)
        self.hints = render_hint_row(get_font(self._scaled(28)), [("ESC / B", "Back")])
        self._panels: Optional[List[pygame.Surface]] = None

    def _scaled(self, value: float) -> int:
        """Scale a reference-layout length to the current screen size."""
        return max(1, int(round(value * self.scale)))

    def layout(self) -> Dict[str, object]:
        """Where each part of the screen sits: 'title', 'panels' (one rect per device) and 'hints'."""
        center_x = config.SCREEN_WIDTH // 2
        title = self.title.get_rect(center=(center_x, int(config.SCREEN_HEIGHT * 0.16)))
        
        rows = max(len(mappings) for _, mappings in CONTROL_GROUPS)
        panel_size = (self._scaled(500), self._scaled(96) + rows * self._scaled(62) + self._scaled(26))
        gap = self._scaled(40)
        total_width = panel_size[0] * len(CONTROL_GROUPS) + gap * (len(CONTROL_GROUPS) - 1)
        top = int(config.SCREEN_HEIGHT * 0.3)
        panels = [
            pygame.Rect(center_x - total_width // 2 + i * (panel_size[0] + gap), top, *panel_size)
            for i in range(len(CONTROL_GROUPS))
        ]
        hints = self.hints.get_rect(midbottom=(center_x, config.SCREEN_HEIGHT - self._scaled(56)))
        return {'title': title, 'panels': panels, 'hints': hints}

    def _render_panel(self, size: Tuple[int, int], name: str, mappings: List[Tuple[str, str]]) -> pygame.Surface:
        """Render one device's panel: its name, then a key pill and action per row."""
        panel = build_panel(size, radius=self._scaled(22)).copy()
        pad = self._scaled(36)
        
        heading = self.group_font.render(name, True, TEXT_LABEL)
        panel.blit(heading, heading.get_rect(midleft=(pad, self._scaled(50))))
        rule_y = self._scaled(84)
        pygame.draw.line(panel, (60, 56, 100), (pad, rule_y), (size[0] - pad, rule_y), max(1, self._scaled(2)))
        
        for i, (key_text, action_text) in enumerate(mappings):
            center_y = self._scaled(96) + i * self._scaled(62) + self._scaled(31)
            key = render_pill(self.row_font, key_text, padding=(self._scaled(14), self._scaled(6)), border=max(1, self._scaled(1.5)))
            panel.blit(key, key.get_rect(midleft=(pad, center_y)))
            action = self.row_font.render(action_text, True, TEXT_DIM)
            panel.blit(action, action.get_rect(midright=(size[0] - pad, center_y)))
        return panel

    def update(self, dt: float) -> None:
        """Update background animation."""
        self.menu_background.update(dt)

    def draw(self) -> None:
        """Draw the controls screen."""
        layout = self.layout()
        if self._panels is None:
            self._panels = [
                self._render_panel(rect.size, name, mappings)
                for rect, (name, mappings) in zip(layout['panels'], CONTROL_GROUPS)
            ]
        
        self.screen.blit(self.backdrop, (0, 0))
        self.menu_background.draw(self.screen)
        self.screen.blit(self.title, layout['title'])
        for panel, rect in zip(self._panels, layout['panels']):
            self.screen.blit(panel, rect)
        self.screen.blit(self.hints, layout['hints'])
