"""The EXIT block in the side panel: what the level's exit policy still needs, or OPEN."""
from typing import Sequence

import pygame

import config
from rendering.fonts import get_font

EXIT_PANEL_TOP = 716  # Just below the gun-upgrade bar in Ship.draw_ui, leaving room for the hunter gauge
LABEL_COLOR = (150, 160, 195)
SHUT_COLOR = (255, 150, 50)
LINE_GAP = 2


def draw_exit_panel(screen: pygame.Surface, lines: Sequence[str], is_open: bool,
                    top: int = EXIT_PANEL_TOP) -> pygame.Rect:
    """Draw the block and return the area it covers."""
    images = [get_font(16).render('EXIT', True, LABEL_COLOR)]
    if is_open:
        images.append(get_font(20).render('OPEN', True, config.COLOR_EXIT))
    else:
        images.extend(get_font(20).render(line, True, SHUT_COLOR) for line in lines)
    centre_x = config.UI_ZONE_WIDTH // 2
    widest = config.UI_ZONE_WIDTH - 24
    drawn = pygame.Rect(centre_x, top, 0, 0)
    y = top
    for image in images:
        if image.get_width() > widest:  # long names shrink to fit, as the score readings do
            ratio = widest / image.get_width()
            image = pygame.transform.smoothscale(image, (widest, max(1, round(image.get_height() * ratio))))
        rect = screen.blit(image, image.get_rect(midtop=(centre_x, y)))
        drawn.union_ip(rect)
        y = rect.bottom + LINE_GAP
    return drawn
