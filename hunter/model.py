"""Immutable values shared by the simulation and pilot worker."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PilotAction:
    turn: int
    thrust: bool
    fire: bool


NEUTRAL = PilotAction(0, False, False)
ACTIONS = {
    f'{name}_{"thrust" if thrust else "coast"}_{"fire" if fire else "hold"}':
        PilotAction(turn, thrust, fire)
    for name, turn in (("left", -1), ("none", 0), ("right", 1))
    for thrust in (False, True)
    for fire in (False, True)
}


@dataclass(frozen=True)
class HunterSettings:
    request_interval: float = 0.250
    action_ttl: float = 0.750
    thrust_multiplier: float = 0.25
    turn_rate_multiplier: float = 0.5
    decision_delay: float = 0.300
    request_timeout: float = 1.0
    sensor_cells: float = 4.0
    max_contacts: int = 24
    max_projectiles: int = 32
    max_memory_contacts: int = 32
    contact_ttl: float = 10.0
    health: int = 3
    indestructible: bool = True
    fire_interval: float = 0.250
    burst_size: int = 3
    burst_spacing: float = 0.050
    damage_immunity: float = 0.500


@dataclass(frozen=True)
class PilotObservation:
    generation: int
    snapshot_at: float
    state_json: str


@dataclass(frozen=True)
class PilotDecision:
    action: PilotAction
    confidence: Optional[float] = None


@dataclass(frozen=True)
class PilotResult:
    generation: int
    snapshot_at: float
    finished_at: float
    decision: Optional[PilotDecision] = None
    error: Optional[str] = None
    permanent: bool = False
