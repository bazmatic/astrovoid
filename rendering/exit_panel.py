"""The EXIT block in the side panel: what the level's exit policy still needs, or OPEN."""
from typing import List, Optional, Sequence

import pygame

import config
from rendering.fonts import get_font

EXIT_PANEL_TOP = 716  # Just below the gun-upgrade bar in Ship.draw_ui, leaving room for the hunter gauge
LABEL_COLOR = (150, 160, 195)
SHUT_COLOR = (255, 150, 50)
LINE_GAP = 2


def draw_exit_panel(screen: pygame.Surface, lines: Sequence[str], is_open: bool,
                    top: Optional[int] = None, bottom: Optional[int] = None) -> pygame.Rect:
    """Draw the block and return the area it covers. Long lists of names wrap when there is room above
    `bottom`, and otherwise shrink onto one line."""
    if top is None:
        top = round(EXIT_PANEL_TOP * min(1.0, screen.get_height() / 878))
    bottom = min(screen.get_height(), bottom) if bottom is not None else screen.get_height()
    widest = config.UI_ZONE_WIDTH - 24
    label = get_font(16).render('EXIT', True, LABEL_COLOR)
    font = get_font(20)
    if is_open:
        texts, colour = ['OPEN'], config.COLOR_EXIT
    else:
        texts, colour = list(lines), SHUT_COLOR
        wrapped = [part for line in lines for part in _wrap(font, line, widest)]
        height = label.get_height() + len(wrapped) * (font.get_height() + LINE_GAP)
        if bottom is None or top + height <= bottom:
            texts = wrapped
    images = [label] + [_fit(font.render(text, True, colour), widest) for text in texts]
    height = sum(image.get_height() for image in images) + LINE_GAP * (len(images) - 1)
    top = max(0, min(top, bottom - height))
    centre_x = config.UI_ZONE_WIDTH // 2
    drawn = pygame.Rect(centre_x, top, 0, 0)
    y = top
    for image in images:
        rect = screen.blit(image, image.get_rect(midtop=(centre_x, y)))
        drawn.union_ip(rect)
        y = rect.bottom + LINE_GAP
    return drawn


def _fit(image: pygame.Surface, widest: int) -> pygame.Surface:
    """Shrink a line too wide for the panel, as the score readings do."""
    if image.get_width() <= widest:
        return image
    ratio = widest / image.get_width()
    return pygame.transform.smoothscale(image, (widest, max(1, round(image.get_height() * ratio))))


def _wrap(font: pygame.font.Font, line: str, width: int) -> List[str]:
    """Break a list of names after its commas so each part fits; a single name too wide is left to shrink."""
    parts: List[str] = []
    for name in line.split(', '):
        joined = f'{parts[-1]} {name}' if parts else name
        if parts and font.size(joined + ',')[0] <= width:
            parts[-1] = joined
        else:
            parts.append(name)
        parts[-1] += ','
    parts[-1] = parts[-1][:-1]
    return parts
