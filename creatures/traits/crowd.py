"""Crowd traits: run once a frame with every live creature of a kind."""
import math
from typing import Optional

from creatures.trait import Trait
from utils.math_utils import get_closest_point_on_line

SEPARATION_PASSES = 20  # a crowd can need a few rounds of pushing before nobody overlaps


def keep_apart(creatures, walls=(), spatial_grid=None) -> None:
    """Push overlapping creatures apart, each by half the overlap, until they only touch. Walls win: after each round
    anything pushed into a wall is put back out, so a crowd pressed against a wall packs tighter rather than squeezing
    one of its members into the wall."""
    for _ in range(SEPARATION_PASSES):
        moved = False
        for i, a in enumerate(creatures):
            for b in creatures[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                distance = math.hypot(dx, dy)
                overlap = a.radius + b.radius - distance
                if overlap <= 0:
                    continue
                if distance == 0:                          # exactly on top of each other: part them sideways
                    dx, dy, distance = 1.0, 0.0, 1.0
                push_x, push_y = dx / distance * overlap / 2, dy / distance * overlap / 2
                a.x, a.y = a.x - push_x, a.y - push_y
                b.x, b.y = b.x + push_x, b.y + push_y
                moved = True
        if not moved:
            return
        if walls:
            for creature in creatures:
                _push_out_of_walls(creature, walls, spatial_grid)


def _push_out_of_walls(creature, walls, spatial_grid=None) -> None:
    """Move a creature straight out of any wall it overlaps, leaving its velocity alone."""
    nearby = spatial_grid.get_nearby_walls((creature.x, creature.y), creature.radius * 2.0) if spatial_grid else walls
    for wall in nearby:
        if hasattr(wall, 'get_segment'):
            if not wall.active:
                continue
            start, end = wall.get_segment()
        else:
            start, end = wall
        # Most nearby walls are clear of the creature's bounding box: a wall that far away is out of
        # reach, so skip the exact test (the margin keeps this from ever skipping an overlap)
        x, y, reach = creature.x, creature.y, creature.radius + 1e-6
        if (x + reach < start[0] and x + reach < end[0]) or (x - reach > start[0] and x - reach > end[0]) or \
                (y + reach < start[1] and y + reach < end[1]) or (y - reach > start[1] and y - reach > end[1]):
            continue
        closest = get_closest_point_on_line((creature.x, creature.y), start, end)
        dx, dy = creature.x - closest[0], creature.y - closest[1]
        distance = math.hypot(dx, dy)
        overlap = creature.radius - distance
        if overlap <= 0 or distance == 0:
            continue
        creature.x += dx / distance * overlap
        creature.y += dy / distance * overlap


class KeepsApart(Trait):
    """Creatures of one crowd never overlap: each frame they are pushed apart until they only touch, and never into a
    wall. The crowd is the creature's kind unless `crowd` names one that several kinds share."""
    NAME = 'keepsApart'
    CROWD = True

    def __init__(self, crowd: Optional[str] = None):
        self.crowd_name = crowd

    def crowd(self, c) -> str:
        return self.crowd_name or c.type

    def on_crowd(self, creatures, enc, dt):
        maze = enc.maze
        keep_apart(creatures, maze.walls if maze is not None else (), maze.spatial_grid if maze is not None else None)
