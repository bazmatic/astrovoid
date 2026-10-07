"""Anemone enemy that pulls the player's ship toward it.

An anemone is rooted to one spot. It draws the ship in whenever it has a clear
line to it, stings and flings the ship on contact, and clamps shut for a
moment when shot, which stops the pull.
"""

import math
from typing import Optional, Tuple

import pygame
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from rendering import visual_effects
from utils import circle_circle_collision, line_line_collision


def pull_acceleration(
    anemone_pos: Tuple[float, float],
    anemone_radius: float,
    ship_pos: Tuple[float, float],
    ship_radius: float,
    reach: float,
    peak_pull: float
) -> Tuple[float, float]:
    """Acceleration an anemone gives a ship, ignoring walls and state.

    Zero at the edge of reach, rising linearly to peak_pull where the two
    hulls touch, and directed at the anemone.

    Args:
        anemone_pos: Centre of the anemone.
        anemone_radius: Radius of the anemone.
        ship_pos: Centre of the ship.
        ship_radius: Radius of the ship.
        reach: Distance from the anemone's centre at which the pull ends.
        peak_pull: Acceleration per frame where the hulls touch.

    Returns:
        (ax, ay) to add to the ship's velocity.
    """
    dx, dy = anemone_pos[0] - ship_pos[0], anemone_pos[1] - ship_pos[1]
    dist = math.hypot(dx, dy)
    contact = anemone_radius + ship_radius
    if dist <= 1e-6 or dist >= reach or reach <= contact:
        return (0.0, 0.0)
    strength = peak_pull * min(1.0, max(0.0, 1.0 - (dist - contact) / (reach - contact)))
    return (dx / dist * strength, dy / dist * strength)


def apply_pull(ship, ax: float, ay: float) -> None:
    """Add a pull to a ship's velocity, holding its speed to its normal maximum.

    The pull is added once per update, as thrust is.
    """
    ship.vx += ax
    ship.vy += ay
    speed = math.hypot(ship.vx, ship.vy)
    if speed > ship.max_speed:
        scale = ship.max_speed / speed
        ship.vx *= scale
        ship.vy *= scale


