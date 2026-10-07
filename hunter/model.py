"""Immutable values shared by the simulation and pilot worker."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PilotAction:
    turn: int
    thrust: bool
    fire: bool
    # Hand steering to fire control: the ship trims its nose onto the firing solution.
    track: bool = False
    # Hand steering and the length of the burn to the navigator: the ship swings its
    # nose onto burn_heading and thrusts only while lined up and only for burn_frames.
    course: bool = False
    # Heading the burn belongs to, in absolute degrees: the engine fires only while the
    # nose is near it. None means thrust goes wherever the nose points.
    burn_heading: Optional[float] = None
    # How many frames the engine may fire on this decision. None means until the next
    # decision replaces it.
    burn_frames: Optional[float] = None
    # The ship's count of thrust frames when the burn was worked out, so thrust applied
    # since then is not burned twice. None means the burn starts fresh.
    burn_reference: Optional[int] = None
    # The pilot asked for the worked burn: its heading and length are filled in from the
    # readings it chose on.
    worked_burn: bool = False


# A pulse: the shortest burn worth making, a tenth of a second.
PULSE_FRAMES = 6

NEUTRAL = PilotAction(0, False, False)
# The engine settings: coast, one short pulse, the worked burn, or held on.
ACTIONS = {
    f'{name}_{engine}_{"fire" if fire else "hold"}':
        PilotAction(turn, thrust, fire, track, course, burn_frames=burn_frames, worked_burn=worked)
    for name, turn, track, course in (
        ("left", -1, False, False), ("none", 0, False, False), ("right", 1, False, False),
        ("track", 0, True, False), ("course", 0, False, True))
    for engine, thrust, burn_frames, worked in (
        ("coast", False, None, False), ("pulse", True, PULSE_FRAMES, False),
        ("burn", True, None, True), ("thrust", True, None, False))
    for fire in (False, True)
}


@dataclass(frozen=True)
class FiringSolution:
    """Where the nose must point to hit the engaged enemy, and whether it already does."""
    lead_degrees: float  # Relative to the nose: negative left, positive right
    on_target: bool  # A shot along the present nose would hit


@dataclass(frozen=True)
class HunterSettings:
    request_interval: float = 0.250
    # A decision is held until the next one lands. Decisions run back to back,
    # so that is two round trips after its snapshot; this covers a slow 0.7 s pair.
    action_ttl: float = 1.500
    thrust_multiplier: float = 0.25
    turn_rate_multiplier: float = 0.5
    # How far ahead "at next decision" readings look: the measured median round trip.
    decision_delay: float = 0.450
    request_timeout: float = 1.0
    # How far the hunter sees, as a share of the maze's width. It is the same distance
    # on screen whatever the maze's cell size, so sight does not shrink in dense mazes.
    sensor_range_fraction: float = 0.4
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

    def sensor_range(self, maze) -> float:
        """How far the hunter sees in this maze, in pixels."""
        return self.sensor_range_fraction * maze.grid_width * maze.cell_size_x


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
