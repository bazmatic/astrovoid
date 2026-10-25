"""Explosions: a blast that hurts everything near it, and the fireball the player sees.

Anything that explodes (a Belemnite now, bombs later) says what its blast is with a `Blast`. `Explosions` holds the
blasts waiting on their fuse and the fireballs on screen: `trigger` lights a blast, `update` returns the blasts that go
off this frame for the game to apply, and `draw` paints the fireballs. Applying a blast can kill something else that
explodes, which triggers its own blast, so explosions chain; the fuse is what makes a chain ripple outwards rather than
go off all at once.

`reaches` and `push` are the blast's reach and shove on a circle, kept here so every target is treated alike.
"""
import math
import random
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

import pygame

from rendering.visual_effects import create_soft_glow_surface


@dataclass(frozen=True)
class Blast:
    """One explosion: where, how far it reaches, and what it does to what it reaches.

    `damage` is the hits it deals each enemy it reaches (the player and the hunter take one); `push` the speed it gives a thing at its centre, fading to
    nothing at its edge; `wall_hits` the hits it deals each wall block it reaches (0 leaves the walls alone). `source`
    is whom its kills count for, as a shot's source does ('player', 'hunter' or 'enemy'); a blast set off by another
    passes it on. `fuse` is the frames between lighting it and its going off.
    """
    pos: Tuple[float, float]
    radius: float
    damage: int = 1
    push: float = 6.0
    wall_hits: int = 1
    source: str = 'enemy'
    fuse: float = 0.0
    color: Tuple[int, int, int] = (255, 170, 60)
    weapon_id: Optional[str] = None


def reaches(blast: Blast, pos: Tuple[float, float], radius: float = 0.0) -> bool:
    """Whether the blast reaches a circle at `pos`."""
    return math.hypot(pos[0] - blast.pos[0], pos[1] - blast.pos[1]) < blast.radius + radius


def push(blast: Blast, pos: Tuple[float, float]) -> Tuple[float, float]:
    """The velocity the blast gives a thing at `pos`: straight away from its centre, fading to nothing at its edge."""
    dx, dy = pos[0] - blast.pos[0], pos[1] - blast.pos[1]
    distance = math.hypot(dx, dy)
    if distance < 1e-6:
        angle = random.uniform(0.0, 2.0 * math.pi)
        dx, dy, distance = math.cos(angle), math.sin(angle), 1.0
    speed = blast.push * max(0.0, 1.0 - distance / blast.radius)
    return dx / distance * speed, dy / distance * speed


class Fireball:
    """What the player sees of a blast: a flash, a shock ring out to its reach, and sparks."""
    DURATION = 36.0  # frames
    SPARKS = 18

    def __init__(self, blast: Blast):
        self.blast = blast
        self.age = 0.0
        self.sparks = [(random.uniform(0.0, 2.0 * math.pi), random.uniform(0.55, 1.15))
                       for _ in range(self.SPARKS)]

    @property
    def active(self) -> bool:
        return self.age < self.DURATION

    @property
    def progress(self) -> float:
        return min(1.0, self.age / self.DURATION)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, screen: pygame.Surface) -> None:
        if not self.active:
            return
        p = self.progress
        x, y = self.blast.pos
        reach = self.blast.radius
        color = self.blast.color
        centre = (round(x), round(y))
        # A soft glow that swells quickly and fades
        fade = (1.0 - p) ** 1.2
        if fade > 0.02:
            glow = create_soft_glow_surface(reach * (0.8 + 0.6 * min(1.0, p * 3.0)), color, 255).copy()
            glow.fill((255, 255, 255, round(255 * fade)), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(glow, glow.get_rect(center=centre))
        # A white-hot core for the first moments
        if p < 0.3:
            core = 1.0 - p / 0.3
            pygame.draw.circle(screen, (255, 250, 220), centre, max(1, round(reach * 0.35 * core)))
        # The shock ring runs out to the blast's reach
        ring = round(reach * (0.2 + 0.8 * math.sqrt(p)))
        width = max(1, round(5 * (1.0 - p)))
        if ring > width:
            ring_color = tuple(round(c + (255 - c) * (1.0 - p) * 0.5) for c in color)
            pygame.draw.circle(screen, ring_color, centre, ring, width)
        # Sparks fly out past the ring and cool
        for angle, speed in self.sparks:
            out = reach * speed * math.sqrt(p)
            tail = reach * speed * 0.12 * (1.0 - p)
            head = (x + math.cos(angle) * out, y + math.sin(angle) * out)
            back = (x + math.cos(angle) * (out - tail), y + math.sin(angle) * (out - tail))
            heat = 1.0 - p
            spark = (255, round(140 + 110 * heat), round(60 * heat))
            pygame.draw.line(screen, spark, back, head, 2 if p < 0.5 else 1)


class Explosions:
    """The blasts lit and waiting on their fuse, and the fireballs on screen."""

    def __init__(self):
        self._lit: List[Blast] = []
        self.fireballs: List[Fireball] = []

    def trigger(self, blast: Optional[Blast]) -> None:
        """Light a blast; it goes off once its fuse has burnt. None (nothing to explode) is ignored."""
        if blast is not None:
            self._lit.append(blast)

    def update(self, dt: float) -> List[Blast]:
        """Burn the fuses and age the fireballs; returns the blasts that go off now, for the game to apply."""
        for fireball in self.fireballs:
            fireball.update(dt)
        self.fireballs = [f for f in self.fireballs if f.active]
        going_off, waiting = [], []
        for blast in self._lit:
            fuse = blast.fuse - dt
            if fuse <= 0.0:
                going_off.append(blast)
                self.fireballs.append(Fireball(blast))
            else:
                waiting.append(replace(blast, fuse=fuse))
        self._lit = waiting
        return going_off

    @property
    def pending(self) -> bool:
        """Whether any blast is lit and waiting, or any fireball still burns."""
        return bool(self._lit or self.fireballs)

    def clear(self) -> None:
        self._lit.clear()
        self.fireballs.clear()

    def draw(self, screen: pygame.Surface) -> None:
        for fireball in self.fireballs:
            fireball.draw(screen)
