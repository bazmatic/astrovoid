"""Reads the WINDOW_SIZE override (e.g. 1352x878) for windowed runs."""


def parse_window_size(text):
    """(width, height) from 'WxH', or None when the text is absent or not a size."""
    if not text:
        return None
    parts = text.lower().replace(' ', '').split('x')
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    width, height = int(parts[0]), int(parts[1])
    return (width, height) if width > 0 and height > 0 else None


# How much of the desktop a fitted window may take: macOS keeps a menu bar on top and often a Dock below
FIT_WIDTH = 0.95
FIT_HEIGHT = 0.9


def fit_window_size(wanted, desktop):
    """`wanted` (width, height), shrunk in proportion to fit inside the desktop with room to spare.

    A window that already fits, or a desktop of unknown size (None), leaves `wanted` as it is.
    """
    if not desktop:
        return wanted
    scale = min(1.0, desktop[0] * FIT_WIDTH / wanted[0], desktop[1] * FIT_HEIGHT / wanted[1])
    return (int(wanted[0] * scale), int(wanted[1] * scale)) if scale < 1.0 else wanted
