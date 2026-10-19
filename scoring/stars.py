"""The five stars a level gives, from what the player did.

Each star is earned on its own: taking no hits, killing half the enemies,
killing every enemy, collecting every crystal, and finishing inside par. A level
that isn't finished gives none.
"""

from dataclasses import dataclass
from typing import Sequence, Tuple

STAR_NAMES = ('no_hits', 'half_enemies', 'every_enemy', 'every_crystal', 'par')


@dataclass(frozen=True)
class StarTally:
    """What happened on a level, as far as the stars care."""

    kills: int
    alive: int
    crystals_collected: int
    crystals_left: int
    play_seconds: float
    par_seconds: float
    hits: int = 0  # Enemy bullets and enemies that struck the ship


def earned(tally: StarTally) -> Tuple[bool, bool, bool, bool, bool]:
    """Which of the five stars the tally earns, in STAR_NAMES order."""
    half = tally.kills * 2 >= tally.kills + tally.alive
    return (
        tally.hits == 0,
        half,
        tally.alive == 0,
        tally.crystals_left == 0,
        tally.play_seconds <= tally.par_seconds,
    )


def star_count(flags: Sequence[bool]) -> int:
    """The number of stars lit."""
    return sum(1 for flag in flags if flag)


def format_clock(seconds: float) -> str:
    """Seconds as m:ss, rounded down."""
    whole = int(max(0.0, seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def describe(tally: StarTally) -> Tuple[str, str, str, str, str]:
    """One short line per star saying what it was for and how close it came."""
    total_enemies = tally.kills + tally.alive
    total_crystals = tally.crystals_collected + tally.crystals_left
    return (
        'NO HITS' if tally.hits == 0 else f"{tally.hits} HIT{'S' if tally.hits > 1 else ''}",
        f"{tally.kills}/{total_enemies} KILLED",
        'NONE LEFT' if tally.alive == 0 else f"{tally.alive} LEFT",
        'NO CRYSTALS' if total_crystals == 0 else f"{tally.crystals_collected}/{total_crystals} CRYSTALS",
        f"{format_clock(tally.play_seconds)} / PAR {format_clock(tally.par_seconds)}",
    )
