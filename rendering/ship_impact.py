"""Deterministic ship hit and breakup effects; visual state never touches physics or random draws."""
import math

import pygame


class ShipImpact:
    DURATION = 14.0

    def __init__(self):
        self.remaining = 0.0

    def hit(self):
        # Sustained contact cannot restart the recoil every frame.
        if self.remaining <= 0:
            self.remaining = self.DURATION

    def update(self, dt):
        self.remaining = max(0.0, self.remaining - dt)

    def offset(self, angle):
        fraction = self.remaining / self.DURATION
        recoil = -4 * fraction * math.sin((1 - fraction) * math.pi * 3)
        heading = math.radians(angle)
        return recoil * math.cos(heading), recoil * math.sin(heading)

    def vertices(self, vertices, angle):
        dx, dy = self.offset(angle)
        return [(x + dx, y + dy) for x, y in vertices]

    def draw(self, screen, centre, radius, vertices):
        if self.remaining <= 0:
            return
        fraction = self.remaining / self.DURATION
        colour = (255, round(100 + 155 * fraction), round(70 + 185 * fraction))
        pygame.draw.lines(screen, colour, True, vertices, max(1, round(2 * fraction)))
        for i in range(6):
            angle = i * math.tau / 6
            reach = radius * (1.1 + 1.6 * (1 - fraction))
            start = (centre[0] + math.cos(angle) * reach, centre[1] + math.sin(angle) * reach)
            end = (start[0] + math.cos(angle) * 6 * fraction, start[1] + math.sin(angle) * 6 * fraction)
            pygame.draw.line(screen, colour, start, end, 1)


def draw_ship_breakup(screen, centre, radius, vertices, colour, progress):
    """Break the actual hull into spinning plates, with a fading flash, sparks and shockwave."""
    if not 0 <= progress < 1:
        return
    spread = 2.4
    reach = math.ceil(radius * 7 * spread + 16)
    layer = pygame.Surface((reach * 2, reach * 2), pygame.SRCALPHA)
    fade = 1 - progress
    local = [(x - centre[0], y - centre[1]) for x, y in vertices]
    for i, (a, b) in enumerate(zip(local, local[1:] + local[:1])):
        direction = math.atan2(a[1] + b[1], a[0] + b[0])
        drift = radius * 4 * progress * spread
        spin = progress * (i + 1) * (1 if i % 2 else -1)
        cs, sn = math.cos(spin), math.sin(spin)
        dx, dy = reach + math.cos(direction) * drift, reach + math.sin(direction) * drift
        points = [(dx + x * cs - y * sn, dy + x * sn + y * cs) for x, y in ((0, 0), a, b)]
        pygame.draw.polygon(layer, (*colour, round(150 * fade)), points)
        pygame.draw.lines(layer, (255, 220, 160, round(255 * fade)), True, points, 1)
    for i in range(16):
        angle = i * math.tau / 16 + 0.17
        distance = radius * (0.5 + progress * (3 + i % 4)) * spread
        x, y = reach + math.cos(angle) * distance, reach + math.sin(angle) * distance
        pygame.draw.line(layer, (255, 170 + i % 3 * 30, 90, round(255 * fade)),
                         (x, y), (x - math.cos(angle) * 8 * fade, y - math.sin(angle) * 8 * fade), 2)
    pygame.draw.circle(layer, (*colour, round(180 * fade)), (reach, reach),
                       max(1, round(radius * (1 + 5 * progress) * spread)), max(1, round(3 * fade)))
    if progress < 0.2:
        pygame.draw.circle(layer, (255, 245, 220, round(255 * (1 - progress / 0.2))),
                           (reach, reach), max(1, round(radius * (1 + progress * 5) * 1.7)))
    screen.blit(layer, (round(centre[0]) - reach, round(centre[1]) - reach))
