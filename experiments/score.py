"""Scores hunter episodes and compares candidates with a paired bootstrap."""
from dataclasses import dataclass
import numpy as np

RATE_FLOOR_SECONDS = 20.0


@dataclass(frozen=True)
class Weights:
    # Chosen from the baseline run (docs/experiments/001-baseline.md); not changed during a comparison.
    wall: float = 4.4
    hit: float = 3.1
    idle: float = 76.0


def components(result):
    """Each term of the score on its own, so no gain can hide a loss."""
    minutes = max(result.elapsed, RATE_FLOOR_SECONDS) / 60.0
    idle = result.idle_seconds / result.elapsed if result.elapsed > 0 else 0.0
    return {'kills_per_min': result.kills / minutes,
            'wall_hits_per_min': result.wall_hits / minutes,
            'hits_taken_per_min': result.hits_taken / minutes,
            'idle_fraction': idle}


def score(result, weights=Weights()):
    c = components(result)
    return (c['kills_per_min'] - weights.wall * c['wall_hits_per_min']
            - weights.hit * c['hits_taken_per_min'] - weights.idle * c['idle_fraction'])


def mean_components(results, weights=Weights()):
    rows = [components(r) for r in results]
    mean = {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}
    mean['score'] = float(np.mean([score(r, weights) for r in results]))
    return mean


def paired_bootstrap(base, candidate, samples=2000, seed=0):
    """(mean difference, 2.5th, 97.5th percentile) of candidate - base over paired episodes."""
    base, candidate = np.asarray(base, dtype=float), np.asarray(candidate, dtype=float)
    if base.shape != candidate.shape or base.ndim != 1 or not len(base):
        raise ValueError('base and candidate must be equal-length, non-empty score lists')
    diffs = candidate - base
    rng = np.random.default_rng(seed)
    means = rng.choice(diffs, size=(samples, len(diffs)), replace=True).mean(axis=1)
    return (float(diffs.mean()), float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def improves(base, candidate, **kwargs):
    """True when the candidate beats the base by more than the noise (95% interval above zero)."""
    return paired_bootstrap(base, candidate, **kwargs)[1] > 0
