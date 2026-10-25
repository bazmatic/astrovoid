"""One implementation of replacement, ammo, fallback, and firing cadence."""
from dataclasses import dataclass
from collections import Counter
import math
from weapons.catalog import CATALOG

@dataclass(frozen=True)
class WeaponView:
    id: str
    ammo: int | None
    capacity: int | None
    cooldown: float
    interval: float

    @property
    def ammo_fraction(self):
        return 1.0 if self.capacity is None else self.ammo / self.capacity

@dataclass(frozen=True)
class FireResult:
    weapon_id: str
    projectiles: tuple = ()

class EquippedWeapon:
    def __init__(self, catalog=CATALOG):
        self.catalog = catalog
        self.reset()

    def reset(self):
        self.weapon_id, self.ammo, self.cooldown = 'basic', None, 0.0
        self.volleys_fired = Counter()

    @property
    def definition(self):
        return self.catalog[self.weapon_id]

    @property
    def view(self):
        return WeaponView(self.weapon_id, self.ammo, self.definition.capacity, self.cooldown, self.definition.interval)

    def equip(self, weapon_id):
        definition = self.catalog[weapon_id]  # validate before changing anything
        self.weapon_id, self.ammo = definition.id, definition.capacity

    def update(self, dt):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('dt must be finite and nonnegative')
        self.cooldown = max(0.0, self.cooldown - dt)

    def try_fire(self, pos, angle, source='player'):
        if self.cooldown > 1e-8:
            return FireResult(self.weapon_id)
        from weapons.projectile import make_projectile
        d = self.definition
        rad = math.radians(angle)
        shots = tuple(make_projectile((pos[0] - math.sin(rad) * side, pos[1] + math.cos(rad) * side),
                                      angle + spread, source, d)
                      for side, spread in d.offsets)
        self.volleys_fired[d.id] += 1
        self.cooldown = d.interval
        if self.ammo is not None:
            self.ammo -= 1
            if self.ammo == 0:
                self.weapon_id, self.ammo = 'basic', None
        return FireResult(d.id, shots)
