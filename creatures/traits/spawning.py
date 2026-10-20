"""Traits that put new enemies on the level: splitting into children on death, laying eggs."""
import math
import random

import enemy_kinds
from creatures.trait import Trait


def _open_spot(maze, pos, radius, origin, max_offset):
    """`pos` if something of this radius fits there, else an open spot near `origin`."""
    if maze is None or maze.is_open(pos, radius):
        return pos
    return maze.open_spot_near(origin, radius, max_offset)


class SplitsOnDeath(Trait):
    """Its death leaves `count` creatures of kind `into`, scattered `spread / 2` to `spread` px around it and flying
    apart at `speed`: the first 45 degrees to the left of its direction of travel, the rest 45 degrees to the right."""
    NAME = 'splitsOnDeath'

    def __init__(self, into: str, count: int, spread: float, speed: float):
        if into not in enemy_kinds.kinds():
            raise ValueError(f'splitsOnDeath: {into!r} is not an enemy kind')
        self.into, self.count, self.spread, self.speed = into, count, spread, speed

    def on_death(self, c, enc):
        child_radius = enemy_kinds.kind(self.into).tuning['size']
        travel = math.atan2(c.vy, c.vx)
        for i in range(self.count):
            bearing = random.uniform(0, 2 * math.pi)
            reach = random.uniform(self.spread * 0.5, self.spread)
            pos = (c.x + math.cos(bearing) * reach, c.y + math.sin(bearing) * reach)
            pos = _open_spot(enc.maze, pos, child_radius, c.get_pos(), self.spread)
            heading = travel - math.pi / 4 if i == 0 else travel + math.pi / 4
            child = enc.spawn(self.into, pos, c.level)
            child.vx, child.vy = math.cos(heading) * self.speed, math.sin(heading) * self.speed


class LaysEggs(Trait):
    """Lays an egg on its first frame and then every `interval` frames, close beside it, where the egg has room to
    grow."""
    NAME = 'laysEggs'

    def __init__(self, interval: int):
        self.interval = interval

    def on_spawn(self, c, enc):
        c.egg_cooldown = 0.0

    def on_frame(self, c, enc, dt):
        if c.egg_cooldown > 0:
            c.egg_cooldown -= dt
            if c.egg_cooldown > 0:
                return
        egg_size = enemy_kinds.kind('egg').tuning['maxSize']
        bearing = random.uniform(0, 2 * math.pi)
        reach = random.uniform(0, c.radius * 0.5)
        pos = (c.x + math.cos(bearing) * reach, c.y + math.sin(bearing) * reach)
        enc.spawn('egg', _open_spot(enc.maze, pos, egg_size, c.get_pos(), c.radius), c.level)
        c.egg_cooldown = self.interval
