"""Splash scene rendering.

The player's ship darts up the screen with one of the game's squids on its
tail. The squid gives up the chase to hover over the title, watching the ship
loop round it and away.
"""

import math
import pygame
from typing import List, Tuple
import config
from rendering.fonts import get_font
from rendering.menu_components import AnimatedBackground, build_menu_backdrop, menu_scale, render_title
from utils.resource_path import resource_path
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.command_recorder import CommandRecorder
from entities.ship import Ship


class SplashScene:
    """A big squid chasing the little ship up the screen, then settling above the title."""

    # Lengths are on the reference layout, heights are fractions of the screen
    SQUID_RADIUS = 150
    SQUID_HOVER_Y = 0.31
    SQUID_SWAY = 5  # Degrees
    SQUID_BOB = 10
    SQUID_HOVER_SPEED = 0.03  # Radians per frame
    STROKE_INTERVAL = 26.0  # Frames between jet strokes
    STROKE_REACH = 0.045  # Kick per pixel still to travel
    STROKE_MAX_KICK = 17.0  # Pixels per frame
    FRICTION = 0.95  # Velocity kept per frame
    ARRIVAL_DISTANCE = 40  # Within this the squid stops jetting and hovers
    SQUID_TRACK_ANGLE = 40  # Degrees the squid will lean to keep its eyes on the ship
    SQUID_TURN_RATE = 0.07  # Share of the remaining turn made per frame
    # The ship's route, as fractions of the screen: up the left of the squid,
    # over its head and off to the right. It stays its in-game size
    SHIP_ROUTE = ((0.38, 1.06), (0.36, 0.62), (0.34, 0.3), (0.5, 0.08), (0.68, 0.24), (0.8, 0.5), (1.3, 0.62))
    SHIP_ROUTE_SAMPLES = 240
    SHIP_FLIGHT_TIME = 3.3  # Seconds to fly the route
    TITLE_CENTER_Y = 0.82
    TITLE_WIDTH = 860
    TITLE_FADE = (1.9, 2.7)  # Seconds from the start of the scene

    def __init__(self, screen: pygame.Surface):
        """Initialize the splash scene.

        Args:
            screen: The pygame Surface to draw on.
        """
        self.screen = screen
        self.scale = menu_scale()
        self.backdrop = build_menu_backdrop(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.title = self._load_title()
        self.squid = ReplayEnemyShip((0.0, 0.0), CommandRecorder())
        self.ship = Ship((0.0, 0.0))
        self.ship_route = self._build_ship_route()
        self.reset()

    def _scaled(self, value: float) -> int:
        """Scale a reference-layout length to the current screen size."""
        return max(1, int(round(value * self.scale)))

    def _load_title(self) -> pygame.Surface:
        """Load the title graphic, or a text heading if the file is missing."""
        try:
            image = pygame.image.load(resource_path("assets/title.png")).convert_alpha()
            image = image.subsurface(image.get_bounding_rect())
            width = min(self._scaled(self.TITLE_WIDTH), config.SCREEN_WIDTH - self._scaled(96))
            height = int(image.get_height() * width / image.get_width())
            return pygame.transform.smoothscale(image, (width, height))
        except (pygame.error, FileNotFoundError):
            return render_title(get_font(self._scaled(config.FONT_SIZE_TITLE * 2)), "SQUIDDLER")

    def _build_ship_route(self) -> List[Tuple[float, float]]:
        """Evenly spaced points along a smooth curve through the route's waypoints."""
        points = [(x * config.SCREEN_WIDTH, y * config.SCREEN_HEIGHT) for x, y in self.SHIP_ROUTE]
        padded = [points[0]] + points + [points[-1]]
        curve = []
        steps = 24
        for i in range(len(points) - 1):
            p0, p1, p2, p3 = padded[i:i + 4]
            for j in range(steps):
                t = j / steps
                # Catmull-Rom spline
                curve.append(tuple(
                    0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3)
                    for a, b, c, d in zip(p0, p1, p2, p3)
                ))
        curve.append(points[-1])

        # Walk the curve at a steady pace
        lengths = [0.0]
        for a, b in zip(curve, curve[1:]):
            lengths.append(lengths[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        route = []
        index = 0
        for n in range(self.SHIP_ROUTE_SAMPLES + 1):
            target = lengths[-1] * n / self.SHIP_ROUTE_SAMPLES
            while index < len(curve) - 2 and lengths[index + 1] < target:
                index += 1
            span = lengths[index + 1] - lengths[index]
            t = (target - lengths[index]) / span if span else 0.0
            a, b = curve[index], curve[index + 1]
            route.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        return route

    def _ship_position(self, seconds: float) -> Tuple[float, float]:
        """Where the ship is on its route at a time into the scene."""
        along = max(0.0, min(1.0, seconds / self.SHIP_FLIGHT_TIME)) * self.SHIP_ROUTE_SAMPLES
        index = min(int(along), self.SHIP_ROUTE_SAMPLES - 1)
        a, b = self.ship_route[index], self.ship_route[index + 1]
        t = along - index
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    @property
    def ship_flying(self) -> bool:
        """Whether the ship is still on its way across the screen."""
        return self.time_elapsed < self.SHIP_FLIGHT_TIME

    def _update_ship(self, dt: float) -> None:
        """Move the ship along its route, nose first, leaving its wake."""
        if not self.ship_flying:
            return
        ship = self.ship
        previous = (ship.x, ship.y)
        ship.x, ship.y = self._ship_position(self.time_elapsed)
        ship.vx = (ship.x - previous[0]) / dt if dt else 0.0
        ship.vy = (ship.y - previous[1]) / dt if dt else 0.0
        if ship.vx or ship.vy:
            ship.angle = math.degrees(math.atan2(ship.vy, ship.vx))
            ship.trail.append(previous)
            del ship.trail[:-ship.TRAIL_LENGTH]
        ship.thrusting = True

    def reset(self) -> None:
        """Send the squid back below the screen to make its entrance again."""
        self.time_elapsed = 0.0
        self.hover_phase = 0.0
        self.stroke_timer = 0.0
        self.squid.radius = self._scaled(self.SQUID_RADIUS)
        self.squid.angle = -90.0
        self.squid.x = config.SCREEN_WIDTH / 2
        # Start with the tip of the mantle just out of sight
        self.swim_y = config.SCREEN_HEIGHT + self.squid.radius * 1.2
        self.squid.y = self.swim_y
        self.swim_speed = 0.0
        self.squid.jet = 0.0
        self.squid.tentacles = []
        self.ship.x, self.ship.y = self.ship_route[0]
        self.ship.vx = self.ship.vy = 0.0
        self.ship.angle = -90.0
        self.ship.trail = []

    @property
    def hover_y(self) -> float:
        """Height the squid settles at."""
        return config.SCREEN_HEIGHT * self.SQUID_HOVER_Y

    @property
    def title_alpha(self) -> float:
        """Opacity of the title (0.0 to 1.0), which appears once the squid has arrived."""
        start, end = self.TITLE_FADE
        return max(0.0, min(1.0, (self.time_elapsed - start) / (end - start)))

    def title_rect(self) -> pygame.Rect:
        """Where the title sits."""
        return self.title.get_rect(center=(config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * self.TITLE_CENTER_Y)))

    def update(self, dt: float) -> None:
        """Update the scene.

        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        self.time_elapsed += dt / 60.0
        self.background.update(dt)
        self._update_ship(dt)

        # Swim up in strokes: each kick is sized to the distance left, so the
        # squid surges in and eases to a stop
        remaining = self.swim_y - self.hover_y
        self.stroke_timer -= dt
        if self.stroke_timer <= 0.0 and remaining > self._scaled(self.ARRIVAL_DISTANCE):
            self.stroke_timer = self.STROKE_INTERVAL
            max_kick = self.STROKE_MAX_KICK * self.scale
            self.swim_speed = min(max_kick, remaining * self.STROKE_REACH)
            self.squid.jet = self.swim_speed / max_kick
        self.swim_y -= self.swim_speed * dt
        self.swim_speed *= self.FRICTION ** dt

        # Hovering takes over as the squid arrives
        self.hover_phase += self.SQUID_HOVER_SPEED * dt
        settled = 1.0 - min(1.0, max(0.0, remaining) / (config.SCREEN_HEIGHT * 0.25))
        self.squid.y = self.swim_y + self._scaled(self.SQUID_BOB) * math.sin(self.hover_phase) * settled
        lean = self.SQUID_SWAY * math.sin(self.hover_phase * 0.6) * settled
        if self.ship_flying:
            # Keep watching the ship as far as the squid can lean
            bearing = math.degrees(math.atan2(self.ship.y - self.squid.y, self.ship.x - self.squid.x))
            off_upright = (bearing + 90.0 + 180.0) % 360.0 - 180.0
            lean = max(-self.SQUID_TRACK_ANGLE, min(self.SQUID_TRACK_ANGLE, off_upright))
        turn = 1.0 - (1.0 - self.SQUID_TURN_RATE) ** dt
        self.squid.angle += (-90.0 + lean - self.squid.angle) * turn
        self.squid.animate(dt)

    def draw(self) -> None:
        """Draw the scene."""
        self.screen.blit(self.backdrop, (0, 0))
        self.background.draw(self.screen)
        self.squid.draw(self.screen)
        if self.ship_flying:
            self.ship.draw(self.screen)
        alpha = self.title_alpha
        if alpha > 0.0:
            self.title.set_alpha(int(255 * alpha))
            self.screen.blit(self.title, self.title_rect())
