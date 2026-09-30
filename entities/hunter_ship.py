"""Allied spacecraft executing pilot inputs using the shared flight physics."""
import math
import pygame
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.projectile import Projectile
from hunter.model import HunterSettings


class HunterShip(RotatingThrusterShip):
    COLOR = (70, 235, 255)

    def __init__(self, start_pos, settings=HunterSettings()):
        super().__init__(start_pos, config.SHIP_SIZE)
        self.settings = settings
        self.health = settings.health
        self.fire_remaining = 0.0
        self.immunity_remaining = 0.0
        self.pilot_thrusting = False

    def is_enemy_ship(self):
        return False

    def step(self, dt, action):
        if not self.active:
            return None
        seconds = dt / config.FPS
        self.fire_remaining = max(0.0, self.fire_remaining - seconds)
        self.immunity_remaining = max(0.0, self.immunity_remaining - seconds)
        if action.turn < 0:
            self.rotate_left()
        elif action.turn > 0:
            self.rotate_right()
        self.pilot_thrusting = action.thrust
        if action.thrust:
            self.apply_thrust()
        projectile = None
        if action.fire and self.fire_remaining <= 1e-9:
            heading = math.radians(self.angle)
            muzzle = (self.x + math.cos(heading) * (self.radius + 5),
                      self.y + math.sin(heading) * (self.radius + 5))
            projectile = Projectile(muzzle, self.angle, source='hunter',
                                    dynamic_color=self.COLOR)
            self.fire_remaining = self.settings.fire_interval
        super().update(dt)
        return projectile

    def take_damage(self):
        if not self.active or self.immunity_remaining > 0:
            return False
        self.health -= 1
        self.immunity_remaining = self.settings.damage_immunity
        self.active = self.health > 0
        return not self.active

    def draw(self, screen):
        if not self.active:
            return
        color = self.COLOR
        if self.immunity_remaining and int(self.immunity_remaining * 20) % 2:
            color = (230, 255, 255)
        pygame.draw.polygon(screen, color, self.get_vertices(), 2)
        pygame.draw.circle(screen, color, (round(self.x), round(self.y)), 3)
        if self.pilot_thrusting:
            angle = math.radians(self.angle)
            tail = (self.x - math.cos(angle) * self.radius,
                    self.y - math.sin(angle) * self.radius)
            end = (self.x - math.cos(angle) * (self.radius + 12),
                   self.y - math.sin(angle) * (self.radius + 12))
            pygame.draw.line(screen, (170, 245, 255), tail, end, 3)
