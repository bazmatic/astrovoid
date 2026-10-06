"""Sea urchin body for static enemies.

A static enemy sits still, hurts on contact, takes several hits to kill and
gets knocked across the floor by each one. This module draws it as a sea
urchin: a dome covered in spines that bristle at a nearby player, roll with
every knock and snap off as it takes damage.

The urchin is purely visual. Momentum, hit points and collision stay with the
Enemy and its strategy.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame
import config
from rendering import visual_effects
from utils import distance, get_angle_to_point

if TYPE_CHECKING:
    from entities.enemy import Enemy

Point = Tuple[float, float]


@dataclass
class Shard:
    """A snapped-off spine tumbling away."""
    x: float
    y: float
    vx: float
    vy: float
    angle: float  # Degrees
    spin: float  # Degrees per frame
    length: float  # Pixels
    life: float = 1.0  # 1.0 fresh, 0.0 gone


class Urchin:
    """Animation state and drawing for a static enemy's sea urchin body.

    Lengths are multiples of the enemy radius.

    Attributes:
        roll: Rotation of the spines in degrees; it turns as the urchin slides.
        alarm: 0.0 calm, 1.0 bristling at a nearby player.
        squash: 0.0 round, 1.0 flattened by an impact.
        spine_intact: Whether each main spine is still whole.
        shards: Snapped-off spines still flying.
    """

    SPINE_COUNT = 16  # Main spines, which snap off with damage
    SPINE_LENGTH = 1.3  # Centre to tip of the longest spine
    SPINE_STUB_LENGTH = 0.72  # Centre to the end of a snapped spine
    SHORT_SPINE_LENGTH = 0.9  # Fixed spines between the main ones
    SPINE_SWAY_ANGLE = 5.0  # Degrees
    SWAY_SPEED = 0.05  # Radians per frame
    BODY_RADIUS = 0.58
    BODY_POINTS = 20
    ALARM_RANGE = 90.0  # Pixels within which the player makes it bristle
    ALARM_SMOOTHING = 0.12  # Fraction of the gap closed per frame
    BRISTLE_STRETCH = 0.3  # Extra reach of a spine pointing straight at the player
    SQUASH_THRESHOLD = 0.5  # Velocity jump (pixels per frame) that counts as an impact
    SQUASH_FULL = 3.0  # Velocity jump that flattens it completely
    SQUASH_DECAY = 0.85  # Squash kept per frame
    SHARD_FRAMES = 24.0  # How long a snapped spine stays visible
    SHARD_FRICTION = 0.9
    SHADOW_COLOR = (50, 5, 20)
    # Death animation
    DEATH_DURATION = 36.0  # Frames (0.6 seconds at 60 FPS)
    DEATH_FRICTION = 0.9  # Velocity kept per frame while the pieces drift
    SHELL_PIECES = 5
    SHELL_SPREAD = 0.9  # How far the shell pieces drift apart

    def __init__(self, enemy: 'Enemy'):
        """Initialize the urchin for an enemy."""
        self.roll = random.uniform(0, 360)
        self.sway_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.alarm = 0.0
        self.squash = 0.0
        self.shards: List[Shard] = []
        self.spine_intact = [True] * self.SPINE_COUNT
        # Every urchin is a little different
        self._spine_scale = [random.uniform(0.8, 1.0) for _ in range(self.SPINE_COUNT)]
        self._break_order = random.sample(range(self.SPINE_COUNT), self.SPINE_COUNT)
        self._player_angle = 0.0
        self._squash_angle = 0.0
        self._last_pos = (enemy.x, enemy.y)
        self._last_velocity = (enemy.vx, enemy.vy)
        self._burst = False

    @property
    def intact_spines(self) -> int:
        """Number of main spines still whole."""
        return sum(self.spine_intact)

    def _spine_angle(self, index: int) -> float:
        """Direction a main spine points, in degrees, before any sway."""
        return self.roll + index * 360.0 / self.SPINE_COUNT

    def spine_reach(self, index: int) -> float:
        """Distance from the centre to a main spine's tip.

        Spines pointing at a nearby player stretch out; snapped ones are stubs.
        """
        if not self.spine_intact[index]:
            return self.SPINE_STUB_LENGTH
        facing = math.cos(math.radians(self._spine_angle(index) - self._player_angle))
        bristle = max(0.0, facing) ** 2 * self.alarm
        return self.SPINE_LENGTH * self._spine_scale[index] * (1.0 + self.BRISTLE_STRETCH * bristle)

    def shell_spread(self, death_progress: float) -> float:
        """How far the shell pieces have drifted from the centre on death."""
        return self.SHELL_SPREAD * death_progress * (2.0 - death_progress)

    def update(self, enemy: 'Enemy', dt: float, player_pos: Optional[Point] = None) -> None:
        """Advance rolling, bristling, impacts and broken spines.

        Args:
            enemy: The enemy this urchin belongs to.
            dt: Delta time since last update.
            player_pos: Current player position, if available.
        """
        self.sway_phase += dt * self.SWAY_SPEED
        self._roll_and_squash(enemy)

        near = player_pos is not None and distance((enemy.x, enemy.y), player_pos) <= self.ALARM_RANGE
        if player_pos is not None:
            self._player_angle = get_angle_to_point((enemy.x, enemy.y), player_pos)
        self.alarm += ((1.0 if near else 0.0) - self.alarm) * self.ALARM_SMOOTHING

        # Spines left standing track the share of hit points left
        health = max(0.0, enemy.hit_points / enemy.max_hit_points)
        self._snap_spines(enemy, math.ceil(self.SPINE_COUNT * health), speed=(1.2, 2.4))
        self._update_shards(dt)

    def update_death(self, enemy: 'Enemy', dt: float) -> None:
        """Burst the remaining spines outward and let the pieces drift."""
        self._ensure_burst(enemy)
        self._roll_and_squash(enemy)
        self._update_shards(dt)

    def _ensure_burst(self, enemy: 'Enemy') -> None:
        """Throw off every remaining spine, once, when the urchin dies."""
        if not self._burst:
            self._burst = True
            self._snap_spines(enemy, 0, speed=(2.0, 4.0))

    def _roll_and_squash(self, enemy: 'Enemy') -> None:
        """Turn with distance covered and flatten on a sudden change of velocity."""
        dx = enemy.x - self._last_pos[0]
        dy = enemy.y - self._last_pos[1]
        self._last_pos = (enemy.x, enemy.y)
        # Seen from above there is no true rolling axis, so spin one way for
        # rightward or downward travel and the other way for the reverse
        direction = math.copysign(1.0, dx if abs(dx) >= abs(dy) else dy)
        self.roll += direction * math.degrees(math.hypot(dx, dy) / enemy.radius)

        # Friction changes velocity gradually; a hit or a wall bounce jumps it
        jump_x = enemy.vx - self._last_velocity[0]
        jump_y = enemy.vy - self._last_velocity[1]
        self._last_velocity = (enemy.vx, enemy.vy)
        jump = math.hypot(jump_x, jump_y)
        if jump > self.SQUASH_THRESHOLD:
            self.squash = min(1.0, jump / self.SQUASH_FULL)
            self._squash_angle = math.atan2(jump_y, jump_x)
        else:
            self.squash *= self.SQUASH_DECAY
            if self.squash < 0.005:
                self.squash = 0.0

    def _snap_spines(self, enemy: 'Enemy', keep: int, speed: Tuple[float, float]) -> None:
        """Snap spines off until only `keep` are left, sending each one flying."""
        for index in self._break_order:
            if self.intact_spines <= keep:
                break
            if not self.spine_intact[index]:
                continue
            reach = self.spine_reach(index)
            self.spine_intact[index] = False
            angle = self._spine_angle(index)
            angle_rad = math.radians(angle)
            cos_angle, sin_angle = math.cos(angle_rad), math.sin(angle_rad)
            launch = random.uniform(*speed)
            middle = (self.SPINE_STUB_LENGTH + reach) / 2 * enemy.radius
            self.shards.append(Shard(
                x=enemy.x + cos_angle * middle,
                y=enemy.y + sin_angle * middle,
                vx=enemy.vx + cos_angle * launch,
                vy=enemy.vy + sin_angle * launch,
                angle=angle,
                spin=random.uniform(-12.0, 12.0),
                length=(reach - self.SPINE_STUB_LENGTH) * enemy.radius,
            ))

    def _update_shards(self, dt: float) -> None:
        """Move snapped spines along and drop the ones that have faded."""
        for shard in self.shards:
            shard.x += shard.vx * dt
            shard.y += shard.vy * dt
            shard.vx *= self.SHARD_FRICTION
            shard.vy *= self.SHARD_FRICTION
            shard.angle += shard.spin * dt
            shard.life -= dt / self.SHARD_FRAMES
        self.shards = [shard for shard in self.shards if shard.life > 0.0]

    def draw(self, screen: pygame.Surface, enemy: 'Enemy') -> None:
        """Draw the living urchin.

        Args:
            screen: The pygame Surface to draw on.
            enemy: The enemy this urchin belongs to.
        """
        base = config.COLOR_ENEMY_STATIC
        center = (int(enemy.x), int(enemy.y))
        # Stepped alpha keeps the glow cache small
        glow_alpha = int(50 + 50 * self.alarm) // 10 * 10
        glow = visual_effects.create_soft_glow_surface(enemy.radius * 2.2, base, glow_alpha)
        screen.blit(glow, glow.get_rect(center=center))

        self._draw_spines(screen, (enemy.x, enemy.y), enemy.radius)
        self._draw_shell(screen, (enemy.x, enemy.y), enemy.radius, 0.0)
        if self.shards:
            self._draw_shards(screen, enemy, 1.0)

    def draw_death(self, screen: pygame.Surface, enemy: 'Enemy') -> None:
        """Draw the dying urchin: spines burst outward and the shell cracks apart.

        Args:
            screen: The pygame Surface to draw on.
            enemy: The enemy this urchin belongs to.
        """
        progress = enemy.death_progress
        if progress >= 1.0:
            return
        self._ensure_burst(enemy)
        visibility = 1.0 - progress * progress
        # Drawn off-screen so the pieces can fade
        size = int(enemy.radius * 5)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        self._draw_shell(layer, (size / 2, size / 2), enemy.radius, progress)
        layer.set_alpha(int(255 * visibility))
        screen.blit(layer, layer.get_rect(center=(int(enemy.x), int(enemy.y))))
        self._draw_shards(screen, enemy, visibility)

    def _squashed(self, offset_x: float, offset_y: float) -> Point:
        """Flatten an offset from the centre along the direction of the last impact."""
        if self.squash <= 0.0:
            return (offset_x, offset_y)
        normal_x, normal_y = math.cos(self._squash_angle), math.sin(self._squash_angle)
        along = offset_x * normal_x + offset_y * normal_y
        across_x, across_y = offset_x - along * normal_x, offset_y - along * normal_y
        along *= 1.0 - 0.35 * self.squash
        bulge = 1.0 + 0.18 * self.squash
        return (along * normal_x + across_x * bulge, along * normal_y + across_y * bulge)

    def _draw_spines(self, target: pygame.Surface, origin: Point, radius: float) -> None:
        """Draw the spines: short fixed ones, then the main ones that can snap."""
        base = config.COLOR_ENEMY_STATIC
        dark = visual_effects.interpolate_color(base, self.SHADOW_COLOR, 0.45)
        spine_color = visual_effects.interpolate_color(base, (255, 255, 255), 0.25)
        tip_color = visual_effects.interpolate_color(base, (255, 255, 255), 0.5 + 0.5 * self.alarm)
        # A bristling urchin holds its spines rigid
        sway = self.SPINE_SWAY_ANGLE * (1.0 - self.alarm)

        def point(angle: float, reach: float) -> Point:
            angle_rad = math.radians(angle)
            offset = self._squashed(math.cos(angle_rad) * reach * radius, math.sin(angle_rad) * reach * radius)
            return (origin[0] + offset[0], origin[1] + offset[1])

        root = self.BODY_RADIUS * 0.85
        half_step = 180.0 / self.SPINE_COUNT
        for index in range(self.SPINE_COUNT):
            angle = self._spine_angle(index) + half_step
            pygame.draw.aaline(target, dark, point(angle, root), point(angle, self.SHORT_SPINE_LENGTH))

        for index in range(self.SPINE_COUNT):
            angle = self._spine_angle(index) + sway * math.sin(self.sway_phase + index * 1.7)
            reach = self.spine_reach(index)
            root_px = point(angle, root)
            if not self.spine_intact[index]:
                pygame.draw.line(target, dark, root_px, point(angle, reach), 2)
                continue
            tip_px = point(angle, reach)
            # Thick at the root, fine at the tip
            pygame.draw.line(target, dark, root_px, point(angle, (root + reach) / 2), 2)
            pygame.draw.aaline(target, spine_color, root_px, tip_px)
            target.set_at((int(tip_px[0]), int(tip_px[1])), tip_color)

    def _draw_shell(self, target: pygame.Surface, origin: Point, radius: float, death_progress: float) -> None:
        """Draw the domed shell, in pieces drifting apart if it is dying."""
        base = config.COLOR_ENEMY_STATIC
        dark = visual_effects.interpolate_color(base, self.SHADOW_COLOR, 0.6)
        light = visual_effects.interpolate_color(base, (255, 255, 255), 0.45)
        spread = self.shell_spread(death_progress)
        body = self.BODY_RADIUS
        piece_span = 360.0 / self.SHELL_PIECES
        points_per_piece = max(2, self.BODY_POINTS // self.SHELL_PIECES)

        for piece in range(self.SHELL_PIECES):
            start = self.roll + piece * piece_span
            drift_rad = math.radians(start + piece_span / 2)
            drift = (math.cos(drift_rad) * spread * radius, math.sin(drift_rad) * spread * radius)

            def wedge(scale: float) -> List[Point]:
                points = [(origin[0] + drift[0], origin[1] + drift[1])]
                for j in range(points_per_piece + 1):
                    angle_rad = math.radians(start + piece_span * j / points_per_piece)
                    offset = self._squashed(
                        math.cos(angle_rad) * body * scale * radius,
                        math.sin(angle_rad) * body * scale * radius
                    )
                    points.append((origin[0] + drift[0] + offset[0], origin[1] + drift[1] + offset[1]))
                return points

            pygame.draw.polygon(target, dark, wedge(1.0))
            pygame.draw.polygon(target, base, wedge(0.8))
            if death_progress > 0.0:
                # Cracked edges catch the light
                edge = wedge(1.0)
                pygame.draw.line(target, light, edge[0], edge[1], 1)

        if death_progress > 0.0:
            return
        # Highlight from a fixed light at the top left, and the five-fold
        # pattern every urchin shell has
        highlight = self._squashed(-body * 0.28 * radius, -body * 0.28 * radius)
        pygame.draw.circle(
            target, light, (int(origin[0] + highlight[0]), int(origin[1] + highlight[1])),
            max(1, int(round(body * 0.3 * radius)))
        )
        for petal in range(5):
            petal_rad = math.radians(self.roll + petal * 72.0)
            offset = self._squashed(
                math.cos(petal_rad) * body * 0.55 * radius, math.sin(petal_rad) * body * 0.55 * radius
            )
            target.set_at((int(origin[0] + offset[0]), int(origin[1] + offset[1])), dark)

    def _draw_shards(self, screen: pygame.Surface, enemy: 'Enemy', visibility: float) -> None:
        """Draw snapped spines tumbling away and fading."""
        spine_color = visual_effects.interpolate_color(config.COLOR_ENEMY_STATIC, (255, 255, 255), 0.25)
        for shard in self.shards:
            alpha = int(255 * max(0.0, min(1.0, shard.life * 1.5)) * visibility)
            if alpha <= 0:
                continue
            size = int(shard.length) + 4
            layer = pygame.Surface((size, size), pygame.SRCALPHA)
            angle_rad = math.radians(shard.angle)
            half_x = math.cos(angle_rad) * shard.length / 2
            half_y = math.sin(angle_rad) * shard.length / 2
            middle = size / 2
            pygame.draw.line(
                layer, (*spine_color, alpha),
                (middle - half_x, middle - half_y), (middle + half_x, middle + half_y), 1
            )
            screen.blit(layer, layer.get_rect(center=(int(shard.x), int(shard.y))))
