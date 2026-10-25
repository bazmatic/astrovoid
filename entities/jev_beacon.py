"""Jev beacon entity implementation.

This module implements the JevBeacon class: the pickup that summons the
allied Jev hunter when the player collects it.
"""

import math
from typing import List, Tuple
import pygame
from entities.hunter_ship_body import DEFAULT_COLOURS, HULL_POINTS
from entities.powerup_crystal import Pickup
from rendering import visual_effects


class JevBeacon(Pickup):
    """A collectible that calls in the Jev hunter.

    It moves and is collected like a powerup crystal, but is drawn as the
    hunter's arrowhead inside a turning amber ring, so it cannot be mistaken
    for the green gem that upgrades the guns.
    """

    # Drawing constants (lengths are multiples of the radius)
    RING_COLOR = DEFAULT_COLOURS['engineLitColor']
    RING_RADIUS = 2.3
    RING_ARCS = 3  # Broken into arcs so the turning shows
    RING_ARC_SWEEP = 80.0  # Degrees covered by each arc
    RING_ARC_STEPS = 8  # Straight pieces making up each arc
    EMBLEM_SCALE = 1.1  # Size of the arrowhead
    FORMATION_FRAMES = 72.0
    ARRIVAL_FRAMES = 132.0
    LIFETIME_FRAMES = None  # Earned ally summons remain available until collected.

    @property
    def formed(self):
        return self.age >= self.FORMATION_FRAMES

    @property
    def spawn_scale(self):
        elapsed = self.age - self.FORMATION_FRAMES
        if elapsed <= 0:
            return 0.0
        if elapsed >= self.SPAWN_FRAMES:
            return 1.0
        swing = math.pi / 2 * self.SPAWN_OVERSHOOT
        return math.sin(elapsed / self.SPAWN_FRAMES * swing) / math.sin(swing)

    def update(self, dt, player_pos=None):
        # Light converges on a fixed point; attraction begins once the beacon exists.
        super().update(dt, player_pos if self.formed else None)

    def check_circle_collision(self, other_pos, other_radius):
        return self.formed and super().check_circle_collision(other_pos, other_radius)

    def _draw_arrival(self, screen):
        if self.age >= self.ARRIVAL_FRAMES:
            self._arrival_layer = None
            return
        from rendering.beacon_arrival import draw_arrival
        layer = getattr(self, '_arrival_layer', None)
        if layer is None or layer.get_size() != screen.get_size():
            self._arrival_layer = layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        draw_arrival(screen, layer, self.get_pos(), self.age, self.FORMATION_FRAMES,
                     self.ARRIVAL_FRAMES, self.emblem_points)

    def emblem_points(self, center: Tuple[float, float], size: float) -> List[Tuple[float, float]]:
        """The hunter's arrowhead, nose up, with its centre at center."""
        outline = HULL_POINTS
        # Centre the complete arrowhead in the beacon's ring.
        middle = (HULL_POINTS[0][0] + HULL_POINTS[1][0]) / 2
        return [(center[0] + y * size, center[1] - (x - middle) * size) for x, y in outline]

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the beacon: the hunter's arrowhead inside a turning ring.

        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        self._draw_arrival(screen)
        scale = self.spawn_scale
        if scale <= 0.0:
            return

        size = self.radius * scale * (1.0 + 0.06 * math.sin(self.pulse_phase))
        center = (self.x, self.y + math.sin(self.pulse_phase * 0.7) * self.BOB_HEIGHT)

        # Stepped alpha keeps the glow cache small
        glow_alpha = int(85 + 35 * math.sin(self.pulse_phase * 2.0)) // 10 * 10
        glow = visual_effects.create_soft_glow_surface(self.radius * 4.0, self.RING_COLOR, glow_alpha)
        screen.blit(glow, glow.get_rect(center=(int(center[0]), int(center[1]))))

        # Each arc is a run of short lines: pygame's own arcs come out ragged at this size
        ring_radius = self.RING_RADIUS * size
        for arc in range(self.RING_ARCS):
            start = self.rotation_angle + arc * 360.0 / self.RING_ARCS
            points = []
            for step in range(self.RING_ARC_STEPS + 1):
                angle = math.radians(start + self.RING_ARC_SWEEP * step / self.RING_ARC_STEPS)
                points.append((center[0] + math.cos(angle) * ring_radius, center[1] + math.sin(angle) * ring_radius))
            pygame.draw.lines(screen, self.RING_COLOR, False, points, 2)
        
        emblem = self.emblem_points(center, size * self.EMBLEM_SCALE)
        pygame.draw.polygon(screen, DEFAULT_COLOURS['fill'], emblem)
        pygame.draw.aalines(screen, DEFAULT_COLOURS['color'], True, emblem)
        pygame.draw.circle(screen, DEFAULT_COLOURS['noseColor'], (int(emblem[0][0]), int(emblem[0][1])), 1)
