"""The numbers the rules hunter is tuned by. Defaults are the game's current values."""
from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True)
class RuleParams:
    steer_band_degrees: float = 20.0  # Within this of the nose, hold no steering
    engage_standoff_cells: float = 1.5  # The distance the hunter fights from, in maze cells
    too_close_ratio: float = 0.6  # Closer than this share of the standoff is too close
    far_ratio: float = 1.15  # Further than this multiple of the standoff is far
    harmless_speed: float = 15.0  # m/s below which a wall brush is harmless
    wall_follow_cruise: float = 0.6  # Share of the wall-following cruise speed
    course_approach_fraction: float = 0.7  # Share of the speed limit a course holds at
    cruising_speed_fraction: float = 0.5  # Share of the safe speed that counts as cruising
    pulse_frames: float = 6.0  # Length of one engine pulse, in frames
    # Structural switches: whole rules that are off until an experiment shows they help.
    pursue_unaimed: bool = False  # Close in on a visible enemy that cannot yet be shot at
    investigate_memory: bool = False  # Head for where a remembered enemy was last seen

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in fields(cls)}
        values = {}
        for name, value in data.items():
            if name not in known:
                raise ValueError(f'unknown rule parameter {name!r}')
            if name in SWITCHES:
                if not isinstance(value, bool):
                    raise ValueError(f'rule switch {name!r} must be true or false, got {value!r}')
                values[name] = value
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'rule parameter {name!r} must be a number, got {value!r}')
            low, high = BOUNDS[name]
            if not low <= value <= high:
                raise ValueError(f'rule parameter {name!r}={value} is outside {low}..{high}')
            values[name] = float(value)
        return cls(**values)


DEFAULT = RuleParams()
# The rules pilot's own defaults: DEFAULT plus the structural rules experiments have adopted
# (docs/experiments). Jev and the student keep DEFAULT.
RULES = replace(DEFAULT, investigate_memory=True)

SWITCHES = ('pursue_unaimed', 'investigate_memory')

# The ranges the search may explore, and the limits from_dict accepts.
BOUNDS = {
    'steer_band_degrees': (2.0, 60.0),
    'engage_standoff_cells': (0.5, 4.0),
    'too_close_ratio': (0.2, 0.95),
    'far_ratio': (1.0, 2.5),
    'harmless_speed': (2.0, 60.0),
    'wall_follow_cruise': (0.2, 1.2),
    'course_approach_fraction': (0.3, 1.0),
    'cruising_speed_fraction': (0.1, 0.9),
    'pulse_frames': (1.0, 20.0),
}
