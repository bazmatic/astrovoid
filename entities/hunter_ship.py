"""Allied spacecraft executing pilot inputs using the shared flight physics."""
import math
import pygame
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.projectile import Projectile
from game_handlers.fire_rate_calculator import calculate_fire_cooldown, shots_per_volley
from hunter.model import HunterSettings


class HunterShip(RotatingThrusterShip):
    # Green marks an ally: the player is blue, enemies are red, orange and purple.
    COLOR = (120, 255, 90)
    FILL = (25, 110, 40)
    NOSE_COLOR = (215, 255, 200)  # Pale tip, so the front reads at a glance
    COCKPIT_COLOR = (15, 60, 30)
    ENGINE_COLOR = (170, 95, 20)  # Amber mark in the tail notch, engine off
    ENGINE_LIT_COLOR = (255, 200, 80)  # ... and engine on
    # An arrowhead, in multiples of the radius: x along the heading, y across it.
    # A long nose, swept-back wings and a notched tail give it only one way to point.
    BURN_ALIGNMENT_DEGREES = 5.0  # How close to a course's burn heading the nose must be to thrust
    LOOSE_BURN_ALIGNMENT_DEGREES = 20.0  # The same for a burn made while the nose is not the navigator's
    NOSE_X = 1.4
    WING_X = -0.9
    WING_HALF_SPAN = 0.85
    NOTCH_X = -0.35
    COCKPIT_X = 0.5
    ENGINE_X = -0.5

    def __init__(self, start_pos, settings=HunterSettings()):
        super().__init__(start_pos, config.SHIP_SIZE)
        self.settings = settings
        # Held steering needs a turn rate the pilot's decision rate can control.
        self.rotation_speed_multiplier = settings.turn_rate_multiplier
        self.health = settings.health
        self.fire_remaining = 0.0
        self.burst_remaining = 0
        self.gun_upgrade_level = 0  # Powerups in effect: they upgrade the guns as the player's do
        self.upgrade_remaining = 0.0  # Seconds until the powerups wear off
        self.immunity_remaining = 0.0
        self.pilot_thrusting = False
        self.thrust_frames = 0  # Frames of thrust ever applied
        self._decision = None  # The pilot decision the burn budget belongs to
        self._burn_left = None  # Frames of burn the present course still allows

    def is_enemy_ship(self):
        return False

    @property
    def thrust_force(self):
        return config.SHIP_THRUST_FORCE * self.settings.thrust_multiplier

    def get_gun_upgrade_level(self):
        return self.gun_upgrade_level

    def collect_powerup(self):
        """Take a powerup crystal: one more level of gun upgrade, and the clock on them all restarts."""
        self.gun_upgrade_level += 1
        self.upgrade_remaining = config.POWERUP_DURATION_SECONDS

    @property
    def fire_interval(self):
        """Seconds between bursts, which changes with powerups in step with the player's fire rate."""
        base = config.SETTINGS.powerups.fireRateBaseCooldown
        return self.settings.fire_interval * calculate_fire_cooldown(self) / base

    def _shots(self):
        """The projectiles of one shot: a single one, or a three-way spread from the second powerup."""
        heading = math.radians(self.angle)
        muzzle = (self.x + math.cos(heading) * (self.radius + 5),
                  self.y + math.sin(heading) * (self.radius + 5))
        level = self.gun_upgrade_level
        angles = [self.angle]
        if shots_per_volley(level) > 1:
            spread = config.UPGRADED_PROJECTILE_SPREAD_ANGLE
            angles += [self.angle - spread, self.angle + spread]
        # Powerups beyond the third make the shots bigger and faster
        extra = max(0, level - 3)
        return [Projectile(
            muzzle, angle, is_upgraded=level >= 1,
            enhanced_size_multiplier=1.0 + extra * config.POWERUP_BEYOND_LEVEL_3_SIZE_INCREMENT,
            enhanced_speed_multiplier=1.0 + extra * config.POWERUP_BEYOND_LEVEL_3_SPEED_INCREMENT,
            source='hunter', dynamic_color=self.COLOR) for angle in angles]

    def cancel_burst(self):
        """Drop the rest of a burst once no live pilot decision backs the trigger."""
        self.burst_remaining = 0

    def step(self, dt, action, solution=None):
        """Fly one frame on the pilot's held controls.

        `solution` is fire control's firing solution for the engaged enemy, or
        None when there is no target. Tracking trims the nose onto it, and a
        shot is only released while it reports the nose on target.

        Returns the projectiles of a shot released this frame (one, or three once
        the guns spread), or None.
        """
        if not self.active:
            return None
        seconds = dt / config.FPS
        self.fire_remaining = max(0.0, self.fire_remaining - seconds)
        self.immunity_remaining = max(0.0, self.immunity_remaining - seconds)
        if self.gun_upgrade_level:
            # Powerups wear off all together, as the player's do
            self.upgrade_remaining -= seconds
            if self.upgrade_remaining <= 0.0:
                self.gun_upgrade_level = 0
        if action.track:
            if solution is not None:
                # Swing at the normal turn rate, but stop exactly on the solution.
                rate = self.current_rotation_speed
                self.angle = (self.angle + max(-rate, min(rate, solution.lead_degrees))) % 360
        elif action.course:
            if action.burn_heading is not None:
                rate = self.current_rotation_speed
                swing = (action.burn_heading - self.angle + 180) % 360 - 180
                self.angle = (self.angle + max(-rate, min(rate, swing))) % 360
        elif action.turn < 0:
            self.rotate_left()
        elif action.turn > 0:
            self.rotate_right()
        # A decision may bring a burn of a set length, and a heading the burn belongs
        # to. Thrust applied since a worked burn was worked out counts against it.
        if action is not self._decision:
            self._decision = action
            self._burn_left = None
            if action.burn_frames is not None:
                used = (0 if action.burn_reference is None
                        else self.thrust_frames - action.burn_reference)
                self._burn_left = max(0.0, action.burn_frames - used)
        thrusting = action.thrust
        if thrusting and action.burn_heading is not None:
            # The navigator holds the nose on a course's heading, so that burn can be
            # exact. Otherwise the nose is busy elsewhere and close is good enough.
            swing = (action.burn_heading - self.angle + 180) % 360 - 180
            thrusting = abs(swing) <= (self.BURN_ALIGNMENT_DEGREES if action.course
                                       else self.LOOSE_BURN_ALIGNMENT_DEGREES)
        if thrusting and self._burn_left is not None:
            thrusting = self._burn_left > 0.0
            if thrusting:
                self._burn_left -= dt
        self.pilot_thrusting = thrusting
        if thrusting:
            self.apply_thrust()
            self.thrust_frames += 1
        shots = None
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
            shots = self._shots()
            self.burst_remaining -= 1
            self.fire_remaining = (self.settings.burst_spacing if self.burst_remaining
                                   else self.fire_interval)
        super().update(dt)
        return shots

    def take_damage(self):
        if not self.active or self.settings.indestructible or self.immunity_remaining > 0:
            return False
        self.health -= 1
        self.immunity_remaining = self.settings.damage_immunity
        self.active = self.health > 0
        return not self.active

    def _place(self, x, y):
        """Convert a point in the ship's own frame (radius units) to the screen."""
        heading = math.radians(self.angle)
        cos_heading, sin_heading = math.cos(heading), math.sin(heading)
        return (self.x + (x * cos_heading - y * sin_heading) * self.radius,
                self.y + (x * sin_heading + y * cos_heading) * self.radius)

    def outline(self):
        """Corners of the arrowhead: nose, right wing tip, tail notch, left wing tip."""
        return [self._place(self.NOSE_X, 0.0),
                self._place(self.WING_X, self.WING_HALF_SPAN),
                self._place(self.NOTCH_X, 0.0),
                self._place(self.WING_X, -self.WING_HALF_SPAN)]

    def cockpit(self):
        """Where the cockpit sits, forward of centre."""
        return self._place(self.COCKPIT_X, 0.0)

    def _nose_section(self, back_x):
        """The part of the arrowhead ahead of back_x: a triangle ending at the nose."""
        half_width = self.WING_HALF_SPAN * (self.NOSE_X - back_x) / (self.NOSE_X - self.WING_X)
        return [self._place(self.NOSE_X, 0.0), self._place(back_x, half_width),
                self._place(back_x, -half_width)]

    def draw(self, screen):
        if not self.active:
            return
        color = self.COLOR
        if self.immunity_remaining and int(self.immunity_remaining * 20) % 2:
            color = (235, 255, 230)
        outline = self.outline()
        # Dark at the tail, brightening in two steps to a pale nose
        pygame.draw.polygon(screen, self.FILL, outline)
        middle = tuple((a + b) // 2 for a, b in zip(self.FILL, self.COLOR))
        pygame.draw.polygon(screen, middle, self._nose_section(-0.2))
        pygame.draw.polygon(screen, self.NOSE_COLOR, self._nose_section(0.45))
        pygame.draw.lines(screen, color, True, outline, 1)
        cockpit = self.cockpit()
        pygame.draw.circle(screen, self.COCKPIT_COLOR, (round(cockpit[0]), round(cockpit[1])), 1)
        # The engine sits in the tail notch and marks the back even when it is off
        engine = self._place(self.ENGINE_X, 0.0)
        pygame.draw.circle(
            screen, self.ENGINE_LIT_COLOR if self.pilot_thrusting else self.ENGINE_COLOR,
            (round(engine[0]), round(engine[1])), max(2, round(self.radius * 0.22)))
        # The hunter's gentle thrust rarely reaches plume-length speeds, so hold
        # the cone open while the pilot's engine is on.
        self.draw_thrust_plume(
            screen, config.THRUST_PLUME_LENGTH * 0.6 if self.pilot_thrusting else 0.0)
