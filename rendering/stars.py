"""Procedural cut-metal stars shared by completion rewards and level tiles."""
import math
from functools import lru_cache

import pygame


@lru_cache(maxsize=128)
def _star_surface(size: int, filled: bool, flash: int) -> pygame.Surface:
    # Supersampling keeps the outline crisp at both tile and reward sizes.
    resolution = 3
    side = max(3, size * resolution)
    surface = pygame.Surface((side + 6, side + 6), pygame.SRCALPHA)
    center = (surface.get_width() / 2, surface.get_height() / 2)
    radius = side * 0.48
    points = [
        (center[0] + math.cos(-math.pi / 2 + i * math.pi / 5) * radius * (1 if i % 2 == 0 else 0.44),
         center[1] + math.sin(-math.pi / 2 + i * math.pi / 5) * radius * (1 if i % 2 == 0 else 0.44))
        for i in range(10)
    ]
    if filled:
        for i in range(10):
            # Light comes from the top left; alternate ridges give the star depth.
            shade = [(255, 238, 158), (255, 203, 62), (218, 137, 26), (158, 83, 18),
                     (191, 109, 20), (240, 170, 33), (255, 217, 91), (255, 241, 172),
                     (235, 170, 46), (255, 227, 124)][i]
            color = tuple(round(c + (255 - c) * flash / 10) for c in shade)
            pygame.draw.polygon(surface, color, [center, points[i], points[(i + 1) % 10]])
    pygame.draw.lines(surface, (255, 241, 183) if filled else (78, 72, 120), True,
                      points, resolution)
    return pygame.transform.smoothscale(surface, (size + 2, size + 2))


def draw_star(screen, x, y, size, filled=True, flash=0.0, shimmer=None):
    """Draw a faceted star or dim empty outline without changing screen alpha."""
    sprite = _star_surface(max(2, round(size)), filled, round(min(1, max(0, flash)) * 10))
    if shimmer is not None and filled:
        sprite = sprite.copy()
        band = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        width, height = sprite.get_size()
        center = shimmer * width
        for offset in range(-max(2, width // 6), max(2, width // 6)):
            alpha = int(110 * max(0, 1 - abs(offset) / max(2, width / 6)))
            pygame.draw.line(band, (255, 255, 240, alpha),
                             (center + offset, 0), (center + offset - width * 0.3, height), 1)
        # Cut the light band to the star silhouette.
        mask = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 0))
        mask.blit(sprite, (0, 0))
        band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sprite.blit(band, (0, 0))
    screen.blit(sprite, sprite.get_rect(center=(round(x), round(y))))


@lru_cache(maxsize=96)
def _glow_surface(size, color):
    from rendering.visual_effects import create_radial_gradient_surface
    return create_radial_gradient_surface((size, size), color, 110)


def draw_glow(screen, x, y, size, color, strength=1.0):
    """A soft halo with breathing opacity; keep expensive gradients cached."""
    halo = _glow_surface(max(4, round(size)), color)
    halo.set_alpha(round(255 * max(0, min(1, strength))))
    screen.blit(halo, halo.get_rect(center=(round(x), round(y))))


class StarBurst:
    """A short expanding ring and ballistic gold sparks, positioned relative to a row."""

    LIFETIME = 0.9

    def __init__(self, x, y, size=60, count=12, spread=0, seed=0):
        import random
        rng = random.Random(seed)
        self.x, self.y, self.size = x, y, size
        self.age = 0.0
        self.sparks = []
        for _ in range(min(80, max(0, count))):
            angle = rng.uniform(0, math.tau)
            speed = rng.uniform(1.2, 3.4) * size
            self.sparks.append((rng.uniform(-spread / 2, spread / 2),
                                math.cos(angle) * speed, math.sin(angle) * speed,
                                rng.uniform(0.018, 0.04) * size))

    @property
    def alive(self):
        return self.age < self.LIFETIME

    def update(self, seconds):
        self.age += seconds
        if not self.alive:
            self.sparks.clear()

    def draw(self, screen, origin=(0, 0)):
        if not self.alive:
            return
        t = self.age
        # Draw fading light on a temporary surface, then alpha blend it over the
        # opaque menu instead of drawing alpha values directly onto the screen.
        extent = math.ceil(self.size * 9)
        layer = pygame.Surface((extent, extent), pygame.SRCALPHA)
        cx = cy = extent / 2
        if t < 0.55:
            radius = round(self.size * (0.35 + 1.8 * t))
            pygame.draw.circle(layer, (255, 223, 127, round(180 * (1 - t / 0.55))),
                               (round(cx), round(cy)), radius, max(1, round(self.size / 35)))
        alpha = round(255 * (1 - t / self.LIFETIME) ** 1.3)
        for offset, vx, vy, radius in self.sparks:
            x = cx + offset + vx * t
            y = cy + vy * t + self.size * 1.8 * t * t
            tail = (x - vx * 0.035, y - (vy + self.size * 3.6 * t) * 0.035)
            pygame.draw.line(layer, (255, 185, 54, alpha), tail, (x, y), max(1, round(radius)))
            pygame.draw.circle(layer, (255, 245, 188, alpha), (round(x), round(y)), max(1, round(radius)))
        screen.blit(layer, layer.get_rect(center=(round(origin[0] + self.x), round(origin[1] + self.y))))
