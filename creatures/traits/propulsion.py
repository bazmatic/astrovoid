"""Propulsion: traits that turn a creature's controls into motion."""
import config
from creatures.trait import Trait


class Coasts(Trait):
    """No drive of its own: it keeps whatever momentum it is given, and friction slows it to a stop."""
    NAME = 'coasts'

    def on_frame(self, c, enc, dt):
        c.x += c.vx * dt
        c.y += c.vy * dt
        c.vx *= config.FRICTION_COEFFICIENT
        c.vy *= config.FRICTION_COEFFICIENT
        if abs(c.vx) < config.MIN_VELOCITY_THRESHOLD:
            c.vx = 0.0
        if abs(c.vy) < config.MIN_VELOCITY_THRESHOLD:
            c.vy = 0.0
