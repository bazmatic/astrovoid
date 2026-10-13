"""Describes a neural student for the lab: which weights, how often it decides, how fast it turns."""
import functools
from dataclasses import dataclass
from hunter.neural.loader import load_neural_policy


@dataclass(frozen=True)
class StudentSpec:
    weights: str
    decision_frames: int = 6
    turn_rate: float = 1.0
    greedy: bool = True
    sample_seed: int = 0          # seeds the sampling generator when greedy is False


@functools.lru_cache(maxsize=8)
def load_policy(spec):
    """The spec's policy (None if the file is missing or invalid), loaded once per process."""
    return load_neural_policy(spec.weights)