class Anemone(GameEntity, Collidable, Drawable):
    """Rooted enemy that pulls the player's ship toward it.

    Attributes:
        hit_points: Hits it can still take.
        stun_timer: Frames left clamped shut, during which it does not pull.
        stun_total: Length of the stun now running (for the reopening animation).
        pull_fraction: Strength of the pull applied this frame (0.0 to 1.0 of the peak).
        pull_angle: Direction from the anemone to the ship it is pulling, in radians.
        reach_px: Reach in pixels, known once it has been asked to pull.
    """

    DEATH_DURATION = 30.0  # Frames (0.5 seconds at 60 FPS)

    # Drawing constants (lengths are multiples of the radius unless noted)
    TENTACLES = 12
    TENTACLE_SEGMENTS = 4
    TENTACLE_ROOT = 0.6  # Distance of the tentacle ring from the centre
    TENTACLE_LENGTH = 1.3
    TENTACLE_LEAN = 0.9  # How far tips swing toward a pulled ship, in radians, at full pull
    COLUMN_RADIUS = 0.8
    MOUTH_RADIUS = 0.32
    SHADOW_COLOR = (40, 12, 34)
    MOUTH_COLOR = (60, 10, 40)
    DULL_COLOR = (90, 80, 100)  # What its colours fade toward when clamped shut
    STREAKS = 10
    STREAK_SPEED = 0.006  # Fraction of the reach a streak drifts inward per frame
    STREAK_STRENGTH = 0.22  # How far streaks stand out from the background (0 to 1)
    REOPEN_FRACTION = 1 / 3  # Share of a stun spent reopening

    def __init__(self, pos: Tuple[float, float]):
        """Initialize an anemone rooted at a position.

        Args:
            pos: Position as (x, y) tuple.
        """
        super().__init__(pos, config.ANEMONE_SIZE)
        self.anchor = (float(pos[0]), float(pos[1]))
        self.hit_points = config.ANEMONE_HIT_POINTS
        self.max_hit_points = config.ANEMONE_HIT_POINTS
        self.stun_timer = 0.0
        self.stun_total = 0.0
        self.pull_fraction = 0.0
        self.pull_angle = 0.0
        self.reach_px = 0.0
        self.sway_phase = 0.0
        self.streak_phase = 0.0

    @property
    def is_stunned(self) -> bool:
        """Whether it is clamped shut and not pulling."""
        return self.stun_timer > 0.0

    @property
    def closed_fraction(self) -> float:
        """How tightly it is clamped shut: 1.0 while stunned, easing to 0.0 as the stun ends."""
        if self.stun_timer <= 0.0 or self.stun_total <= 0.0:
            return 0.0
        return min(1.0, self.stun_timer / (self.stun_total * self.REOPEN_FRACTION))

    def stun(self, frames: float) -> None:
        """Clamp shut for a number of frames. Never shortens a stun already running."""
        if frames > self.stun_timer:
            self.stun_timer = float(frames)
            self.stun_total = float(frames)

    def take_damage(self) -> bool:
        """Take damage from a projectile hit.

        Returns:
            True if hit points reached 0, False otherwise.
        """
        self.hit_points -= 1
        return self.hit_points <= 0

    def apply_momentum(self, _vx: float, _vy: float) -> None:
        """Anemones are rooted; momentum does not move them."""
        return

    def reach(self, maze) -> float:
        """Distance from its centre at which the pull ends, for a maze's cell size."""
        return config.ANEMONE_REACH_CELLS * (maze.cell_size_x + maze.cell_size_y) / 2

    def _wall_between(self, pos: Tuple[float, float], maze) -> bool:
        """Whether an active wall crosses the line from the anemone to a position."""
        walls = maze.walls
        if maze.spatial_grid is not None:
            walls = maze.spatial_grid.get_walls_along_path(self.get_pos(), pos, 0.0)
        return any(
            wall.active and line_line_collision(self.get_pos(), pos, wall.start, wall.end)
            for wall in walls
        )

    def pull_on(self, ship, maze) -> Tuple[float, float]:
        """Acceleration this anemone gives the ship right now.

        Returns:
            (ax, ay), or (0.0, 0.0) when it is dead or stunned, the ship is
            inactive or shielded, out of reach, or behind a wall.
        """
        self.reach_px = self.reach(maze)
        if not self.active or self.is_stunned or not ship.active or ship.is_shield_active():
            return (0.0, 0.0)
        pull = pull_acceleration(
            self.get_pos(), self.radius, ship.get_pos(), ship.radius, self.reach_px,
            config.ANEMONE_PULL_THRUST_FRACTION * config.SHIP_THRUST_FORCE
        )
        if pull == (0.0, 0.0) or self._wall_between(ship.get_pos(), maze):
            return (0.0, 0.0)
        return pull

    def reach_for(self, ship, maze) -> Tuple[float, float]:
        """Work out this frame's pull on the ship and remember it for drawing, without applying it.

        Returns:
            The (ax, ay) this anemone wants to give the ship.
        """
        ax, ay = self.pull_on(ship, maze)
        peak = config.ANEMONE_PULL_THRUST_FRACTION * config.SHIP_THRUST_FORCE
        self.pull_fraction = math.hypot(ax, ay) / peak if peak > 0 else 0.0
        if self.pull_fraction <= 0.0:
            return (0.0, 0.0)
        self.pull_angle = math.atan2(ship.y - self.y, ship.x - self.x)
        return (ax, ay)

    def pull_ship(self, ship, maze) -> Tuple[float, float]:
        """Apply this frame's pull to the ship and remember it for drawing.

        Returns:
            The (ax, ay) that was applied.
        """
        ax, ay = self.reach_for(ship, maze)
        if (ax, ay) != (0.0, 0.0):
            apply_pull(ship, ax, ay)
        return (ax, ay)

    def fling(self, ship) -> None:
        """Throw a ship that has touched it straight back out, then let go for a moment."""
        dx, dy = ship.x - self.anchor[0], ship.y - self.anchor[1]
        dist = math.hypot(dx, dy)
        if not math.isfinite(dist) or dist <= 1e-6:
            # Dead centre (where the bounce itself has no direction to work with):
            # throw it back the way it came, or to the right if it was still
            speed = math.hypot(ship.vx, ship.vy)
            moving = math.isfinite(speed) and speed > 1e-6
            dx, dy = (-ship.vx / speed, -ship.vy / speed) if moving else (1.0, 0.0)
        else:
            dx, dy = dx / dist, dy / dist
        clear = self.radius + ship.radius + 1.0
        ship.x, ship.y = self.anchor[0] + dx * clear, self.anchor[1] + dy * clear
        ship.vx, ship.vy = dx * config.ANEMONE_FLING_SPEED, dy * config.ANEMONE_FLING_SPEED
        self._hold_position()
        self.pull_fraction = 0.0
        self.stun(config.ANEMONE_RELEASE_FRAMES)

    def _hold_position(self) -> None:
        """Undo anything a collision did to its position or velocity."""
        self.x, self.y = self.anchor
        self.vx = self.vy = 0.0

    def update(self, dt: float) -> None:
        """Advance the stun timer and animation.

        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        self._hold_position()
        self.stun_timer = max(0.0, self.stun_timer - dt)
        self.sway_phase = (self.sway_phase + 0.05 * dt) % (2 * math.pi)
        self.streak_phase = (self.streak_phase + self.STREAK_SPEED * dt) % 1.0

    def check_wall_collision(self, walls, spatial_grid=None) -> bool:
        # Anemones are rooted; ignore wall collisions
        return False

    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float,
        other_entity: Optional[GameEntity] = None
    ) -> bool:
        """Check collision with another circular entity. The anemone itself never moves."""
        return circle_circle_collision((self.x, self.y), self.radius, other_pos, other_radius)

    def _draw_streaks(self, screen: pygame.Surface) -> None:
        """Draw faint marks drifting inward across its reach, to show how far the pull extends."""
        inner = self.radius * 2.2
        if self.reach_px <= inner:
            return
        color = visual_effects.interpolate_color(
            config.COLOR_BACKGROUND, config.ANEMONE_TIP_COLOR, self.STREAK_STRENGTH)
        for index in range(self.STREAKS):
            angle = 2 * math.pi * index / self.STREAKS + 0.4 * math.sin(index * 1.7)
            # Each streak starts at the edge of reach and drifts in to the body, then starts again
            travel = (self.streak_phase + index * 0.37) % 1.0
            outer = self.reach_px - (self.reach_px - inner) * travel
            # Short at the edge and close in, longest part-way, so they fade in and out
            length = self.radius * 0.9 * math.sin(math.pi * travel)
            if length < 1.0:
                continue
            direction = (math.cos(angle), math.sin(angle))
            start = (self.x + direction[0] * outer, self.y + direction[1] * outer)
            end = (self.x + direction[0] * (outer - length), self.y + direction[1] * (outer - length))
            pygame.draw.line(screen, color, start, end, 1)

    def _draw_body(self, screen: pygame.Surface, scale: float, fade: float, closed: float) -> None:
        """Draw the column, tentacles and mouth.

        Args:
            screen: The pygame Surface to draw on.
            scale: Size multiplier (1.0 alive; shrinks as it dies).
            fade: How far its colours have faded into the background (0.0 none, 1.0 gone).
            closed: How tightly it is clamped shut (0.0 open, 1.0 shut).
        """
        radius = self.radius * scale
        if radius < 1.0:
            return
        center = (self.x, self.y)

        def tone(color):
            dulled = visual_effects.interpolate_color(color, self.DULL_COLOR, 0.6 * closed)
            return visual_effects.interpolate_color(dulled, config.COLOR_BACKGROUND, fade)

        body, tip = tone(config.ANEMONE_COLOR), tone(config.ANEMONE_TIP_COLOR)
        pygame.draw.circle(screen, tone(self.SHADOW_COLOR), center, radius * (self.COLUMN_RADIUS + 0.12))
        pygame.draw.circle(screen, visual_effects.interpolate_color(body, tone(self.SHADOW_COLOR), 0.45),
                           center, radius * self.COLUMN_RADIUS)

        length = radius * self.TENTACLE_LENGTH * (1.0 - 0.6 * closed)
        lean = self.TENTACLE_LEAN * self.pull_fraction * (1.0 - closed)
        for index in range(self.TENTACLES):
            base_angle = 2 * math.pi * index / self.TENTACLES
            sway = 0.22 * math.sin(self.sway_phase * 2 + index * 1.9) * (1.0 - closed)
            # Swing toward the ship by the shortest way round, most at the tip
            to_ship = (self.pull_angle - base_angle + math.pi) % (2 * math.pi) - math.pi
            point = (center[0] + math.cos(base_angle) * radius * self.TENTACLE_ROOT,
                     center[1] + math.sin(base_angle) * radius * self.TENTACLE_ROOT)
            for segment in range(self.TENTACLE_SEGMENTS):
                along = (segment + 1) / self.TENTACLE_SEGMENTS
                # Clamped shut, the tentacles curl back over the mouth
                angle = base_angle + sway * along + to_ship * lean * along + math.pi * 0.85 * closed * along
                step = length / self.TENTACLE_SEGMENTS
                next_point = (point[0] + math.cos(angle) * step, point[1] + math.sin(angle) * step)
                width = max(1, int(round(radius * 0.26 * (1.0 - 0.6 * along))))
                color = visual_effects.interpolate_color(body, tip, along)
                pygame.draw.line(screen, color, point, next_point, width)
                pygame.draw.circle(screen, color, next_point, width / 2)
                point = next_point

        pygame.draw.circle(screen, tone(self.MOUTH_COLOR), center, radius * self.MOUTH_RADIUS)
        glow = self.pull_fraction * (1.0 - closed) * (1.0 - fade)
        if glow > 0.02:
            # Stepped alpha keeps the glow cache small
            alpha = int(60 + 180 * glow) // 10 * 10
            surface = visual_effects.create_soft_glow_surface(radius * 0.9, config.ANEMONE_TIP_COLOR, alpha)
            screen.blit(surface, surface.get_rect(center=(int(center[0]), int(center[1]))))

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the anemone.

        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        if not self.is_stunned:
            self._draw_streaks(screen)
        self._draw_body(screen, 1.0, 0.0, self.closed_fraction)

    def draw_death(self, screen: pygame.Surface) -> None:
        """Draw it wilting: folding shut, shrinking and fading out.

        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.is_dying:
            return
        progress = self.death_progress
        self._draw_body(screen, 1.0 - 0.6 * progress, progress, min(1.0, progress * 2.5))
