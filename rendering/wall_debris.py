"""Rock knocked off the maze walls by shots.

A hit makes the struck block flash and throws a few chips out from the point
of impact. A block that is destroyed bursts into rubble instead. None of it
collides with anything; it tumbles, slows and fades.
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame
import config
from rendering.visual_effects import interpolate_color

Point = Tuple[float, float]
Color = Tuple[int, int, int]
BlockRect = Tuple[int, int, int, int]  # Left, top, width, height


@dataclass
class Chip:
    """A fragment of rock tumbling away."""
    x: float
    y: float
    vx: float
    vy: float
    angle: float  # Degrees
    spin: float  # Degrees per frame
    size: float  # Pixels across
    color: Color
    life: float = 1.0  # 1.0 fresh, 0.0 gone


@dataclass
class Flash:
    """A block lit up by the shot that struck it."""
    rect: pygame.Rect
    life: float = 1.0  # 1.0 fresh, 0.0 gone


class WallDebris:
    """The chips and flashes thrown up by shots hitting the walls.

    Attributes:
        chips: Fragments of rock still flying.
        flashes: Blocks still lit by a hit.
    """

    HIT_CHIPS = 7
    RUBBLE_CHIPS = 26
    CHIP_SPEED = (1.0, 4.0)  # Pixels per frame
    CHIP_SIZE = (2.0, 4.5)
    RUBBLE_SIZE = (3.0, 7.0)
    CHIP_FRAMES = 26.0
    RUBBLE_FRAMES = 40.0
    CHIP_FRICTION = 0.93
    CHIP_SPIN = 18.0  # Degrees per frame, either way
    FLASH_FRAMES = 7.0
    FLASH_COLOR = (235, 245, 255)
    FLASH_ALPHA = 120

    def __init__(self):
        """Initialize with nothing flying."""
        self.chips: List[Chip] = []
        self.flashes: List[Flash] = []

    def hit(self, rect: BlockRect, impact: Optional[Point] = None) -> None:
        """A shot struck a block and left it standing.

        Args:
            rect: Screen area of the block.
            impact: Where the shot landed. Defaults to the middle of the block.
        """
        area = pygame.Rect(rect)
        self.flashes = [flash for flash in self.flashes if flash.rect != area]
        self.flashes.append(Flash(area))
        if impact is None:
            impact = area.center
        # Chips spray back out of the rock, away from the block's middle
        away = math.atan2(impact[1] - area.centery, impact[0] - area.centerx)
        for _ in range(self.HIT_CHIPS):
            self._throw(impact, away + random.uniform(-1.2, 1.2), self.CHIP_SIZE, self.CHIP_FRAMES)

    def destroy(self, rect: BlockRect) -> None:
        """A block broke apart: scatter rubble from all over it.

        Args:
            rect: Screen area the block filled.
        """
        area = pygame.Rect(rect)
        self.flashes = [flash for flash in self.flashes if flash.rect != area]
        # One piece from each part of the block, so none of it just vanishes
        columns = max(1, int(round(math.sqrt(self.RUBBLE_CHIPS * area.width / max(1, area.height)))))
        rows = max(1, math.ceil(self.RUBBLE_CHIPS / columns))
        for row in range(rows):
            for column in range(columns):
                start = (
                    area.left + area.width * (column + random.random()) / columns,
                    area.top + area.height * (row + random.random()) / rows,
                )
                outward = math.atan2(start[1] - area.centery, start[0] - area.centerx)
                self._throw(start, outward + random.uniform(-0.6, 0.6), self.RUBBLE_SIZE, self.RUBBLE_FRAMES)

    def _throw(self, start: Point, direction: float, sizes: Tuple[float, float], frames: float) -> None:
        """Send one chip flying from a point, in roughly the given direction (radians)."""
        speed = random.uniform(*self.CHIP_SPEED)
        shade = random.uniform(0.45, 0.95)
        self.chips.append(Chip(
            x=start[0],
            y=start[1],
            vx=math.cos(direction) * speed,
            vy=math.sin(direction) * speed,
            angle=random.uniform(0.0, 360.0),
            spin=random.uniform(-self.CHIP_SPIN, self.CHIP_SPIN),
            size=random.uniform(*sizes),
            color=tuple(int(channel * shade) for channel in config.COLOR_WALLS),
            # Chips with less life to begin with are gone sooner
            life=random.uniform(0.6, 1.0) * frames / self.RUBBLE_FRAMES,
        ))

    def update(self, dt: float) -> None:
        """Move the chips along and drop whatever has faded."""
        for chip in self.chips:
            chip.x += chip.vx * dt
            chip.y += chip.vy * dt
            chip.vx *= self.CHIP_FRICTION
            chip.vy *= self.CHIP_FRICTION
            chip.angle += chip.spin * dt
            chip.life -= dt / self.RUBBLE_FRAMES
        self.chips = [chip for chip in self.chips if chip.life > 0.0]
        for flash in self.flashes:
            flash.life -= dt / self.FLASH_FRAMES
        self.flashes = [flash for flash in self.flashes if flash.life > 0.0]

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the flashes over their blocks, then the chips."""
        for flash in self.flashes:
            layer = pygame.Surface(flash.rect.size, pygame.SRCALPHA)
            layer.fill((*self.FLASH_COLOR, int(self.FLASH_ALPHA * flash.life)))
            screen.blit(layer, flash.rect)
        for chip in self.chips:
            alpha = int(255 * max(0.0, min(1.0, chip.life * 3.0)))
            if alpha <= 0:
                continue
            size = int(chip.size) + 4
            layer = pygame.Surface((size, size), pygame.SRCALPHA)
            middle = size / 2
            # A lopsided triangle, lit on one edge
            corners = [
                (
                    middle + math.cos(math.radians(chip.angle + turn)) * chip.size / 2 * reach,
                    middle + math.sin(math.radians(chip.angle + turn)) * chip.size / 2 * reach,
                )
                for turn, reach in ((0.0, 1.0), (130.0, 0.8), (235.0, 0.65))
            ]
            pygame.draw.polygon(layer, (*chip.color, alpha), corners)
            lit = interpolate_color(chip.color, (255, 255, 255), 0.45)
            pygame.draw.line(layer, (*lit, alpha), corners[0], corners[2], 1)
            screen.blit(layer, layer.get_rect(center=(int(chip.x), int(chip.y))))
