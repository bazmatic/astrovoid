"""Brains: traits that decide a creature's controls each frame."""
import math
import random

import config
from creatures.trait import Trait
from utils import circle_line_collision, distance, get_angle_to_point


class Still(Trait):
    """Wants nothing: sets no controls."""
    NAME = 'still'


class Patrol(Trait):
    """Walks straight for a random 50-150 px, then turns around; a wall just ahead turns it at once. It fires at a
    target within its gun's range."""
    NAME = 'patrol'
    DISTANCE = (50.0, 150.0)   # px walked before turning around

    def on_spawn(self, c, enc):
        c.patrol_max = random.uniform(*self.DISTANCE)
        c.patrol_distance = 0.0

    def on_frame(self, c, enc, dt):
        controls = c.controls
        target = enc.target_for(c)
        if target is None:
            controls.heading, controls.fire, controls.aim = None, False, None
            return
        if c.patrol_distance >= c.patrol_max or self._wall_ahead(c, enc.maze, dt):
            c.angle = (c.angle + 180) % 360
            c.patrol_distance = 0.0
        else:
            c.patrol_distance += c.speed * dt
        controls.heading = c.angle
        in_range = distance(c.get_pos(), target) <= c.gun_range
        controls.fire, controls.aim = in_range, (target if in_range else None)

    @staticmethod
    def _wall_ahead(c, maze, dt) -> bool:
        """Whether its next step would touch an active wall."""
        if maze is None:
            return False
        heading = math.radians(c.angle)
        ahead = (c.x + math.cos(heading) * c.speed * dt, c.y + math.sin(heading) * c.speed * dt)
        walls = (maze.spatial_grid.get_nearby_walls(ahead, c.radius * 2.0) if maze.spatial_grid is not None
                 else maze.walls)
        for wall in walls:
            if hasattr(wall, 'get_segment'):
                if not wall.active:
                    continue
                start, end = wall.get_segment()
            else:
                start, end = wall
            if circle_line_collision(ahead, c.radius, start, end):
                return True
        return False


class Chase(Trait):
    """Heads for its target. Stuck (it barely moved last frame), it backs away from the target for a while, then
    chases again. With no target it wants nothing."""
    NAME = 'chase'

    def on_spawn(self, c, enc):
        c.is_alert = c.backing_off = False
        c.chase_last_pos = None
        c.chase_escape_left = 0

    def on_frame(self, c, enc, dt):
        target = enc.target_for(c)
        if target is None:
            c.is_alert = c.backing_off = False
            c.chase_last_pos, c.chase_escape_left = None, 0
            c.controls.heading = None
            return
        c.is_alert = True
        pos, last = c.get_pos(), c.chase_last_pos
        c.chase_last_pos = pos
        if c.chase_escape_left > 0:
            c.chase_escape_left -= 1
        elif last is not None and distance(pos, last) < config.ENEMY_STUCK_DETECTION_THRESHOLD and not c.backing_off:
            c.angle = (get_angle_to_point(pos, target) + 180 + random.uniform(-45, 45)) % 360
            c.chase_escape_left = random.randint(config.ENEMY_SHIFT_DURATION_MIN, config.ENEMY_SHIFT_DURATION_MAX) - 1
            c.backing_off = True
        else:
            c.backing_off = False
            c.angle = get_angle_to_point(pos, target)
        c.controls.heading = c.angle
