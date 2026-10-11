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
