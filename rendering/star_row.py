"""The five stars the player would get by reaching the exit now, drawn in the side panel during play."""
from typing import Sequence, Tuple

import pygame

from rendering.stars import draw_glow, draw_star

# Centre of the row in the side panel: above the level number
STAR_ROW_Y = 20
STAR_ROW_SIZE = 22
PAR_INDEX = 4
PULSE_GLOW = (255, 185, 45)


def draw_star_row(screen: pygame.Surface, flags: Sequence[bool], pulse: float,
                  center: Tuple[int, int], size: int) -> pygame.Rect:
    """Draw five stars in a row, lit or as outlines; pulse (0..1) makes the par star throb. Returns the row's rect."""
    spacing = round(size * 1.3)
    x0 = center[0] - 2 * spacing
    for i, lit in enumerate(flags):
        x = x0 + i * spacing
        if not lit:
            draw_star(screen, x, center[1], size, filled=False)
            continue
        flash = 0.0
        if i == PAR_INDEX and pulse > 0:
            draw_glow(screen, x, center[1], size * 2.2, PULSE_GLOW, pulse)
            flash = pulse * 0.6
        draw_star(screen, x, center[1], size, flash=flash)
    width = 4 * spacing + size
    return pygame.Rect(x0 - size // 2, center[1] - size // 2, width, size)
