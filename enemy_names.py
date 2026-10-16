"""What the player reads for each kind of enemy. Internal names (level files, code, tests) never change."""
from typing import Dict, Tuple

from level_layout import ENEMY_TYPES

# Babies hatch from eggs and are never placed, but the exit can still wait for them
KINDS: Tuple[str, ...] = ENEMY_TYPES + ('baby',)

ENEMY_NAMES: Dict[str, Tuple[str, str]] = {
    'static': ('Urchin', 'Urchins'),
    'patrol': ('Crab', 'Crabs'),
    'aggressive': ('Jelly', 'Jellies'),
    'replay': ('Squiddler', 'Squiddlers'),
    'flocker': ('Flocker', 'Flockers'),
    'flighthouse': ('Flighthouse', 'Flighthouses'),
    'egg': ('Egg', 'Eggs'),
    'baby': ('Squidlet', 'Squidlets'),
    'anemone': ('Anemone', 'Anemones'),
    'split_boss': ('Squiddler Boss', 'Squiddler Bosses'),
    'mother_boss': ('Mother', 'Mothers'),
    'rules_hunter': ('Terminator', 'Terminators'),
    'neural_hunter': ('Viber', 'Vibers'),
    'boss_viber': ('Boss Viber', 'Boss Vibers'),
    'vibelet': ('Vibelet', 'Vibelets'),
}


def name(kind: str) -> str:
    """The display name of one enemy of this kind."""
    return ENEMY_NAMES[kind][0]


def plural(kind: str) -> str:
    """The display name of several enemies of this kind."""
    return ENEMY_NAMES[kind][1]
