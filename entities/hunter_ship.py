"""Allied spacecraft executing pilot inputs using the shared flight physics."""
import math
import pygame
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.projectile import Projectile
from hunter.model import HunterSettings


class HunterShip(RotatingThrusterShip):
    # Green marks an ally: the player is blue, enemies are red, orange and purple.
    COLOR = (120, 255, 90)
    FILL = (25, 110, 40)

    def __init__(self, start_pos, settings=HunterSettings()):
        super().__init__(start_pos, config.SHIP_SIZE)
        self.settings = settings
        # Held steering needs a turn rate the pilot's decision rate can control.
        self.rotation_speed_multiplier = settings.turn_rate_multiplier
        self.health = settings.health
        self.fire_remaining = 0.0
        self.burst_remaining = 0
        self.immunity_remaining = 0.0
        self.pilot_thrusting = False

    def is_enemy_ship(self):
        return False

    @property
    def thrust_force(self):
        return config.SHIP_THRUST_FORCE * self.settings.thrust_multiplier

    def cancel_burst(self):
        """Drop the rest of a burst once no live pilot decision backs the trigger."""
        self.burst_remaining = 0

    def step(self, dt, action, solution=None):
        """Fly one frame on the pilot's held controls.

        `solution` is fire control's firing solution for the engaged enemy, or
        None when there is no target. Tracking trims the nose onto it, and a
        shot is only released while it reports the nose on target.
        """
        if not self.active:
            return None
        seconds = dt / config.FPS
        self.fire_remaining = max(0.0, self.fire_remaining - seconds)
        self.immunity_remaining = max(0.0, self.immunity_remaining - seconds)
        if action.track:
            if solution is not None:
                # Swing at the normal turn rate, but stop exactly on the solution.
                rate = self.current_rotation_speed
                self.angle = (self.angle + max(-rate, min(rate, solution.lead_degrees))) % 360
        elif action.turn < 0:
            self.rotate_left()
        elif action.turn > 0:
            self.rotate_right()
        self.pilot_thrusting = action.thrust
        if action.thrust:
            self.apply_thrust()
        projectile = None
        ready = self.fire_remaining <= 1e-9
        lined_up = solution is not None and solution.on_target
        # Pulling the trigger commits to a whole burst, even if it is then released.
        # Fire control holds each shot until the nose is on target, and drops a
        # burst that is neither lined up nor still asked for.
        if action.fire and ready and lined_up and not self.burst_remaining:
            self.burst_remaining = self.settings.burst_size
        if self.burst_remaining and not lined_up and not action.fire:
            self.burst_remaining = 0
        if self.burst_remaining and ready and lined_up:
            heading = math.radians(self.angle)
            muzzle = (self.x + math.cos(heading) * (self.radius + 5),
                      self.y + math.sin(heading) * (self.radius + 5))
            projectile = Projectile(muzzle, self.angle, source='hunter',
                                    dynamic_color=self.COLOR)
            self.burst_remaining -= 1
            self.fire_remaining = (self.settings.burst_spacing if self.burst_remaining
                                   else self.settings.fire_interval)
        super().update(dt)
        return projectile

    def take_damage(self):
        if not self.active or self.settings.indestructible or self.immunity_remaining > 0:
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
            color = (235, 255, 230)
        pygame.draw.polygon(screen, self.FILL, self.get_vertices())
        pygame.draw.polygon(screen, color, self.get_vertices(), 2)
        pygame.draw.circle(screen, color, (round(self.x), round(self.y)), 3)
        # The hunter's gentle thrust rarely reaches plume-length speeds, so hold
        # the cone open while the pilot's engine is on.
        self.draw_thrust_plume(
            screen, config.THRUST_PLUME_LENGTH * 0.6 if self.pilot_thrusting else 0.0)
