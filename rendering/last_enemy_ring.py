"""The ring that marks the last enemy keeping the exit shut, so the player can find it wherever it hides."""
import math
from typing import Tuple

import pygame

RING_COLOR = (255, 222, 140)
HALO_COLOR = (70, 62, 45)   # The ring's colour faded into the dark, drawn opaque (anti-aliasing onto alpha muddies)
RING_GAP = 10               # Between the enemy's edge and the arcs
ARCS = 3
ARC_DEGREES = 70            # Each arc's sweep; the rest of its third is the gap
ARC_STEPS = 16
TURN_DEGREES_PER_SECOND = 45
BREATH = 2.0                # How far the arcs swell and settle


def draw_last_enemy_ring(screen: pygame.Surface, pos: Tuple[float, float], radius: float, seconds: float) -> None:
    """Three thin arcs turning slowly round the enemy and breathing in and out, over a faint halo."""
    x, y = pos
    breath = (math.sin(seconds * math.tau * 0.8) + 1) / 2
    ring = radius + RING_GAP + BREATH * breath
    pygame.draw.circle(screen, HALO_COLOR, (round(x), round(y)), round(ring + 3), 1)
    turn = seconds * TURN_DEGREES_PER_SECOND
    sweep = math.radians(ARC_DEGREES)
    for i in range(ARCS):
        start = math.radians(turn + i * 360 / ARCS)
        for r in (ring, ring + 1):
            points = [(x + r * math.cos(start + sweep * k / ARC_STEPS), y + r * math.sin(start + sweep * k / ARC_STEPS))
                      for k in range(ARC_STEPS + 1)]
            pygame.draw.aalines(screen, RING_COLOR, False, points)
