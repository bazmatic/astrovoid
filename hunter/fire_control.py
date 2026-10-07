"""Fire control: the firing solution the hunter tracks and holds fire for.

The pilot decides whether to engage. Holding a nose within a few degrees of a
target is beyond a pilot that chooses a few times a second, so that last part
belongs to the ship: it trims the nose onto the solution found here and
releases shots only when the solution says they will hit.
"""
import math
import config
from hunter.model import FiringSolution
from hunter.pilot_sensors import firing_solution, nose_miss_distance, off_nose
from hunter.visibility import local_segments, visible_point


def find_firing_solution(hunter, enemies, maze, settings):
    """The firing solution for the nearest enemy the hunter can see and reach, or None.

    Uses the same visibility and lead calculation as the readings shown to the
    pilot, so the ship engages the enemy the pilot was looking at.
    """
    origin = hunter.get_pos()
    sensor_range = settings.sensor_cells * maze.cell_size_x
    in_range = sorted(
        (math.hypot(enemy.x - origin[0], enemy.y - origin[1]), index, enemy)
        for index, enemy in enumerate(enemies) if enemy.active)
    in_range = [(distance, enemy) for distance, _, enemy in in_range if distance <= sensor_range]
    if not in_range:
        return None
    walls = local_segments(origin, [(w.start, w.end) for w in maze.walls if w.active], sensor_range)
    for _, enemy in in_range:
        if not visible_point(origin, enemy.get_pos(), walls, sensor_range):
            continue
        relative = (enemy.x - origin[0], enemy.y - origin[1])
        velocity = (enemy.vx, enemy.vy)
        lead = firing_solution(relative, velocity, config.PROJECTILE_SPEED)
        if lead is None or lead[0] > config.PROJECTILE_LIFETIME:
            continue
        miss = nose_miss_distance(relative, velocity, hunter.angle,
                                  config.PROJECTILE_SPEED, config.PROJECTILE_LIFETIME)
        reach = enemy.radius + config.PROJECTILE_SIZE
        return FiringSolution(off_nose(lead[1], hunter.angle, digits=None),
                              miss is not None and miss <= reach)
    return None
