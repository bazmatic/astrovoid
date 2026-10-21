"""Rooted creatures: held to one spot, pulling the player's ship in, flinging it back out."""
import math
from typing import Tuple

import config
from creatures.trait import Trait
from creatures.traits.combat import flinch
from entities.anemone import apply_pull, pull_acceleration
from utils import line_line_collision


def hold(c) -> None:
    """Put an anchored creature back on its anchor, at rest."""
    c.x, c.y = c.anchor
    c.vx = c.vy = 0.0


def wall_between(start: Tuple[float, float], end: Tuple[float, float], maze) -> bool:
    """Whether an active wall or a gate crosses the line between two points."""
    walls = maze.walls
    if maze.spatial_grid is not None:
        walls = maze.spatial_grid.get_walls_along_path(start, end, 0.0)
    return any(wall.active and line_line_collision(start, end, wall.start, wall.end)
               for wall in list(walls) + list(getattr(maze, 'gate_segments', ())))


def fling(ship, centre: Tuple[float, float], radius: float, speed: float) -> None:
    """Throw a ship that touched a creature of this radius at `centre` straight back out, at `speed`."""
    dx, dy = ship.x - centre[0], ship.y - centre[1]
    dist = math.hypot(dx, dy)
    if not math.isfinite(dist) or dist <= 1e-6:
        # Dead centre (where the bounce itself has no direction to work with):
        # throw it back the way it came, or to the right if it was still
        moving_speed = math.hypot(ship.vx, ship.vy)
        moving = math.isfinite(moving_speed) and moving_speed > 1e-6
        dx, dy = (-ship.vx / moving_speed, -ship.vy / moving_speed) if moving else (1.0, 0.0)
    else:
        dx, dy = dx / dist, dy / dist
    clear = radius + ship.radius + 1.0
    ship.x, ship.y = centre[0] + dx * clear, centre[1] + dy * clear
    ship.vx, ship.vy = dx * speed, dy * speed


class Anchored(Trait):
    """Rooted where it spawned: whatever shoves or bumps it, it is back on its anchor, at rest, each frame."""
    NAME = 'anchored'

    def on_spawn(self, c, enc):
        c.anchor = (float(c.x), float(c.y))

    def on_frame(self, c, enc, dt):
        hold(c)


class PullsShip(Trait):
    """Draws the player's ship toward it when it has a clear line to it, out to `reachCells` maze cells: nothing at
    the edge, rising to `strength` times the ship's thrust where the hulls touch. Not while the ship is shielded, nor
    while it flinches. However many have hold of the ship, together they pull no harder than one at full strength, so
    a straight burn always breaks free. It keeps `reach_px`, and this frame's `pull_fraction` and `pull_angle`, for its
    Body."""
    NAME = 'pullsShip'
    CROWD = True

    def __init__(self, reachCells: float, strength: float):
        self.reach_cells, self.strength = reachCells, strength

    def on_spawn(self, c, enc):
        maze = enc.maze if enc is not None else None
        c.reach_px = self.reach_cells * (maze.cell_size_x + maze.cell_size_y) / 2 if maze is not None else 0.0
        c.pull_fraction = c.pull_angle = 0.0

    def on_crowd(self, creatures, enc, dt):
        ship, peak = enc.ship, self.strength * config.SHIP_THRUST_FORCE
        free = ship is not None and ship.active and not ship.is_shield_active()
        pull_x = pull_y = 0.0
        for c in creatures:
            ax, ay = self._pull(c, ship, enc.maze, peak) if free else (0.0, 0.0)
            c.pull_fraction = math.hypot(ax, ay) / peak if peak > 0 else 0.0
            if c.pull_fraction > 0.0:
                c.pull_angle = math.atan2(ship.y - c.y, ship.x - c.x)
                pull_x += ax
                pull_y += ay
        strength = math.hypot(pull_x, pull_y)
        if strength > peak:
            pull_x, pull_y = pull_x / strength * peak, pull_y / strength * peak
        if strength > 0.0:
            apply_pull(ship, pull_x, pull_y)

    @staticmethod
    def _pull(c, ship, maze, peak) -> Tuple[float, float]:
        if getattr(c, 'flinch_timer', 0.0) > 0.0:
            return (0.0, 0.0)
        pull = pull_acceleration(c.get_pos(), c.radius, ship.get_pos(), ship.radius, c.reach_px, peak)
        if pull == (0.0, 0.0) or wall_between(c.get_pos(), ship.get_pos(), maze):
            return (0.0, 0.0)
        return pull


class FlingsShip(Trait):
    """When the ship touches it (ramsShip), it throws the ship straight back out at `speed`, and lets go: it flinches
    for `releaseFrames`, so it cannot drag the ship straight back."""
    NAME = 'flingsShip'
    REQUIRES = ('ramsShip', 'flinchesWhenHit')

    def __init__(self, speed: float, releaseFrames: float):
        self.speed, self.release_frames = speed, releaseFrames

    def on_event(self, c, name, enc):
        if name != 'rammed':
            return
        anchored = hasattr(c, 'anchor')
        fling(enc.ship, c.anchor if anchored else c.get_pos(), c.radius, self.speed)
        if anchored:
            hold(c)
        flinch(c, self.release_frames, enc)
