"""Flocking: a brain that steers a creature with its flock and fires with it, and birdsong."""
import math
import random

import config
from creatures.trait import Trait
from entities.flocker_neighbor_cache import FlockerNeighborCache
from utils import angle_to_radians, get_angle_to_point


def _unit(x: float, y: float):
    magnitude = math.hypot(x, y)
    return (x / magnitude, y / magnitude) if magnitude > 0.0 else (x, y)


def _turn_by(diff: float) -> float:
    """`diff` (degrees) brought into -180 to 180."""
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff


class Flocks(Trait):
    """Steers with its flock: away from neighbours within `separationRadius`, along the heading of those within
    `alignmentRadius`, toward the middle of those within `cohesionRadius`, and toward its target, each pull weighted. It
    turns toward the result and thrusts once within 45 degrees of it.

    It fires at its target, in range and loaded, when the target is within `closeRange` and `closeAngle` degrees of
    its heading; or, with chance `syncChance`, when a neighbour within `cohesionRadius` has just fired or is about to.

    It decides for the whole flock at the end of a frame, from where they all are then, and acts on the next."""
    NAME = 'flocks'
    CROWD = True
    REQUIRES = ('thrusters', 'gun')
    ABOUT_TO_FIRE = 0.2 * config.FPS   # frames of reloading left that count as about to fire

    def __init__(self, separationRadius: float, alignmentRadius: float, cohesionRadius: float,
                 separationWeight: float, alignmentWeight: float, cohesionWeight: float, seekWeight: float,
                 closeRange: float, closeAngle: float, syncChance: float):
        self.separation_radius, self.alignment_radius, self.cohesion_radius = (
            separationRadius, alignmentRadius, cohesionRadius)
        self.weights = (separationWeight, alignmentWeight, cohesionWeight, seekWeight)
        self.close_range, self.close_angle, self.sync_chance = closeRange, closeAngle, syncChance

    def on_crowd(self, creatures, enc, dt):
        cache = FlockerNeighborCache(max(self.separation_radius, self.alignment_radius, self.cohesion_radius))
        cache.update(creatures)
        for index, c in enumerate(creatures):
            goal = enc.target_for(c)
            pulls = (self._separation(c, cache, index), self._alignment(cache, index), self._cohesion(c, cache, index),
                     _unit(goal[0] - c.x, goal[1] - c.y) if goal else (0.0, 0.0))
            fx, fy = _unit(sum(p[0] * w for p, w in zip(pulls, self.weights)),
                           sum(p[1] * w for p, w in zip(pulls, self.weights)))
            off = _turn_by(get_angle_to_point((c.x, c.y), (c.x + fx, c.y + fy)) - c.angle)
            controls = c.controls
            controls.heading = None
            controls.turn = 0.0 if abs(off) <= config.SHIP_ROTATION_SPEED * 2.0 else math.copysign(1.0, off)
            controls.thrust = abs(off) < 45.0
            controls.aim = goal
            controls.fire = goal is not None and self._fires(c, goal, cache, index, dt)

    def _separation(self, c, cache, index):
        x = y = 0.0
        for neighbour, dist in cache.get_neighbors(index, self.separation_radius):
            # Away from it, more strongly the closer it is
            x += (c.x - neighbour.x) / dist / dist
            y += (c.y - neighbour.y) / dist / dist
        return _unit(x, y)

    def _alignment(self, cache, index):
        neighbours = cache.get_neighbors(index, self.alignment_radius)
        if not neighbours:
            return (0.0, 0.0)
        x = sum(math.cos(angle_to_radians(n.angle)) for n, _ in neighbours) / len(neighbours)
        y = sum(math.sin(angle_to_radians(n.angle)) for n, _ in neighbours) / len(neighbours)
        return _unit(x, y)

    def _cohesion(self, c, cache, index):
        neighbours = cache.get_neighbors(index, self.cohesion_radius)
        if not neighbours:
            return (0.0, 0.0)
        middle_x = sum(n.x for n, _ in neighbours) / len(neighbours)
        middle_y = sum(n.y for n, _ in neighbours) / len(neighbours)
        return _unit(middle_x - c.x, middle_y - c.y)

    def _fires(self, c, goal, cache, index, dt) -> bool:
        """Whether it fires next frame: in range, loaded by then, and facing a close target or joining a neighbour."""
        reach = math.dist((c.x, c.y), goal)
        if reach > c.gun_range or c.gun_cooldown > dt:
            return False
        if reach <= self.close_range and abs(_turn_by(get_angle_to_point((c.x, c.y), goal) - c.angle)) <= self.close_angle:
            return True
        joining = any(n.just_fired or 0.0 < n.gun_cooldown <= self.ABOUT_TO_FIRE
                      for n, _ in cache.get_neighbors(index, self.cohesion_radius))
        return joining and random.random() < self.sync_chance


class Tweets(Trait):
    """Now and then it tweets: once its quiet time is over, each frame with `chance`. Then it is quiet for `quietMin`
    to `quietMax` frames."""
    NAME = 'tweets'

    def __init__(self, chance: float, quietMin: float, quietMax: float):
        self.chance, self.quiet_min, self.quiet_max = chance, quietMin, quietMax

    def on_spawn(self, c, enc):
        c.tweet_cooldown = 0.0

    def on_frame(self, c, enc, dt):
        if c.tweet_cooldown > 0:
            c.tweet_cooldown -= dt
        elif random.random() < self.chance:
            enc.world.sound_manager.play_tweet()
            c.tweet_cooldown = random.uniform(self.quiet_min, self.quiet_max)
