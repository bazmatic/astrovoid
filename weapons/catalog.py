"""Validated immutable weapon tuning. Stable IDs are also the replay format."""
from dataclasses import asdict, dataclass, replace
import math
import config

RULESET = 'weapon-inventory-v2'
REPLACEMENT_RULESET = 'weapon-pickups-v1'
PICKUP_RULESETS = (RULESET, REPLACEMENT_RULESET)
LEGACY_RULESET = 'legacy'

@dataclass(frozen=True)
class WeaponDefinition:
    id: str
    name: str
    capacity: int | None
    interval: float  # simulation frames
    color: tuple
    symbol: str
    behaviour: str = 'bolt'
    speed: float = 1.0  # multiple of configured base projectile speed
    lifetime: float = 90.0
    offsets: tuple = ((0.0, 0.0),)  # (sideways muzzle offset, angle offset)
    damage: int = 1
    radius: float = 0.0  # zero uses base projectile radius
    blast_radius: float = 60.0
    blast_push: float = 6.0
    wall_hits: int = 1
    restitution: float = 0.7
    turn_rate: float = 4.0  # degrees per frame
    seek_range: float = 500.0
    seek_cone: float = 70.0
    drop_weight: float = 1.0
    base_speed: float = config.PROJECTILE_SPEED
    base_radius: float = config.PROJECTILE_SIZE
    sound_pitch: float = 950.0
    sound_duration: float = .1
    sound_profile: str = 'tone'
    sound_body: float = 0.0
    proximity_radius: float = 0.0
    inflation_seconds: float = 0.0
    inflation_scale: float = 1.0

class WeaponCatalog:
    def __init__(self, definitions):
        self._definitions = {}
        for d in definitions:
            d = replace(d, color=tuple(d.color), offsets=tuple(tuple(pair) for pair in d.offsets))
            if d.id in self._definitions or not d.id or d.interval <= 0 or not math.isfinite(d.interval):
                raise ValueError('invalid or duplicate weapon definition')
            if d.capacity is not None and (type(d.capacity) is not int or d.capacity <= 0):
                raise ValueError('weapon capacity must be a positive integer')
            from weapons.projectile import PROJECTILE_TYPES
            if d.behaviour not in PROJECTILE_TYPES and d.behaviour != 'shield':
                raise ValueError('unknown projectile behaviour')
            from sounds.weapon_fire import PROFILES
            if d.sound_profile not in PROFILES:
                raise ValueError('unknown weapon sound profile')
            numbers = (d.speed,d.lifetime,d.radius,d.blast_radius,d.blast_push,d.restitution,
                       d.turn_rate,d.seek_range,d.seek_cone,d.drop_weight,d.base_speed,d.base_radius,d.sound_pitch,d.sound_duration,d.sound_body,d.proximity_radius,d.inflation_seconds,d.inflation_scale)
            if not all(math.isfinite(n) for n in numbers):
                raise ValueError('weapon tuning must be finite')
            if (d.speed <= 0 or d.lifetime <= 0 or not d.offsets or type(d.damage) is not int or d.damage < 1
                    or d.inflation_seconds < 0 or d.inflation_scale < 1
                    or (d.behaviour == 'inflator' and d.inflation_seconds <= 0)
                    or not 0 <= d.sound_body <= 1 or d.proximity_radius < 0 or d.sound_pitch <= 0 or d.sound_duration <= 0 or d.base_speed <= 0 or d.base_radius <= 0 or d.radius < 0 or d.blast_radius <= 0 or d.blast_push < 0 or d.wall_hits < 0
                    or not 0 <= d.restitution <= 1 or d.turn_rate <= 0 or d.seek_range <= 0
                    or not 0 < d.seek_cone <= 180 or d.drop_weight < 0
                    or any(len(offset) != 2 or not all(math.isfinite(v) for v in offset) for offset in d.offsets)):
                raise ValueError('invalid projectile tuning')
            self._definitions[d.id] = d
        if 'basic' not in self._definitions or self['basic'].capacity is not None:
            raise ValueError('basic weapon must have unlimited ammunition')
        if any(d.capacity is None for d in self._definitions.values() if d.id != 'basic'):
            raise ValueError('only basic may have unlimited ammunition')

    def __getitem__(self, weapon_id):
        return self._definitions[weapon_id]

    @property
    def ids(self):
        return tuple(self._definitions)

    @property
    def drops(self):
        return tuple(key for key in self.ids if key != 'basic')

    def choose_drop(self, rng, allowed=None):
        ids = self.drops if allowed is None else tuple(allowed)
        if not ids or any(key not in self.drops for key in ids):
            raise ValueError('weapon drop allowlist must contain special weapon IDs')
        weights = [self[key].drop_weight for key in ids]
        if not any(weights):
            raise ValueError('weapon drop weights must include a positive weight')
        return rng.choices(ids, weights=weights, k=1)[0]

    def snapshot(self):
        return [asdict(self[key]) for key in self.ids]

CATALOG = WeaponCatalog([
    WeaponDefinition('basic', 'Basic Gun', None, config.SETTINGS.powerups.fireRateBaseCooldown * config.FPS / 1000,
                     (235, 240, 255), 'single', lifetime=config.PROJECTILE_LIFETIME),
    WeaponDefinition('twin_blaster', 'Twin Blaster', 60, 8.4, (80, 170, 255), 'twin', offsets=((-5, 0), (5, 0)), sound_pitch=1500, sound_duration=.065),
    WeaponDefinition('scattergun', 'Scattergun', 20, 27, (255, 145, 65), 'fan', lifetime=24,
                     offsets=tuple((0, angle) for angle in (-20, -10, 0, 10, 20)),
                     damage=2, speed=1.15, radius=3.5, sound_pitch=110, sound_duration=.36, sound_body=.9, sound_profile='blast'),
    WeaponDefinition('railgun', 'Railgun', 12, 25.5, (200, 110, 255), 'needle', 'rail', speed=3.5, damage=2, sound_pitch=2400, sound_duration=.2),
    WeaponDefinition('seeker', 'Seeker', 18, 30, (90, 245, 145), 'fork', 'seeker', speed=0.8, lifetime=150, sound_pitch=650, sound_duration=.16),
    WeaponDefinition('inflator', 'The Inflator', 18, 30, (255, 110, 210), 'balloon', 'inflator',
                     speed=.9, radius=5, drop_weight=.25, sound_pitch=480, sound_duration=.2, sound_body=.5,
                     inflation_seconds=config.SETTINGS.powerups.inflationDurationSeconds,
                     inflation_scale=config.SETTINGS.powerups.inflationSizeMultiplier),
    WeaponDefinition('grenade_launcher', 'Grenade Launcher', 10, 45, (255, 205, 75), 'shell', 'grenade',
                     speed=0.65, lifetime=72, damage=2, radius=5, sound_pitch=110, sound_duration=.22, proximity_radius=28),
    WeaponDefinition('shield', 'Shield', round(config.SETTINGS.powerups.shieldDurationSeconds*config.FPS),
                     1, (100, 220, 255), 'shield', 'shield'),
])


def default_catalog(ruleset):
    """Old recorded rules never introduce the new shield drop."""
    if ruleset == REPLACEMENT_RULESET:
        return WeaponCatalog(CATALOG[key] for key in CATALOG.ids if key != 'shield')
    return CATALOG
