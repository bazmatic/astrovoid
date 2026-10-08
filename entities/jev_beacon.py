"""Jev beacon entity implementation.

This module implements the JevBeacon class: the pickup that summons the
allied Jev hunter when the player collects it.
"""

import math
from typing import List, Tuple
import pygame
from entities.hunter_ship import HunterShip
from entities.powerup_crystal import PowerupCrystal
from rendering import visual_effects


class JevBeacon(PowerupCrystal):
    """A collectible that calls in the Jev hunter.

    It moves and is collected like a powerup crystal, but is drawn as the
    hunter's arrowhead inside a turning amber ring, so it cannot be mistaken
    for the green gem that upgrades the guns.
    """

    # Drawing constants (lengths are multiples of the radius)
    RING_COLOR = HunterShip.ENGINE_LIT_COLOR
    RING_RADIUS = 2.3
    RING_ARCS = 3  # Broken into arcs so the turning shows
    RING_ARC_SWEEP = 80.0  # Degrees covered by each arc
    RING_ARC_STEPS = 8  # Straight pieces making up each arc
    EMBLEM_SCALE = 1.1  # Size of the arrowhead

    def emblem_points(self, center: Tuple[float, float], size: float) -> List[Tuple[float, float]]:
        """The hunter's arrowhead, nose up, with its centre at center."""
        ship = HunterShip
        outline = [
            (ship.NOSE_X, 0.0), (ship.WING_X, ship.WING_HALF_SPAN),
            (ship.NOTCH_X, 0.0), (ship.WING_X, -ship.WING_HALF_SPAN),
        ]
        # Shifted along its length so the shape, not the ship's own centre, sits in the ring
        middle = (ship.NOSE_X + ship.WING_X) / 2
        return [(center[0] + y * size, center[1] - (x - middle) * size) for x, y in outline]

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the beacon: the hunter's arrowhead inside a turning ring.

        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
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
        pygame.draw.polygon(screen, HunterShip.FILL, emblem)
        pygame.draw.aalines(screen, HunterShip.COLOR, True, emblem)
        pygame.draw.circle(screen, HunterShip.NOSE_COLOR, (int(emblem[0][0]), int(emblem[0][1])), 1)
