"""Combat: how a creature hurts, is hurt, is pushed about, and what its death leaves."""
import math

import config
from creatures.trait import Trait
from utils import circle_line_collision
from utils.math_utils import apply_wall_collision_physics


class TakesHits(Trait):
    """Each friendly shot costs it a hit point; the last one kills it."""
    NAME = 'takesHits'

    def __init__(self, hitPoints: int):
        self.hit_points = hitPoints

    def on_spawn(self, c, enc):
        c.hit_points = c.max_hit_points = self.hit_points

    def on_shot(self, c, shot, enc):
        c.hit_points -= 1
        c.emit('hit', enc)
        if c.hit_points <= 0:
            enc.kill(c, shot)


class ShovedByShots(Trait):
    """A shot that strikes it passes on some of its speed. Put it before takesHits, so the killing shot shoves too."""
    NAME = 'shovedByShots'

    def __init__(self, transfer: float = config.MOMENTUM_TRANSFER_FACTOR):
        self.transfer = transfer

    def on_shot(self, c, shot, enc):
        c.vx += shot.vx * self.transfer
        c.vy += shot.vy * self.transfer


class RamsShip(Trait):
    """Touching the player's ship costs the player, unless the shield is up; the two bounce apart."""
    NAME = 'ramsShip'

    def on_frame(self, c, enc, dt):
        ship = enc.ship
        if ship is not None and not ship.is_shield_active() and ship.check_circle_collision(c.get_pos(), c.radius, c):
            enc.scoring.record_enemy_collision()
            c.emit('rammed', enc)


class DropsPickup(Trait):
    """Its death rolls for a pickup where it died."""
    NAME = 'dropsPickup'

    def on_death(self, c, enc):
        enc.drop_pickup(c.get_pos())


class BouncesOffWalls(Trait):
    """While it moves, a wall it touches bounces it back out."""
    NAME = 'bouncesOffWalls'

    def on_frame(self, c, enc, dt):
        if abs(c.vx) < config.MIN_VELOCITY_THRESHOLD and abs(c.vy) < config.MIN_VELOCITY_THRESHOLD:
            return
        maze = enc.maze
        walls = (maze.spatial_grid.get_nearby_walls((c.x, c.y), c.radius * 2.0) if maze.spatial_grid is not None
                 else maze.walls)
        for wall in walls:
            if hasattr(wall, 'get_segment'):
                if not wall.active:
                    continue
                start, end = wall.get_segment()
            else:
                start, end = wall
            if not circle_line_collision((c.x, c.y), c.radius, start, end):
                continue
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            if length > 0:
                normal_x, normal_y = -(end[1] - start[1]) / length, (end[0] - start[0]) / length
                if (c.x - start[0]) * normal_x + (c.y - start[1]) * normal_y < 0:
                    normal_x, normal_y = -normal_x, -normal_y
                apply_wall_collision_physics(c, (normal_x, normal_y), config.COLLISION_RESTITUTION)
                c.x += normal_x * (c.radius + 1.0)
                c.y += normal_y * (c.radius + 1.0)
            c.emit('hit_wall', enc)
            return
