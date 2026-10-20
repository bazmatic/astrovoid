"""Every Enemy Kind, as config/enemies.json describes it: what the player calls it, how it behaves in the maze, and its
own tuning.

The kinds come in the file's order, which is the order the editor palette and the level counts use. A kind's key
(`static`, `patrol`, ...) is its internal name: level files, code and tests use it, and it never changes. The display
names are for the player.

The file is read strictly: a missing or unknown field stops the game at startup rather than leaving a kind half made.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from utils.resource_path import resource_path

PAR_WEIGHTS = ('enemy', 'spawningBoss')
PILOTS = ('rules', 'neural')


@dataclass(frozen=True)
class HunterStats:
    """What sets one enemy hunter apart from another flown by the same pilot."""
    hit_points: int
    size_scale: float      # its radius (and so its drawing and collisions) as a share of a normal ship's
    shot_strength: float   # what its shots cost the player, as a share of a full shot
    shows_hit_points: bool  # whether it carries a bar above it of the hits it has left


@dataclass(frozen=True)
class EnemyKind:
    key: str
    name: str
    plural: str
    anchored: bool         # never moves, so a gate's plank must not cover it and it jams the gates it touches
    replays_player: bool   # flies the player's recorded moves, so it needs the command recorder
    par_weight: str        # the par allowance it earns: an ordinary enemy's or a spawning boss's
    spawn_radius: float    # how far it reaches at its largest: where it is placed must be that open (0: its centre)
    pilot: Optional[str] = None             # an enemy hunter's pilot; None for every other kind
    hunter: Optional[HunterStats] = None    # an enemy hunter's own numbers
    tuning: Mapping[str, Any] = field(default_factory=dict)   # settings only this kind's own code reads


_COMMON = {'name', 'anchored', 'replaysPlayer', 'parWeight', 'spawnRadius'}
_HUNTER = {'pilot', 'hitPoints', 'sizeScale', 'shotStrength', 'showsHitPoints'}


def _parse(key: str, raw: Dict[str, Any]) -> EnemyKind:
    is_hunter = 'pilot' in raw
    required = _COMMON | (_HUNTER if is_hunter else {'tuning'})
    missing, unknown = required - set(raw), set(raw) - required
    if missing or unknown:
        raise ValueError(f'enemy kind {key!r}: missing {sorted(missing)}, unknown {sorted(unknown)}')
    singular, plural = raw['name']
    if raw['parWeight'] not in PAR_WEIGHTS:
        raise ValueError(f'enemy kind {key!r}: parWeight must be one of {PAR_WEIGHTS}')
    hunter = None
    if is_hunter:
        if raw['pilot'] not in PILOTS:
            raise ValueError(f'enemy kind {key!r}: pilot must be one of {PILOTS}')
        hunter = HunterStats(raw['hitPoints'], raw['sizeScale'], raw['shotStrength'], raw['showsHitPoints'])
    return EnemyKind(key=key, name=singular, plural=plural, anchored=raw['anchored'],
                     replays_player=raw['replaysPlayer'], par_weight=raw['parWeight'],
                     spawn_radius=float(raw['spawnRadius']), pilot=raw.get('pilot'), hunter=hunter,
                     tuning=raw.get('tuning', {}))


def load(path: Optional[str] = None) -> Dict[str, EnemyKind]:
    """The catalogue in a file (by default config/enemies.json), by key, in the file's order."""
    with Path(path or resource_path('config/enemies.json')).open('r', encoding='utf-8') as fh:
        raw = json.load(fh)
    return {key: _parse(key, entry) for key, entry in raw.items()}


_CATALOGUE = load()


def kind(key: str) -> EnemyKind:
    """The kind with this key; a KeyError names a kind the catalogue does not have."""
    return _CATALOGUE[key]


def kinds() -> Tuple[str, ...]:
    """Every kind's key, in the catalogue's order. Every kind can be placed in a level."""
    return tuple(_CATALOGUE)


def anchored() -> Tuple[str, ...]:
    """The kinds that never move."""
    return tuple(k for k, entry in _CATALOGUE.items() if entry.anchored)


def hunters() -> Tuple[str, ...]:
    """The kinds flown by a pilot, which the game makes itself (they need a pilot and a view of the game)."""
    return tuple(k for k, entry in _CATALOGUE.items() if entry.pilot is not None)


def name(key: str) -> str:
    """The display name of one enemy of this kind."""
    return _CATALOGUE[key].name


def plural(key: str) -> str:
    """The display name of several enemies of this kind."""
    return _CATALOGUE[key].plural
