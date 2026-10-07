"""Wall following: where to head to keep a wall on the left and move along it.

A hunter that is cut off from the player and has nothing to shoot at explores
by the left-hand rule: stay beside the nearest wall, keep it on the left, and
go wherever that leads. Inside corners turn it right, the ends of walls turn
it left, and in a maze that eventually takes it past every opening.

Everything here is in the simulation's own units: pixels and degrees.
"""
import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class WallFollowTarget:
    """A point to fly towards that carries the ship along the wall on its left."""
    point: Point
    wall_distance: Optional[float]  # Gap between hull and wall; None with no wall in sight
    standoff: float  # Distance from the wall the ship is being held at


def _nearest_on_segment(origin: Point, start: Point, end: Point) -> Point:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return (start[0], start[1])
    t = ((origin[0] - start[0]) * dx + (origin[1] - start[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return (start[0] + dx * t, start[1] + dy * t)


def wall_follow_target(
    origin: Point,
    heading: float,
    radius: float,
    walls: Sequence[Tuple[Point, Point]],
    cell_size: float
) -> WallFollowTarget:
    """Pick the point to fly towards to follow the nearest wall on the left.

    The point sits a fixed distance out from the wall and some way along it.
    The direction along it is the one that leaves the wall on the ship's left.
    Working from the nearest point of wall, not from a particular segment, is
    what makes corners work: as a wall ahead becomes the nearest the direction
    swings right, and round the free end of a wall it swings left.

    Args:
        origin: Ship position.
        heading: Nose heading in degrees, used only when no wall is in sight.
        radius: Ship radius.
        walls: Wall segments the ship can see, each as (start, end).
        cell_size: Width of a maze cell, which sets the distances used.

    Returns:
        The target point and the present gap between hull and wall.
    """
    lookahead = cell_size * 0.75
    # Far enough out to clear the hull comfortably, but well inside a one-cell corridor
    standoff = min(cell_size * 0.5, max(radius * 2.5, cell_size * 0.35))
    nearest, nearest_distance = None, None
    for start, end in walls:
        point = _nearest_on_segment(origin, start, end)
        distance = math.hypot(origin[0] - point[0], origin[1] - point[1])
        if nearest_distance is None or distance < nearest_distance:
            nearest, nearest_distance = point, distance
    if nearest is None:
        # Nothing to follow yet: carry straight on until a wall comes into view.
        nose = math.radians(heading)
        return WallFollowTarget(
            (origin[0] + math.cos(nose) * lookahead, origin[1] + math.sin(nose) * lookahead),
            None, standoff)
    if nearest_distance < 1e-9:
        # Sitting on the wall: any way off it will do.
        nose = math.radians(heading)
        away = (-math.cos(nose), -math.sin(nose))
    else:
        away = ((origin[0] - nearest[0]) / nearest_distance, (origin[1] - nearest[1]) / nearest_distance)
    # With y growing downward, the left of a direction (x, y) is (y, -x). The
    # direction whose left points back at the wall is therefore (away.y, -away.x).
    along = (away[1], -away[0])
    return WallFollowTarget(
        (nearest[0] + away[0] * standoff + along[0] * lookahead,
         nearest[1] + away[1] * standoff + along[1] * lookahead),
        max(0.0, nearest_distance - radius), standoff)
