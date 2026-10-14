"""Allied spacecraft executing pilot inputs using the shared flight physics."""
import math
import pygame
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.tentacle_chain import drag_chain
from entities.projectile import Projectile
from game_handlers.fire_rate_calculator import calculate_fire_cooldown, shots_per_volley
from hunter.model import HunterSettings


class HunterShip(RotatingThrusterShip):
    # Green marks an ally: the player is blue, enemies are red, orange and purple.
    COLOR = (120, 255, 90)
    FILL = (25, 110, 40)
    NOSE_COLOR = (215, 255, 200)  # Pale head and belly, so the front reads at a glance
    COCKPIT_COLOR = (15, 60, 30)  # The eyes' pupils
    ENGINE_COLOR = (170, 95, 20)  # Amber mark at the tail root, engine off
    ENGINE_LIT_COLOR = (255, 200, 80)  # ... and engine on
    # A fish seen from above, in multiples of the radius: x along the heading, y across it. The head is blunt and
    # the body tapers to a narrow tail root, from which a chain of segments trails: it is towed like a rope, so it
    # lags behind a turn and whips back, and a pilot that flips left and right makes the tail wave.
    FISH_NOSE_X = 1.6
    FISH_TAIL_ROOT_X = -0.9
    FISH_WIDTH = 0.66
    FISH_WIDEST_X = 0.45
    EYE_X = 0.95
    EYE_HALF_SPAN = 0.36
    ENGINE_X = -0.62
    TAIL_SEGMENTS = 6
    TAIL_SEGMENT = 0.38           # length of one tail segment
    TAIL_STIFFNESS_BASE = 0.30
    TAIL_STIFFNESS_TIP = 0.08
    TAIL_HALF_WIDTH_ROOT = 0.30
    TAIL_HALF_WIDTH_TIP = 0.14
    TAIL_FIN_SPAN = 0.95
    # The old arrowhead, which the Jev beacon pickup still draws as its icon (entities/jev_beacon.py)
    NOSE_X = 1.4
    WING_X = -0.9
    WING_HALF_SPAN = 0.85
    NOTCH_X = -0.35
    BURN_ALIGNMENT_DEGREES = 5.0  # How close to a course's burn heading the nose must be to thrust
    LOOSE_BURN_ALIGNMENT_DEGREES = 20.0  # The same for a burn made while the nose is not the navigator's

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
        self._hit = None  # strongest collision push since the senses last read it
        self._tail = None  # the tail chain's points, root first, in world space
        self._swim_phase = 0.0  # drives the tail's gentle swimming wave
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
        self._drag_tail(dt)
        return shots

    def register_hit(self, dvx, dvy):
        """A collision changed this ship's velocity by (dvx, dvy). Only the strongest since the last read is kept."""
        if self._hit is None or dvx * dvx + dvy * dvy > self._hit[0] ** 2 + self._hit[1] ** 2:
            self._hit = (dvx, dvy)

    def take_hit(self):
        """The strongest hit since the last call as (dvx, dvy), or None; reading it clears it."""
        hit, self._hit = self._hit, None
        return hit

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
        """The body as a polygon, nose first: down one side to the tail root and back up the other."""
        xs = [self.FISH_NOSE_X - (self.FISH_NOSE_X - self.FISH_TAIL_ROOT_X) * i / 11 for i in range(12)]
        side = [(x, self._half_width(x)) for x in xs]
        return [self._place(x, y) for x, y in side] + [self._place(x, -y) for x, y in reversed(side[1:-1])]

    def _half_width(self, x):
        """How far the body reaches to each side of the spine at x."""
        if x >= self.FISH_WIDEST_X:
            reach = self.FISH_NOSE_X - self.FISH_WIDEST_X
            return self.FISH_WIDTH * math.sqrt(max(0.0, 1.0 - ((x - self.FISH_WIDEST_X) / reach) ** 2))
        run = (x - self.FISH_TAIL_ROOT_X) / (self.FISH_WIDEST_X - self.FISH_TAIL_ROOT_X)
        return self.TAIL_HALF_WIDTH_ROOT + (self.FISH_WIDTH - self.TAIL_HALF_WIDTH_ROOT) * max(0.0, run) ** 0.8

    def eyes(self):
        """Where the two eyes sit, either side of the head."""
        return [self._place(self.EYE_X, self.EYE_HALF_SPAN), self._place(self.EYE_X, -self.EYE_HALF_SPAN)]

    def _front_part(self, back_x, shrink=1.0):
        """The body ahead of back_x, narrowed by `shrink`: a lighter patch laid over the body."""
        xs = [self.FISH_NOSE_X - (self.FISH_NOSE_X - back_x) * i / 7 for i in range(8)]
        side = [(x, self._half_width(x) * shrink) for x in xs]
        return [self._place(x, y) for x, y in side] + [self._place(x, -y) for x, y in reversed(side[1:-1])]

    def _drag_tail(self, dt=1.0, snap=False):
        """Tow the tail behind the body. It swims in a gentle wave that grows with speed."""
        speed = math.hypot(self.vx, self.vy)
        self._swim_phase += dt * (0.22 + 0.05 * speed)
        swing = 0.45 + 0.5 * min(1.0, speed / max(self.max_speed, 1e-6))
        behind = math.radians(self.angle) + math.pi
        phase = self._swim_phase
        anchor = self._place(self.FISH_TAIL_ROOT_X, 0.0)
        if self._tail is None:
            self._tail = [anchor] * (self.TAIL_SEGMENTS + 1)
            snap = True
        elif math.hypot(self._tail[0][0] - anchor[0], self._tail[0][1] - anchor[1]) > self.radius * 3:
            snap = True               # a jump (a respawn): do not stretch the tail across the screen

        def rest_angle(i, t):
            return behind + math.sin(phase - i * 0.9) * swing * t

        drag_chain(self._tail, anchor, self.TAIL_SEGMENT * self.radius, rest_angle,
                   self.TAIL_STIFFNESS_BASE, self.TAIL_STIFFNESS_TIP, snap)

    def _tail_pieces(self):
        """The tail as one quad per segment, tapering along the chain (robust where the chain bends sharply)."""
        edges = []
        last = len(self._tail) - 1
        for i, (x, y) in enumerate(self._tail):
            before = self._tail[max(i - 1, 0)]
            after = self._tail[min(i + 1, last)]
            dx, dy = after[0] - before[0], after[1] - before[1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            half = (self.TAIL_HALF_WIDTH_ROOT + (self.TAIL_HALF_WIDTH_TIP - self.TAIL_HALF_WIDTH_ROOT) * i / last) * self.radius
            edges.append(((x + nx * half, y + ny * half), (x - nx * half, y - ny * half)))
        return [[edges[i][0], edges[i + 1][0], edges[i + 1][1], edges[i][1]] for i in range(last)]

    def _tail_fin(self):
        """The forked fin at the end of the tail: two lobes with a notch between them."""
        (x1, y1), (x2, y2) = self._tail[-2], self._tail[-1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        span = self.TAIL_FIN_SPAN * self.radius
        reach = self.TAIL_SEGMENT * self.radius * 1.3
        return [(x2 - ux * reach * 0.15, y2 - uy * reach * 0.15),
                (x2 + ux * reach + nx * span, y2 + uy * reach + ny * span),
                (x2 + ux * reach * 0.45, y2 + uy * reach * 0.45),
                (x2 + ux * reach - nx * span, y2 + uy * reach - ny * span)]

    def _side_fins(self):
        """Two small pectoral fins swept back from the sides of the body."""
        fins = []
        for sign in (1, -1):
            fins.append([self._place(0.35, sign * self._half_width(0.35) * 0.9),
                         self._place(-0.15, sign * (self._half_width(-0.15) + 0.55)),
                         self._place(-0.35, sign * self._half_width(-0.35) * 0.9)])
        return fins

    def draw(self, screen):
        if not self.active:
            return
        color = self.COLOR
        if self.immunity_remaining and int(self.immunity_remaining * 20) % 2:
            color = (235, 255, 230)
        if self._tail is None:
            self._drag_tail(snap=True)
        # The engine's flame goes first, so the fish is drawn over it
        self.draw_thrust_plume(
            screen, config.THRUST_PLUME_LENGTH * 0.6 if self.pilot_thrusting else 0.0)
        middle = tuple((a + b) // 2 for a, b in zip(self.FILL, self.COLOR))
        # The tail is a mid green and its fin the body's own, so it reads against the dark maze
        for piece in self._tail_pieces():
            pygame.draw.polygon(screen, middle, piece)
            pygame.draw.polygon(screen, middle, piece, 1)    # closes the hairline gaps between pieces
        fin = self._tail_fin()
        pygame.draw.polygon(screen, self.COLOR, fin)
        pygame.draw.lines(screen, color, True, fin, 1)
        for side_fin in self._side_fins():
            pygame.draw.polygon(screen, middle, side_fin)
            pygame.draw.lines(screen, color, True, side_fin, 1)
        outline = self.outline()
        # Dark at the tail root, brightening in two steps to a pale head
        pygame.draw.polygon(screen, self.FILL, outline)
        pygame.draw.polygon(screen, middle, self._front_part(-0.35))
        pygame.draw.polygon(screen, self.NOSE_COLOR, self._front_part(0.55, 0.6))
        pygame.draw.lines(screen, color, True, outline, 1)
        for eye in self.eyes():
            pygame.draw.circle(screen, (255, 255, 255), (round(eye[0]), round(eye[1])), max(1, round(self.radius * 0.2)))
            pygame.draw.circle(screen, self.COCKPIT_COLOR, (round(eye[0]), round(eye[1])), max(1, round(self.radius * 0.1)))
        # The engine glows where the tail joins the body, and marks the back even when it is off
        engine = self._place(self.ENGINE_X, 0.0)
        pygame.draw.circle(
            screen, self.ENGINE_LIT_COLOR if self.pilot_thrusting else self.ENGINE_COLOR,
            (round(engine[0]), round(engine[1])), max(2, round(self.radius * 0.22)))
