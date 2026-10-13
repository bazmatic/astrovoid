"""Scores hunter episodes and compares candidates with a paired bootstrap."""
from dataclasses import dataclass
import numpy as np

# Episodes shorter than this are rated as if they took this long, so a very quick clear cannot
# produce an extreme rate.
RATE_FLOOR_SECONDS = 45.0

# Points lost per unit of wall collision quotient per minute (one unit is a hit that takes the hunter's full top
# speed). Set from the student's own collisions (a typical hit takes about 0.33), so a typical hit costs about
# what the old 3.4 per hit did.
QUOTIENT_WEIGHT = 10.0


@dataclass(frozen=True)
class Weights:
    # Chosen from the baseline run (docs/experiments/001-baseline.md); not changed during a comparison.
    wall: float = 3.4          # per wall hit: only the rules-pilot lab uses it; the score uses `quotient`
    quotient: float = QUOTIENT_WEIGHT
    hit: float = 3.5
    idle: float = 77.0


def components(result):
    """Each term of the score on its own, so no gain can hide a loss."""
    minutes = max(result.elapsed, RATE_FLOOR_SECONDS) / 60.0
    idle = result.idle_seconds / result.elapsed if result.elapsed > 0 else 0.0
    # The share of every enemy that existed (those at the start and those that spawned) killed
    # per minute, so a level that keeps spawning enemies cannot be farmed for a bigger number.
    total = result.enemies_at_start + result.enemies_spawned
    return {'kill_pct_per_min': 100.0 * result.kills / total / minutes if total else 0.0,
            'kills_per_min': result.kills / minutes,
            'wall_hits_per_min': result.wall_hits / minutes,
            'wall_quotient_per_min': result.wall_impulse / minutes,
            'hits_taken_per_min': result.hits_taken / minutes,
            'idle_fraction': idle}


def score(result, weights=Weights()):
    c = components(result)
    return (c['kill_pct_per_min'] - weights.quotient * c['wall_quotient_per_min']
            - weights.hit * c['hits_taken_per_min'] - weights.idle * c['idle_fraction'])


def mean_components(results, weights=Weights()):
    rows = [components(r) for r in results]
    mean = {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}
    mean['score'] = float(np.mean([score(r, weights) for r in results]))
    return mean


def paired_bootstrap(base, candidate, samples=2000, seed=0, level=0.95):
    """(mean difference, lower, upper) of candidate - base over paired episodes, at `level`."""
    if not 0.0 < level < 1.0:
        raise ValueError('level must be between 0 and 1')
    base, candidate = np.asarray(base, dtype=float), np.asarray(candidate, dtype=float)
    if base.shape != candidate.shape or base.ndim != 1 or not len(base):
        raise ValueError('base and candidate must be equal-length, non-empty score lists')
    diffs = candidate - base
    rng = np.random.default_rng(seed)
    means = rng.choice(diffs, size=(samples, len(diffs)), replace=True).mean(axis=1)
    tail = 100.0 * (1.0 - level) / 2.0
    return (float(diffs.mean()), float(np.percentile(means, tail)),
            float(np.percentile(means, 100.0 - tail)))


def improves(base, candidate, **kwargs):
    """True when the candidate beats the base by more than the noise (interval above zero)."""
    return paired_bootstrap(base, candidate, **kwargs)[1] > 0
