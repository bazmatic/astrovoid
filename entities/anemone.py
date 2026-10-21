"""The Anemone's Body, and the pull it puts on the player's ship.

An anemone is rooted to one spot (`anchored`). It draws the ship in whenever it has a clear line to it (`pullsShip`),
flings the ship out on contact (`flingsShip`), and clamps shut for a moment when shot (`flinchesWhenHit`), which stops
the pull. The Body draws its reach as faint streaks, leans its tentacles toward a ship it is pulling, and folds shut
while it flinches; it reads that state from the creature, counting any its traits have not set yet as nothing.
"""

import math
from typing import Optional, Tuple

import pygame
import config
from rendering import visual_effects


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


class AnemoneBody:
    """The look of an anemone.

    Attributes:
        sway_phase: Phase of the tentacles' idle sway.
        streak_phase: How far the reach streaks have drifted in (0.0 to 1.0).
    """

    DEATH_DURATION = 30.0  # Frames (0.5 seconds at 60 FPS)
    DEATH_FRICTION = 0.0   # Rooted even in death

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
    REOPEN_FRACTION = 1 / 3  # Share of a flinch spent reopening

    def __init__(self, creature):
        self._creature = creature
        self.sway_phase = 0.0
        self.streak_phase = 0.0

    x = property(lambda self: self._creature.x)
    y = property(lambda self: self._creature.y)
    radius = property(lambda self: self._creature.radius)
    pull_fraction = property(lambda self: getattr(self._creature, 'pull_fraction', 0.0))
    pull_angle = property(lambda self: getattr(self._creature, 'pull_angle', 0.0))
    reach_px = property(lambda self: getattr(self._creature, 'reach_px', 0.0))

    @property
    def is_flinching(self) -> bool:
        """Whether it is clamped shut and not pulling."""
        return getattr(self._creature, 'flinch_timer', 0.0) > 0.0

    @property
    def closed_fraction(self) -> float:
        """How tightly it is clamped shut: 1.0 while flinching, easing to 0.0 as the flinch ends."""
        timer = getattr(self._creature, 'flinch_timer', 0.0)
        total = getattr(self._creature, 'flinch_total', 0.0)
        if timer <= 0.0 or total <= 0.0:
            return 0.0
        return min(1.0, timer / (total * self.REOPEN_FRACTION))

    def on_event(self, creature, name: str) -> None:
        """Its look follows its pull and its flinch, so events change nothing."""

    def update(self, creature, dt: float, target=None) -> None:
        """The tentacles sway and the reach streaks drift in."""
        self.sway_phase = (self.sway_phase + 0.05 * dt) % (2 * math.pi)
        self.streak_phase = (self.streak_phase + self.STREAK_SPEED * dt) % 1.0

    def update_death(self, creature, dt: float) -> None:
        """It wilts as death_progress runs; nothing else moves."""

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

    def draw(self, screen: pygame.Surface, creature) -> None:
        """Draw the anemone, with its reach unless it is clamped shut."""
        if not self.is_flinching:
            self._draw_streaks(screen)
        self._draw_body(screen, 1.0, 0.0, self.closed_fraction)

    def draw_death(self, screen: pygame.Surface, creature) -> None:
        """Draw it wilting: folding shut, shrinking and fading out."""
        progress = creature.death_progress
        self._draw_body(screen, 1.0 - 0.6 * progress, progress, min(1.0, progress * 2.5))
