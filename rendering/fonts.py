"""The game's typeface.

Chakra Petch is bundled in assets/fonts (SIL Open Font License). Every piece
of text in the game should get its font from get_font so the look stays
consistent.
"""

from typing import Dict, Optional, Tuple

import pygame
from utils.resource_path import resource_path

BOLD_PATH = "assets/fonts/ChakraPetch-Bold.ttf"
SEMIBOLD_PATH = "assets/fonts/ChakraPetch-SemiBold.ttf"

# Sizes throughout the game were chosen for pygame's built-in font, whose
# letters are small for their nominal size. Scaling here keeps text the same
# visual size without touching every caller
SIZE_SCALE = 0.8
# Small text reads better a little lighter; headings and buttons take the bold cut
BOLD_FROM_SIZE = 30

_fonts: Dict[Tuple[int, bool], pygame.font.Font] = {}
_quit_hook_registered = False


def _forget_fonts() -> None:
    """Drop cached fonts when pygame shuts down; using one afterwards crashes the interpreter."""
    global _quit_hook_registered
    _fonts.clear()
    _quit_hook_registered = False


def get_font(size: int, bold: Optional[bool] = None) -> pygame.font.Font:
    """Get the game font at a size given in the built-in font's units.

    Args:
        size: Nominal size, as you would pass to pygame.font.Font(None, size).
        bold: Force the bold or semi-bold cut; by default chosen from the size.

    Returns:
        A cached font. Falls back to pygame's built-in font if the files are missing.
    """
    size = int(size)
    if bold is None:
        bold = size >= BOLD_FROM_SIZE
    global _quit_hook_registered
    if not pygame.font.get_init():
        _fonts.clear()
        pygame.font.init()
    if not _quit_hook_registered:
        pygame.register_quit(_forget_fonts)
        _quit_hook_registered = True
    key = (size, bold)
    if key not in _fonts:
        try:
            font = pygame.font.Font(resource_path(BOLD_PATH if bold else SEMIBOLD_PATH), max(1, round(size * SIZE_SCALE)))
        except (FileNotFoundError, OSError, pygame.error):
            font = pygame.font.Font(None, size)
        _fonts[key] = font
    return _fonts[key]
