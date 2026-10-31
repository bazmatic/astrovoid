"""A local wall-following fallback for the demonstration teacher, when cell routing cannot supply a safe waypoint."""
import math

from creatures.wallcrawler_team import path_clear
from utils import get_closest_point_on_line


def waypoint(c, enc, target):
    maze = enc.maze
    walls = (maze.spatial_grid.get_nearby_walls(c.get_pos(), 200)
             if maze.spatial_grid is not None else maze.walls)
    walls = [w for w in list(walls) + list(getattr(maze, 'gate_segments', ())) if w.active]
    memories = getattr(enc, '_jelly_wall_follow', None)
    if memories is None:
        enc._jelly_wall_follow = memories = {}
    key = id(c)
    if not walls:
        return None
    wall = min(walls, key=lambda w: math.dist(c.get_pos(), get_closest_point_on_line(c.get_pos(), w.start, w.end)))
    foot = get_closest_point_on_line(c.get_pos(), wall.start, wall.end)
    dx, dy = c.x - foot[0], c.y - foot[1]
    distance = math.hypot(dx, dy)
    if distance < 1e-6:
        dx, dy = wall.end[1] - wall.start[1], wall.start[0] - wall.end[0]
        distance = math.hypot(dx, dy)
    if distance < 1e-6:
        return None
    nx, ny = dx / distance, dy / distance
    if key not in memories:
        # Pick one side once, then keep it through corners instead of oscillating between equally good tangents.
        alignment = -ny * (target[0] - c.x) + nx * (target[1] - c.y)
        memories[key] = 1 if alignment >= 0 else -1
    side = memories[key]
    clearance = c.radius + 14.
    correction = max(-.75, min(1.5, (clearance - distance) / clearance))
    vx, vy = -ny * side + nx * correction, nx * side + ny * correction
    heading = math.atan2(vy, vx)
    # Search away from the obstructed tangent if the next wall corner is too tight for the body.
    for offset in (0., side * math.pi/4, -side * math.pi/4, side * math.pi/2, -side * math.pi/2, math.pi):
        point = (c.x + 30 * math.cos(heading + offset), c.y + 30 * math.sin(heading + offset))
        if path_clear(c, enc, point):
            return point
    return None


def clear(c, enc):
    getattr(enc, '_jelly_wall_follow', {}).pop(id(c), None)
