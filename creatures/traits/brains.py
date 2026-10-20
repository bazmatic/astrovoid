"""Brains: traits that decide a creature's controls each frame."""
from creatures.trait import Trait


class Still(Trait):
    """Wants nothing: sets no controls."""
    NAME = 'still'
