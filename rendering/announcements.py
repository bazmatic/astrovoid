"""Important announcements, such as the level's mission, shown in the centre of the playfield.

One announcement shows at a time: a small heading over a line or two of large text, on a soft dark panel so it reads
over rock and creatures. It fades in, stays until dismissed, then fades out. It is driven in frames, like the game, so
it waits while the game does.
"""
from typing import List, Optional, Tuple

import pygame

import config
from rendering.exit_panel import LABEL_COLOR
from rendering.fonts import get_font

FADE_IN_FRAMES = 12.0
FADE_OUT_FRAMES = 60.0
HEADING_SIZE = 26
TEXT_SIZE = 50
TEXT_COLOR = (255, 255, 255)
PANEL_COLOR = (8, 6, 24)
PANEL_ALPHA = 170
PADDING = (36, 22)  # px around the words, across and down
MARGIN = 40  # px kept clear at each side of the playfield
GAP = 10  # px between the heading and the text, and between lines of text


class Announcer:
    """Shows one announcement at a time in the centre of the playfield."""

    def __init__(self):
        self._message: Optional[Tuple[str, str]] = None
        self._strength = 0.0  # 0 (unseen) to 1 (full)
        self._leaving = False

    @property
    def showing(self) -> Optional[Tuple[str, str]]:
        """The heading and text on screen, fading or not; None when nothing is."""
        return self._message

    def show(self, heading: str, text: str) -> None:
        """Announce this, in place of whatever was showing; it stays until dismissed."""
        self._message = (heading, text)
        self._strength = 0.0
        self._leaving = False

    def dismiss(self) -> None:
        """Let the announcement fade away."""
        self._leaving = True

    def clear(self) -> None:
        """Remove the announcement at once."""
        self._message = None
        self._strength = 0.0
        self._leaving = False

    def update(self, dt: float) -> None:
        """Advance its fade by dt frames."""
        if self._message is None:
            return
        if self._leaving:
            self._strength -= dt / FADE_OUT_FRAMES
            if self._strength <= 0.0:
                self.clear()
        else:
            self._strength = min(1.0, self._strength + dt / FADE_IN_FRAMES)

    def draw(self, screen: pygame.Surface) -> None:
        if self._message is None or self._strength <= 0.0:
            return
        heading, text = self._message
        left = config.UI_ZONE_WIDTH if screen.get_width() > config.UI_ZONE_WIDTH * 2 else 0
        playfield = pygame.Rect(left, 0, screen.get_width() - left, screen.get_height())
        widest = playfield.width - 2 * (MARGIN + PADDING[0])
        text_font = get_font(TEXT_SIZE)
        images = [get_font(HEADING_SIZE).render(' '.join(heading), True, LABEL_COLOR)]
        images += [text_font.render(line, True, TEXT_COLOR) for line in _wrap(text_font, text, widest)]
        width = max(image.get_width() for image in images) + 2 * PADDING[0]
        height = sum(image.get_height() for image in images) + GAP * (len(images) - 1) + 2 * PADDING[1]
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((*PANEL_COLOR, round(PANEL_ALPHA * self._strength)))
        y = PADDING[1]
        for image in images:
            image.set_alpha(round(255 * self._strength))
            panel.blit(image, image.get_rect(midtop=(width // 2, y)))
            y += image.get_height() + GAP
        screen.blit(panel, panel.get_rect(center=playfield.center))


def _wrap(font: pygame.font.Font, text: str, width: int) -> List[str]:
    """Break text between words so each line fits; a single word too wide stays whole."""
    lines: List[str] = []
    for word in text.split():
        joined = f'{lines[-1]} {word}' if lines else word
        if lines and font.size(joined)[0] <= width:
            lines[-1] = joined
        else:
            lines.append(word)
    return lines
