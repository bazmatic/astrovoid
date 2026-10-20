"""Combat: how a creature hurts, is hurt, is pushed about, and what its death leaves."""
import math
import random
from typing import Optional

import config
import level_rules
from creatures.trait import Trait
from entities.projectile import Projectile
from utils import circle_line_collision, get_angle_to_point
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


class Gun(Trait):
    """Fires at where its brain aims when its brain says fire and it has reloaded. Numbers left out come from the
    creature's level. It keeps `gun_charge`, how far it is through reloading (0 to 1), for its Body to show."""
    NAME = 'gun'

    def __init__(self, intervalMin: Optional[int] = None, intervalMax: Optional[int] = None,
                 range: Optional[float] = None):
        self.interval_min, self.interval_max, self.range = intervalMin, intervalMax, range

    def on_spawn(self, c, enc):
        strength = level_rules.get_enemy_strength(c.level)
        c.gun_range = strength.fire_range if self.range is None else self.range
        self._reload(c, strength)

    def on_frame(self, c, enc, dt):
        c.gun_cooldown = max(0.0, c.gun_cooldown - dt)
        controls = c.controls
        if controls.fire and controls.aim is not None and c.gun_cooldown <= 0:
            pos = c.get_pos()
            enc.add_shot(Projectile(pos, get_angle_to_point(pos, controls.aim), is_enemy=c.allegiance == 'enemy'))
            self._reload(c, level_rules.get_enemy_strength(c.level))
            c.emit('fired', enc)
        c.gun_charge = 1.0 - c.gun_cooldown / c.gun_interval

    def _reload(self, c, strength):
        low = strength.fire_interval_min if self.interval_min is None else self.interval_min
        high = strength.fire_interval_max if self.interval_max is None else self.interval_max
        c.gun_interval = c.gun_cooldown = random.randint(low, high)
