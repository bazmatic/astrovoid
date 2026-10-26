"""Propulsion: traits that turn a creature's controls into motion."""
import math
from dataclasses import fields
from typing import Optional

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
    never passes through one. Its top speed is `speedShare` of the player's unless `maxSpeed` is supplied."""
    NAME = 'thrusters'

    def __init__(self, speedShare: float, thrust: float = config.SHIP_THRUST_FORCE,
                 turnRate: float = config.SHIP_ROTATION_SPEED, friction: float = config.SHIP_FRICTION,
                 mode: str = 'standard', maxSpeed: Optional[float] = None):
        if mode not in ('standard', 'hunter'):
            raise ValueError('thrusters: unknown mode')
        self.mode = mode
        self.max_speed = speedShare * config.SHIP_MAX_SPEED if maxSpeed is None else maxSpeed
        self.force, self.turn_rate, self.friction = thrust, turnRate, friction

    def on_spawn(self, c, enc):
        c.prev_x, c.prev_y = c.x, c.y
        c.max_speed, c.thrust_force, c.current_rotation_speed = self.max_speed, self.force, self.turn_rate
        c.friction = self.friction
        c.pilot_thrusting = False
        c.thrust_frames = 0
        c._decision = c._burn_left = None
        c._pilot_velocity = (c.vx, c.vy)
        c.thrust_particles = []
        c.thrusting = False

    def on_frame(self, c, enc, dt):
        if self.mode == 'hunter':
            self._steer(c, enc, dt)
            return
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
        if maze is not None:
            vx, vy = c.vx, c.vy
            if thrust.sweep_walls(c, maze.walls, maze.spatial_grid):
                c.wall_impulse = (c.vx - vx, c.vy - vy)
                c.emit('hit_wall', enc)

    def _steer(self, c, enc, dt):
        action = c.controls
        if action.track:
            if action.lead_degrees is not None:
                c.angle = (c.angle + max(-self.turn_rate, min(self.turn_rate, action.lead_degrees))) % 360
        elif action.course:
            if action.burn_heading is not None:
                swing = (action.burn_heading - c.angle + 180) % 360 - 180
                c.angle = (c.angle + max(-self.turn_rate, min(self.turn_rate, swing))) % 360
        elif action.turn:
            c.angle = (c.angle + (1 if action.turn > 0 else -1) * self.turn_rate) % 360
        if action.decision_token is not c._decision:
            c._decision = action.decision_token
            c._burn_left = None
            if action.burn_frames is not None:
                used = 0 if action.burn_reference is None else c.thrust_frames - action.burn_reference
                c._burn_left = max(0.0, action.burn_frames - used)
        burning = action.thrust
        if burning and action.burn_heading is not None:
            swing = (action.burn_heading - c.angle + 180) % 360 - 180
            burning = abs(swing) <= (5.0 if action.course else 20.0)
        if burning and c._burn_left is not None:
            burning = c._burn_left > 0
            if burning:
                c._burn_left -= dt
        c.pilot_thrusting = burning
        if burning:
            thrust.apply_thrust(c, self.force, self.max_speed)
            c.thrust_frames += 1
            c.emit('thrust', enc)

    def on_after_frame(self, c, enc, dt):
        if self.mode != 'hunter':
            return
        thrust.coast(c, dt, self.friction)
        c.integration_dt = dt
        c.emit('integrated', enc)
        thrust.cap_speed(c, self.max_speed)
        maze = enc.maze
        if maze is not None:
            vx, vy = c.vx, c.vy
            c.wall_contact = thrust.sweep_walls(c, maze.walls, maze.spatial_grid)
            c.wall_impulse = (0.0, 0.0)
            if c.wall_contact:
                c.wall_impulse = (c.vx - vx, c.vy - vy)
                c.emit('hit_wall', enc)
            c.emit('wall_checked', enc)
        c._pilot_velocity = (c.vx, c.vy)
