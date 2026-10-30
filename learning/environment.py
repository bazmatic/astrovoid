"""The training seam: numeric observations/actions; no game or learner implementation leaks through it."""
from dataclasses import dataclass
from typing import Protocol, Mapping
import numpy as np


@dataclass
class Snapshot:
    observations: Mapping[int, np.ndarray]
    masks: Mapping[int, dict]
    critic: np.ndarray
    agent_critics: Mapping[int, np.ndarray] | None = None


@dataclass
class Transition:
    snapshot: Snapshot
    reward: float
    terminated: bool
    truncated: bool
    events: dict
    agent_rewards: Mapping[int, float] | None = None


class Environment(Protocol):
    def reset(self, seed: int, **scenario) -> Snapshot: ...
    def step(self, actions: Mapping[int, tuple]) -> Transition: ...
    def close(self) -> None: ...
