"""A creature's energy, immunity and strongest collision knock."""
import math

import config
from creatures.trait import Trait


def register_hit(c, dvx, dvy):
    """Remember the strongest velocity change since the pilot last looked."""
    hit = getattr(c, '_hit', None)
    if hit is None or dvx * dvx + dvy * dvy > hit[0] ** 2 + hit[1] ** 2:
        c._hit = (dvx, dvy)
    if hasattr(c, '_pilot_velocity'):
        c._pilot_velocity = (c.vx, c.vy)


def take_hit(c):
    """Read and clear the strongest knock."""
    hit, c._hit = getattr(c, '_hit', None), None
    return hit


def damage(c, enc):
    """Apply one energy hit; True only when this call destroys the creature."""
    c.emit('damage_attempted', enc)
    if not c.active or c.indestructible or c.immunity_remaining > 0:
        return False
    c.health -= 1
    c.immunity_remaining = c.damage_immunity
    c.emit('damaged', enc)
    if c.health <= 0:
        enc.kill(c)
    return not c.active


class Energy(Trait):
    NAME = 'energy'

    def __init__(self, health=3, indestructible=True, immunity=0.5, wallEnergy=0.0):
        if health <= 0 or immunity < 0 or wallEnergy < 0:
            raise ValueError('energy: health must be positive; immunity and wallEnergy nonnegative')
        self.health, self.indestructible = health, indestructible
        self.immunity, self.wall_energy = immunity, wallEnergy

    def on_spawn(self, c, enc):
        c.health = self.health
        c.indestructible = self.indestructible
        c.damage_immunity = self.immunity
        c.wall_energy = self.wall_energy
        c.immunity_remaining = 0.0
        c._hit = None

    def on_frame(self, c, enc, dt):
        c.immunity_remaining = max(0.0, c.immunity_remaining - dt / config.FPS)

    def on_event(self, c, name, enc):
        if name == 'contact':
            register_hit(c, *c.contact_impulse)
        if name == 'hit_wall' and c.active:
            dvx, dvy = c.wall_impulse
            register_hit(c, dvx, dvy)
            if not c.indestructible and c.wall_energy > 0:
                c.health -= c.wall_energy * math.hypot(dvx, dvy) / max(getattr(c, 'max_speed', config.SHIP_MAX_SPEED), 1e-6)
                if c.health <= 0:
                    enc.kill(c)
