"""Growth: a creature that grows bigger and tougher, and one that hatches into others once fully grown."""
import math
import random

import enemy_kinds
from creatures.trait import Trait
from creatures.traits.spawning import _open_spot


class Grows(Trait):
    """Grows by a rate rolled in `[rateMin, rateMax]` px a frame until its radius reaches `to`. Its hit points grow with
    it, from what it started with to `hitPointsGrown`, keeping the share of damage it has taken. It keeps `growth`,
    from 0 (as laid) to 1 (fully grown)."""
    NAME = 'grows'

    def __init__(self, to: float, rateMin: float, rateMax: float, hitPointsGrown: int):
        self.to, self.rate_min, self.rate_max, self.hit_points_grown = to, rateMin, rateMax, hitPointsGrown

    def on_spawn(self, c, enc):
        c.growth_rate = random.uniform(self.rate_min, self.rate_max)
        c.start_radius = c.radius
        c.start_hit_points = c.max_hit_points
        c.growth = 0.0

    def on_frame(self, c, enc, dt):
        c.radius = min(self.to, c.radius + c.growth_rate * dt)
        span = self.to - c.start_radius
        c.growth = 1.0 if span <= 0 else max(0.0, min(1.0, (c.radius - c.start_radius) / span))
        grown = int(round(c.start_hit_points + c.growth * (self.hit_points_grown - c.start_hit_points)))
        if grown != c.max_hit_points:
            share = c.hit_points / c.max_hit_points if c.max_hit_points > 0 else 1.0
            c.max_hit_points = grown
            c.hit_points = min(grown, int(round(grown * share)))


class Hatches(Trait):
    """Once fully grown it hatches: `countMin` to `countMax` creatures of kind `into` (the count rolled when it is laid)
    come out `spread / 2` to `spread` px around it, and it is gone. Hatching is not a kill: no pickup, no score."""
    NAME = 'hatches'
    REQUIRES = ('grows',)

    def __init__(self, into: str, countMin: int, countMax: int, spread: float):
        if into not in enemy_kinds.kinds():
            raise ValueError(f'hatches: {into!r} is not an enemy kind')
        self.into, self.count_min, self.count_max, self.spread = into, countMin, countMax, spread

    def on_spawn(self, c, enc):
        c.hatch_count = random.randint(self.count_min, self.count_max)
        c.hatched = False

    def on_frame(self, c, enc, dt):
        if c.growth < 1.0:
            return
        child_radius = enemy_kinds.kind(self.into).tuning['size']
        for _ in range(c.hatch_count):
            bearing = random.uniform(0, 2 * math.pi)
            reach = random.uniform(self.spread * 0.5, self.spread)
            pos = (c.x + math.cos(bearing) * reach, c.y + math.sin(bearing) * reach)
            enc.spawn(self.into, _open_spot(enc.maze, pos, child_radius, c.get_pos(), self.spread), c.level)
        c.hatched = True
        c.die()
