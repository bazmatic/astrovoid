"""Shared firing cadence with legacy replacement and current per-weapon inventory."""
from dataclasses import dataclass
from collections import Counter
import math
from weapons.catalog import CATALOG

@dataclass(frozen=True)
class WeaponView:
    id: str
    ammo: int | float | None
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


class WeaponInventory(EquippedWeapon):
    """Owned weapons in pickup order, each retaining its own ammunition."""
    def reset(self):
        self._ammo = {}
        self.shield_active = False
        self._trigger_down = False
        self._cycle_down = False
        super().reset()

    @property
    def ammo(self):
        return self._ammo[self.weapon_id]

    @ammo.setter
    def ammo(self, value):
        self._ammo[self.weapon_id] = value

    @property
    def inventory(self):
        return tuple(WeaponView(key, ammo, self.catalog[key].capacity,
                                self.cooldown, self.catalog[key].interval)
                     for key, ammo in self._ammo.items())

    def equip(self, weapon_id):
        keep_shield = self.shield_active and weapon_id == self.weapon_id
        super().equip(weapon_id)
        self.shield_active = keep_shield

    def cycle(self, pressed=True):
        """Advance once per press, skipping empty slots but retaining them for refills."""
        edge = pressed and not self._cycle_down
        self._cycle_down = pressed
        if not edge:
            return False
        ids = tuple(self._ammo)
        start = ids.index(self.weapon_id)
        for offset in range(1,len(ids)+1):
            key = ids[(start+offset)%len(ids)]
            if self._ammo[key] is None or self._ammo[key] > 0:
                changed = key != self.weapon_id
                self.weapon_id = key
                self.shield_active = False
                return changed
        return False

    def release_trigger(self):
        self._trigger_down = False

    def try_fire(self, pos, angle, source='player'):
        edge = not self._trigger_down
        self._trigger_down = True
        if self.definition.behaviour == 'shield':
            if edge and self.ammo > 0:
                self.shield_active = not self.shield_active
            return FireResult(self.weapon_id)
        return super().try_fire(pos,angle,source)

    def update(self, dt):
        super().update(dt)
        if self.shield_active:
            self.ammo = max(0,self.ammo-dt)
            if self.ammo <= 0:
                self.shield_active = False
                self.weapon_id = 'basic'
