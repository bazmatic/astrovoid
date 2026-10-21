"""A searchlight: sweeping for the player, locking on, and launching creatures at them."""
import math

import config
import enemy_kinds
import level_rules
from creatures.trait import Trait
from creatures.traits.rooted import wall_between
from utils import get_angle_to_point, normalize_angle


def _turn_by(diff: float) -> float:
    """`diff` (degrees) brought into -180 to 180."""
    return (diff + 180) % 360 - 180


class Scans(Trait):
    """Sweeps its beam round at `scanSpeed` degrees a second until it sees the player's ship (never the hunter):
    within `range`, within the `coneDegrees` cone of its heading, and with no wall or gate in the way. Then it turns
    after the ship at `trackSpeed`. It keeps `sees_target`, and `sighted_at` (where the ship is) while it sees it, and
    emits `sighted` when it first sees it. It keeps `scan_range` and `scan_cone` for its Body's beam."""
    NAME = 'scans'

    def __init__(self, coneDegrees: float, range: float, scanSpeed: float, trackSpeed: float):
        self.cone, self.range, self.scan_speed, self.track_speed = coneDegrees, range, scanSpeed, trackSpeed

    def on_spawn(self, c, enc):
        c.scan_range, c.scan_cone = self.range, self.cone
        c.sees_target, c.sighted_at = False, None

    def on_frame(self, c, enc, dt):
        seconds = dt / float(config.FPS)
        ship = enc.ship
        goal = ship.get_pos() if ship is not None and ship.active and not getattr(ship, 'observer', False) else None
        seen = goal is not None and self._sees(c, goal, enc.maze)
        if seen:
            turn = _turn_by(get_angle_to_point(c.get_pos(), goal) - c.angle)
            reach = self.track_speed * seconds
            c.angle = normalize_angle(c.angle + max(-reach, min(reach, turn)))
        else:
            c.angle = normalize_angle(c.angle + self.scan_speed * seconds)
        first_sight = seen and not c.sees_target
        c.sees_target, c.sighted_at = seen, goal if seen else None
        if first_sight:
            c.emit('sighted', enc)

    def _sees(self, c, goal, maze) -> bool:
        if math.dist(c.get_pos(), goal) > self.range:
            return False
        if abs(_turn_by(get_angle_to_point(c.get_pos(), goal) - c.angle)) > self.cone * 0.5:
            return False
        return maze is None or not wall_between(c.get_pos(), goal, maze)


class LaunchesFlock(Trait):
    """While it sees its target it launches a creature of kind `into` at it, from where it stands, at `speed` times
    that creature's top speed; then again each time the level's launch interval has passed. A fresh sighting launches
    at once. It emits `launched`."""
    NAME = 'launchesFlock'
    REQUIRES = ('scans',)

    def __init__(self, into: str, speed: float):
        if into not in enemy_kinds.kinds() or 'thrusters' not in dict(enemy_kinds.kind(into).traits):
            raise ValueError(f'launchesFlock: {into!r} is not an enemy kind with thrusters')
        self.into, self.speed = into, speed

    def on_spawn(self, c, enc):
        c.launch_cooldown = 0.0   # seconds

    def on_event(self, c, name, enc):
        if name == 'sighted':
            c.launch_cooldown = 0.0

    def on_frame(self, c, enc, dt):
        c.launch_cooldown = max(0.0, c.launch_cooldown - dt / float(config.FPS))
        if not c.sees_target or c.launch_cooldown > 0.0:
            return
        child = enc.spawn(self.into, c.get_pos(), c.level)
        child.angle = get_angle_to_point(c.get_pos(), c.sighted_at)
        top_speed = dict(enemy_kinds.kind(self.into).traits)['thrusters']['speedShare'] * config.SHIP_MAX_SPEED
        heading = math.radians(child.angle)
        child.vx, child.vy = math.cos(heading) * top_speed * self.speed, math.sin(heading) * top_speed * self.speed
        c.launch_cooldown = level_rules.get_flighthouse_spawn_interval(c.level)
        c.emit('launched', enc)
