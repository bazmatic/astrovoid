"""Crab body for patrol enemies.

A patrol enemy paces back and forth along a line and shoots at the player.
This module draws it as a crab scuttling sideways: the shell lies along the
patrol line, the legs step with real movement, and one oversized cannon claw
swivels to track the player and telegraphs each shot.

The crab is purely visual. Movement, firing and collision stay with the Enemy
and its strategy.
"""

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame
import config
from rendering import visual_effects
from utils import distance, get_angle_to_point

if TYPE_CHECKING:
    from entities.enemy import Enemy

Point = Tuple[float, float]


def _angle_diff(target: float, current: float) -> float:
    """Shortest signed turn in degrees from current to target."""
    return (target - current + 180) % 360 - 180


def _ease(progress: float, span: Tuple[float, float]) -> float:
    """Eased progress (0.0 to 1.0) through a (start, end) span."""
    start, end = span
    t = max(0.0, min(1.0, (progress - start) / (end - start)))
    return t * t * (3.0 - 2.0 * t)


class PatrolCrab:
    """Animation state and drawing for a patrol enemy's crab body.

    Lengths are multiples of the enemy radius, in the crab's own frame:
    "side" runs along the patrol line and "front" is where the eyes point.

    Attributes:
        facing: Direction the eyes point, in degrees. Always across the patrol line.
        walk_phase: Leg cycle phase in radians, driven by distance travelled.
        claw_angle: Direction the cannon claw points, in degrees.
        charge: How close the next shot is (0.0 idle, 1.0 about to fire).
        fire_flash: 1.0 the moment a shot is fired, fading to 0.0.
    """

    SHELL_HALF_WIDTH = 1.05  # Along the patrol line
    SHELL_HALF_DEPTH = 0.72
    SHELL_POINTS = 18
    FACING_TURN_SPEED = 6.0  # Degrees per frame
    LEG_ANGLES = (-48, -17, 15, 44)  # Degrees from the side axis, back to front
    LEG_LENGTH = 0.95
    LEG_STRIDE = 0.3  # Foot swing along the patrol line
    LEG_LIFT = 0.18  # How much a leg tucks in while swinging forward
    GAIT_DISTANCE = 1.6  # Distance travelled per full leg cycle
    EYE_STALKS = ((-0.32, 0.6, -0.4, 1.02), (0.32, 0.6, 0.4, 1.02))  # side, front at root then tip
    CLAW_SHOULDER = (0.72, 0.42)  # Where the cannon claw's arm joins the shell
    SMALL_CLAW_SHOULDER = (-0.72, 0.42)
    CLAW_REACH = 0.75  # Shoulder to claw
    CLAW_RECOIL = 0.35  # Reach lost at the moment of firing
    CLAW_TURN_SPEED = 9.0  # Degrees per frame
    CLAW_PALM_LENGTH = 0.5
    CLAW_PALM_WIDTH = 0.42
    CLAW_FINGER_LENGTH = 0.7
    CLAW_OPEN_MIN = 7.0  # Degrees each pincer opens when idle
    CLAW_OPEN_MAX = 38.0  # ... and when fully charged
    SMALL_CLAW_SCALE = 0.55
    CHARGE_SMOOTHING = 0.2  # Fraction of the gap closed per frame
    FIRE_FLASH_FRAMES = 12.0
    SHADOW_COLOR = (60, 15, 10)
    BELLY_COLOR = (255, 225, 190)
    CHARGE_COLOR = (255, 255, 120)
    # Death animation, as (start, end) spans of the enemy's death_progress
    DEATH_DURATION = 42.0  # Frames (0.7 seconds at 60 FPS)
    DEATH_FRICTION = 0.8  # Velocity kept per frame while the dead crab slides
    DEATH_FLIP = (0.0, 0.4)
    DEATH_CURL = (0.25, 0.7)
    DEATH_FADE = (0.65, 1.0)

    def __init__(self, enemy: 'Enemy'):
        """Initialize the crab for an enemy."""
        self.walk_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.charge = 0.0
        self.fire_flash = 0.0
        self.reset(enemy)

    def reset(self, enemy: 'Enemy') -> None:
        """Square the crab up to the enemy's current patrol line and position."""
        self.facing = (enemy.angle + 90.0) % 360
        self.claw_angle = self.facing
        self._last_pos = (enemy.x, enemy.y)

    def update(self, enemy: 'Enemy', dt: float, player_pos: Optional[Point]) -> None:
        """Advance the gait, claw aim and firing tell.

        Args:
            enemy: The enemy this crab belongs to.
            dt: Delta time since last update.
            player_pos: Current player position, if available.
        """
        # Stay sideways-on to the patrol line. Reversing along the line keeps
        # the same facing, so pick whichever side is nearer.
        ahead = _angle_diff(enemy.angle + 90.0, self.facing)
        behind = _angle_diff(enemy.angle - 90.0, self.facing)
        turn = ahead if abs(ahead) <= abs(behind) else behind
        max_turn = self.FACING_TURN_SPEED * dt
        self.facing = (self.facing + max(-max_turn, min(max_turn, turn))) % 360

        # Legs step with distance covered along the side axis
        side_x, side_y = self._side_axis()
        moved = (enemy.x - self._last_pos[0]) * side_x + (enemy.y - self._last_pos[1]) * side_y
        self.walk_phase += moved / (enemy.radius * self.GAIT_DISTANCE) * 2 * math.pi
        self._last_pos = (enemy.x, enemy.y)

        # Claw tracks the player, or rests pointing forward
        target = get_angle_to_point((enemy.x, enemy.y), player_pos) if player_pos else self.facing
        max_turn = self.CLAW_TURN_SPEED * dt
        swivel = _angle_diff(target, self.claw_angle)
        self.claw_angle = (self.claw_angle + max(-max_turn, min(max_turn, swivel))) % 360

        # Charge follows the strategy's fire cooldown while the player is in range
        target_charge = 0.0
        interval = getattr(enemy.strategy, 'next_fire_interval', 0)
        if player_pos and interval > 0 and distance((enemy.x, enemy.y), player_pos) <= enemy.fire_range:
            target_charge = 1.0 - min(1.0, enemy.strategy.fire_cooldown / interval)
        self.charge += (target_charge - self.charge) * self.CHARGE_SMOOTHING

        self.fire_flash = max(0.0, self.fire_flash - dt / self.FIRE_FLASH_FRAMES)

    def on_fire(self) -> None:
        """Snap the claw shut with a flash: a shot was just fired."""
        self.fire_flash = 1.0
        self.charge = 0.0

    def update_death(self, enemy: 'Enemy', dt: float) -> None:
        """Let the claw go limp while the crab dies."""
        self.charge *= 0.8
        self.fire_flash = max(0.0, self.fire_flash - dt / self.FIRE_FLASH_FRAMES)

    def flip(self, death_progress: float) -> float:
        """How the shell is turned: 1.0 right way up, -1.0 on its back."""
        return math.cos(math.pi * _ease(death_progress, self.DEATH_FLIP))

    def _side_axis(self) -> Point:
        """Unit vector along the shell's width (the patrol line)."""
        side_rad = math.radians(self.facing - 90.0)
        return (math.cos(side_rad), math.sin(side_rad))

    def draw(self, screen: pygame.Surface, enemy: 'Enemy') -> None:
        """Draw the living crab.

        Args:
            screen: The pygame Surface to draw on.
            enemy: The enemy this crab belongs to.
        """
        glow = visual_effects.create_soft_glow_surface(enemy.radius * 2.6, config.COLOR_ENEMY_DYNAMIC, 60)
        screen.blit(glow, glow.get_rect(center=(int(enemy.x), int(enemy.y))))
        self._draw_body(screen, (enemy.x, enemy.y), enemy.radius, 0.0)

    def draw_death(self, screen: pygame.Surface, enemy: 'Enemy') -> None:
        """Draw the dying crab: it flips onto its back, curls its legs in and fades.

        Args:
            screen: The pygame Surface to draw on.
            enemy: The enemy this crab belongs to.
        """
        progress = enemy.death_progress
        fade = _ease(progress, self.DEATH_FADE)
        if fade >= 1.0:
            return
        # Drawn off-screen so the whole crab can fade as one
        size = int(enemy.radius * 6)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        self._draw_body(layer, (size / 2, size / 2), enemy.radius * (1.0 - 0.3 * fade), progress)
        layer.set_alpha(int(255 * (1.0 - fade)))
        screen.blit(layer, layer.get_rect(center=(int(enemy.x), int(enemy.y))))

    def _draw_body(self, target: pygame.Surface, origin: Point, radius: float, death_progress: float) -> None:
        """Draw the crab centred on origin, part-way through dying if death_progress > 0."""
        flip = self.flip(death_progress)
        curl = _ease(death_progress, self.DEATH_CURL)
        upright = flip > 0.0
        side_x, side_y = self._side_axis()
        front_rad = math.radians(self.facing)
        front_x, front_y = math.cos(front_rad), math.sin(front_rad)

        def place(side: float, front: float) -> Point:
            # Rolling over squashes everything along the front axis
            front *= flip
            return (
                origin[0] + (side * side_x + front * front_x) * radius,
                origin[1] + (side * side_y + front * front_y) * radius,
            )

        base = config.COLOR_ENEMY_DYNAMIC
        dark = visual_effects.interpolate_color(base, self.SHADOW_COLOR, 0.55)
        light = visual_effects.interpolate_color(base, (255, 255, 255), 0.4)

        self._draw_legs(target, place, radius, curl, dark, base)

        # The small claw just bobs; the cannon claw aims
        limp = 1.0 - curl
        small_angle = self.facing - 28.0 + 6.0 * math.sin(self.walk_phase)
        self._draw_claw(
            target, place(*self.SMALL_CLAW_SHOULDER), small_angle, radius * self.SMALL_CLAW_SCALE,
            reach=self.CLAW_REACH * limp, opening=self.CLAW_OPEN_MIN, charge=0.0, flash=0.0,
            colors=(dark, base, light)
        )

        self._draw_shell(target, place, radius, upright, dark, base, light)

        if upright:
            eye_radius = max(1, int(round(radius * 0.17)))
            for root_side, root_front, tip_side, tip_front in self.EYE_STALKS:
                tip = place(tip_side, tip_front)
                pygame.draw.line(target, dark, place(root_side, root_front), tip, max(1, int(radius * 0.15)))
                pygame.draw.circle(target, (20, 10, 10), (int(tip[0]), int(tip[1])), eye_radius + 1)
                pygame.draw.circle(target, (255, 250, 220), (int(tip[0]), int(tip[1])), eye_radius)

        # Drawn last: the cannon claw swings over the shell to aim behind
        opening = self.CLAW_OPEN_MIN + (self.CLAW_OPEN_MAX - self.CLAW_OPEN_MIN) * self.charge
        opening *= (1.0 - self.fire_flash) * limp
        reach = (self.CLAW_REACH - self.CLAW_RECOIL * self.fire_flash) * (0.4 + 0.6 * limp)
        self._draw_claw(
            target, place(*self.CLAW_SHOULDER), self.claw_angle, radius,
            reach=reach, opening=opening, charge=self.charge * limp, flash=self.fire_flash * limp,
            colors=(dark, base, light)
        )

    def _draw_legs(self, target: pygame.Surface, place, radius: float, curl: float,
                   dark: Tuple[int, int, int], base: Tuple[int, int, int]) -> None:
        """Draw four pairs of legs stepping in an alternating gait."""
        width = max(1, int(round(radius * 0.2)))
        for side in (-1.0, 1.0):
            for index, leg_angle in enumerate(self.LEG_ANGLES):
                leg_rad = math.radians(leg_angle)
                root = (side * self.SHELL_HALF_WIDTH * 0.8 * math.cos(leg_rad),
                        self.SHELL_HALF_DEPTH * 0.8 * math.sin(leg_rad))
                # Neighbouring legs, and the two sides, step out of phase
                phase = self.walk_phase + index * math.pi + (math.pi if side > 0 else 0.0)
                tuck = 1.0 - self.LEG_LIFT * max(0.0, math.cos(phase))
                # A dead crab's legs fold in over its belly
                length = self.LEG_LENGTH * tuck * (1.0 - 0.75 * curl)
                foot = (root[0] + side * math.cos(leg_rad * 1.2) * length + self.LEG_STRIDE * math.sin(phase) * (1.0 - curl),
                        root[1] + math.sin(leg_rad * 1.2) * length)
                foot = (foot[0] * (1.0 - 0.5 * curl), foot[1] * (1.0 - 0.5 * curl))
                # Knee bows away from the middle legs
                bow = 0.2 if leg_angle > 0 else -0.2
                knee = ((root[0] + foot[0]) / 2 + side * 0.12, (root[1] + foot[1]) / 2 + bow)
                root_px, knee_px, foot_px = place(*root), place(*knee), place(*foot)
                pygame.draw.line(target, dark, root_px, knee_px, width + 1)
                pygame.draw.line(target, base, knee_px, foot_px, width)

    def _draw_shell(self, target: pygame.Surface, place, radius: float, upright: bool,
                    dark: Tuple[int, int, int], base: Tuple[int, int, int], light: Tuple[int, int, int]) -> None:
        """Draw the shell as nested bands, or the pale belly when on its back."""
        def outline(scale: float, shift: float) -> List[Point]:
            points = []
            for i in range(self.SHELL_POINTS):
                theta = 2 * math.pi * i / self.SHELL_POINTS
                cos_t, sin_t = math.cos(theta), math.sin(theta)
                # Squarer than an ellipse, and flatter across the front
                side = math.copysign(abs(cos_t) ** 0.75, cos_t) * self.SHELL_HALF_WIDTH
                front = math.copysign(abs(sin_t) ** 0.75, sin_t) * self.SHELL_HALF_DEPTH
                if front > 0:
                    front *= 0.88
                points.append(place(side * scale, front * scale + shift))
            return points

        if upright:
            layers = ((1.0, 0.0, dark), (0.84, 0.02, base), (0.5, 0.12, light))
        else:
            belly_shade = visual_effects.interpolate_color(self.BELLY_COLOR, base, 0.45)
            layers = ((1.0, 0.0, dark), (0.84, 0.0, belly_shade), (0.55, 0.0, self.BELLY_COLOR))
        rim = outline(1.0, 0.0)
        for scale, shift, color in layers:
            pygame.draw.polygon(target, color, outline(scale, shift))
        pygame.draw.aalines(target, light if upright else self.BELLY_COLOR, True, rim)

        spot_radius = max(1, int(round(radius * 0.11)))
        if upright:
            for side, front in ((-0.45, -0.22), (0.0, -0.36), (0.45, -0.22)):
                spot = place(side, front)
                pygame.draw.circle(target, dark, (int(spot[0]), int(spot[1])), spot_radius)
        else:
            # Segments of the folded tail
            for front in (-0.3, 0.0, 0.3):
                pygame.draw.line(target, dark, place(-0.3, front), place(0.3, front), 1)

    def _draw_claw(self, target: pygame.Surface, shoulder: Point, angle: float, size: float, *,
                   reach: float, opening: float, charge: float, flash: float,
                   colors: Tuple[Tuple[int, int, int], ...]) -> None:
        """Draw a claw on its arm.

        Args:
            target: Surface to draw on.
            shoulder: Where the arm joins the shell, in pixels.
            angle: Direction the claw points, in degrees.
            size: Pixel length of one unit (the radius, or less for the small claw).
            reach: Distance from shoulder to claw, in units.
            opening: Degrees each pincer swings away from the centre line.
            charge: Glow between the pincers (0.0 to 1.0).
            flash: Muzzle flash (0.0 to 1.0).
            colors: (dark, base, light).
        """
        dark, base, light = colors
        aim_rad = math.radians(angle)
        aim_x, aim_y = math.cos(aim_rad), math.sin(aim_rad)

        def along(forward: float, across: float) -> Point:
            return (
                shoulder[0] + ((reach + forward) * aim_x - across * aim_y) * size,
                shoulder[1] + ((reach + forward) * aim_y + across * aim_x) * size,
            )

        wrist = along(0.0, 0.0)
        pygame.draw.line(target, dark, shoulder, wrist, max(2, int(round(size * 0.3))))

        knuckle = along(self.CLAW_PALM_LENGTH * 0.6, 0.0)
        if charge > 0.05 or flash > 0.0:
            mouth = along(self.CLAW_PALM_LENGTH + self.CLAW_FINGER_LENGTH * 0.4, 0.0)
            # Stepped alpha keeps the glow cache small
            glow_alpha = int(min(1.0, charge + flash) * 255) // 15 * 15
            if glow_alpha > 0:
                glow_radius = int(size * (1.0 + 0.8 * charge + 1.2 * flash) / 2) * 2
                glow = visual_effects.create_soft_glow_surface(glow_radius, self.CHARGE_COLOR, glow_alpha)
                target.blit(glow, glow.get_rect(center=(int(mouth[0]), int(mouth[1]))))

        # Two pincers hinged at the knuckle, heating up as the shot charges
        finger_color = visual_effects.interpolate_color(base, self.CHARGE_COLOR, max(charge, flash))
        for sign in (-1.0, 1.0):
            finger_rad = aim_rad + sign * math.radians(opening)
            tip = (knuckle[0] + math.cos(finger_rad) * self.CLAW_FINGER_LENGTH * size * 1.3,
                   knuckle[1] + math.sin(finger_rad) * self.CLAW_FINGER_LENGTH * size * 1.3)
            finger = [
                along(self.CLAW_PALM_LENGTH * 0.3, sign * self.CLAW_PALM_WIDTH),
                tip,
                along(self.CLAW_PALM_LENGTH * 0.5, sign * 0.04),
            ]
            pygame.draw.polygon(target, finger_color, finger)
            pygame.draw.aalines(target, light, False, finger[:2])

        palm = [
            along(-0.1, -self.CLAW_PALM_WIDTH * 0.7),
            along(self.CLAW_PALM_LENGTH * 0.45, -self.CLAW_PALM_WIDTH),
            along(self.CLAW_PALM_LENGTH * 0.7, 0.0),
            along(self.CLAW_PALM_LENGTH * 0.45, self.CLAW_PALM_WIDTH),
            along(-0.1, self.CLAW_PALM_WIDTH * 0.7),
        ]
        pygame.draw.polygon(target, base, palm)
        pygame.draw.aalines(target, dark, True, palm)

        if flash > 0.3:
            muzzle = along(self.CLAW_PALM_LENGTH + self.CLAW_FINGER_LENGTH * 0.6, 0.0)
            pygame.draw.circle(target, (255, 255, 255), (int(muzzle[0]), int(muzzle[1])),
                               max(1, int(round(size * 0.35 * flash))))
