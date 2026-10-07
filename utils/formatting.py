"""Display formatting shared by record screens."""

def format_time(seconds: float) -> str:
    """Match stored tenths, including a carry across the minute boundary."""
    tenths = round(seconds * 10)
    minutes, remainder = divmod(tenths, 600)
    whole_seconds, fraction = divmod(remainder, 10)
    return f"{minutes:02d}:{whole_seconds:02d}.{fraction}"


