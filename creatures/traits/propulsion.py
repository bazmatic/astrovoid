"""Propulsion: traits that turn a creature's controls into motion."""
import math
from dataclasses import fields

import config
import level_rules
from physics import thrust
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


class Drift(Trait):
    """Steers its velocity toward the heading its brain wants, at its speed. A bounce is kept rather than steered out
    at once, and a turn right round is taken at once. With no heading it slows to a stop."""
    NAME = 'drift'
    REVERSAL = 150.0   # degrees: a change of heading this big is a deliberate turn around

    def __init__(self, speed):
        if isinstance(speed, str) and speed not in {f.name for f in fields(level_rules.EnemyStrength)}:
            raise ValueError(f'drift: speed {speed!r} is not a level strength')
        self.speed = speed

    def on_spawn(self, c, enc):
        c.speed = (getattr(level_rules.get_enemy_strength(c.level), self.speed) if isinstance(self.speed, str)
                   else float(self.speed))
        c.drift_heading = None

    def on_frame(self, c, enc, dt):
        heading = c.controls.heading
        last, c.drift_heading = c.drift_heading, heading
        if heading is None:
            c.apply_friction_and_update_position(config.FRICTION_COEFFICIENT, dt)
            return
        rad = math.radians(heading)
        want_x, want_y = math.cos(rad) * c.speed, math.sin(rad) * c.speed
        if last is not None and abs((heading - last + 180) % 360 - 180) > self.REVERSAL:
            c.vx, c.vy = want_x, want_y
            c.x += c.vx * dt
            c.y += c.vy * dt
            return
        blend = self._blend(c, rad)
        c.vx = c.vx * (1.0 - blend) + want_x * blend
        c.vy = c.vy * (1.0 - blend) + want_y * blend
        c.apply_friction_and_update_position(config.FRICTION_COEFFICIENT, dt)

    @staticmethod
    def _blend(c, rad, base=0.7) -> float:
        """How much of the wanted velocity to take this frame. Velocity far off the heading is a bounce (opposite, or
        across and much faster): keep most of it, so the bounce shows."""
        current = math.hypot(c.vx, c.vy)
        if current <= 0.01:
            return 1.0
        alignment = (c.vx * math.cos(rad) + c.vy * math.sin(rad)) / current
        if alignment < -0.2 or (alignment < 0.2 and current / max(c.speed, 0.1) > 1.5):
            return 0.15
        if alignment > 0.7:
            return base
        if alignment > 0.3:
            return base * 0.8
        return base * 0.5


class Thrusters(Trait):
    """Flies like a ship: it turns toward its brain's heading (or by its brain's turn) and thrusts along its own
    heading, coasting with friction between thrusts, bouncing off the screen edges, and sweeping into walls so it
    never passes through one. Its top speed is `speedShare` of the player ship's."""
    NAME = 'thrusters'

    def __init__(self, speedShare: float, thrust: float = config.SHIP_THRUST_FORCE,
                 turnRate: float = config.SHIP_ROTATION_SPEED, friction: float = config.SHIP_FRICTION):
        self.max_speed = speedShare * config.SHIP_MAX_SPEED
        self.force, self.turn_rate, self.friction = thrust, turnRate, friction

    def on_spawn(self, c, enc):
        c.prev_x, c.prev_y = c.x, c.y

    def on_frame(self, c, enc, dt):
        controls = c.controls
        if controls.heading is not None:
            thrust.turn_toward(c, controls.heading, self.turn_rate)
        elif controls.turn:
            c.angle = (c.angle + controls.turn * self.turn_rate) % 360
        if controls.thrust:
            thrust.apply_thrust(c, self.force, self.max_speed)
            c.emit('thrust', enc)
        thrust.coast(c, dt, self.friction)
        thrust.cap_speed(c, self.max_speed)
        maze = enc.maze
        if maze is not None and thrust.sweep_walls(c, maze.walls, maze.spatial_grid):
            c.emit('hit_wall', enc)
