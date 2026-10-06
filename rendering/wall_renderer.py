"""Rough, reef-like drawing for maze walls.

Walls collide as straight line segments. This module draws each one as an
uneven ridge of rock instead of a ruled line: it wanders slightly, varies in
thickness and color, has a lit and a shadowed edge, and shows cracks once it
has been hit. Some walls carry barnacles or a tuft of swaying weed.

The drawing never strays more than MAX_REACH from the true segment and always
covers it, so what the player sees is still what they collide with. Each
wall's shape is derived from its end points, so it looks the same every frame.

Walls are painted once onto a cached surface. When one is damaged or destroyed
only the patch around it is repainted. Weed is the only part drawn fresh each
frame.
"""

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

import pygame
import config
from rendering.visual_effects import interpolate_color

if TYPE_CHECKING:
    from maze.wall_segment import WallSegment

Point = Tuple[float, float]
Color = Tuple[int, int, int]
SegmentKey = Tuple[Tuple[int, int], Tuple[int, int]]


@dataclass
class Weed:
    """A tuft of weed growing from a wall."""
    base: Point
    direction: Point  # Unit vector pointing away from the wall
    blade_lengths: Tuple[float, ...]
    phase: float
    color: Color


class WallRenderer:
    """Paints a maze's walls as rough rock, caching the result between frames.

    Attributes:
        weeds: Tufts of weed on the current walls, drawn fresh each frame.
        repaint_count: How many times the cached walls have been repainted.
    """

    # Furthest any wall pixel may be from the segment it belongs to
    MAX_REACH = config.WALL_THICKNESS * 1.4
    SAMPLE_SPACING = 7.0  # Pixels between points along a ridge
    THICKNESS_RANGE = (0.75, 1.35)  # Multiples of half the wall thickness
    WOBBLE = 0.3  # Sideways wander, as a multiple of the wall thickness
    COVER_MARGIN = 1.2  # Pixels of rock always kept either side of the true line
    # Rock tints, as multiples of the configured wall color
    TINTS = ((0.62, 0.80, 0.87), (0.78, 0.70, 0.83), (0.57, 0.87, 0.77))
    CRACK_COLOR = (25, 30, 40)
    DAMAGED_SHADE = 0.78  # Brightness of a wall that has been hit
    BARNACLE_CHANCE = 0.22
    BARNACLE_COLOR = (205, 205, 185)
    WEED_CHANCE = 0.16
    WEED_COLORS = ((70, 170, 120), (95, 190, 110), (60, 150, 140))
    WEED_SWAY = 2.5  # Pixels the tips move
    WEED_SWAY_SPEED = 1.6  # Radians per second
    # Never produced by the palette, so it can mark empty space in the cache
    TRANSPARENT = (255, 0, 255)

    def __init__(self):
        """Initialize an empty renderer."""
        self.weeds: List[Weed] = []
        self.repaint_count = 0
        self._segments: Dict[SegmentKey, int] = {}  # Hit points shown for each painted edge
        self._weed_by_segment: Dict[SegmentKey, Weed] = {}
        self._surface: Optional[pygame.Surface] = None
        self._origin = (0, 0)
        self._signature: Optional[Tuple[int, int, int]] = None

    def draw(
        self,
        screen: pygame.Surface,
        walls: Sequence['WallSegment'],
        time_seconds: Optional[float] = None,
        animate: bool = True
    ) -> None:
        """Draw the walls.

        Args:
            screen: The pygame Surface to draw on.
            walls: The maze's wall segments. Inactive ones are skipped.
            time_seconds: Clock for the swaying weed. Defaults to the pygame clock.
            animate: Draw the weed. Without it only the rock is drawn.
        """
        # Walls only ever lose hit points or vanish, so this changes whenever
        # the picture should
        count = hit_points = identity = 0
        for wall in walls:
            if wall.active:
                count += 1
                hit_points += wall.hit_points
                identity ^= id(wall)
        signature = (count, hit_points, identity)
        if signature != self._signature:
            self._signature = signature
            self._repaint(walls)

        if self._surface is not None:
            screen.blit(self._surface, self._origin)

        if animate and self.weeds:
            if time_seconds is None:
                time_seconds = pygame.time.get_ticks() / 1000.0
            self._draw_weeds(screen, time_seconds)

    @staticmethod
    def _key(wall: 'WallSegment') -> SegmentKey:
        """Identify a segment by its end points, whichever way round it was built.

        Neighbouring wall cells each own a copy of their shared edge, running
        in opposite directions; both copies get the same key and so the same look.
        """
        start = (int(round(wall.start[0])), int(round(wall.start[1])))
        end = (int(round(wall.end[0])), int(round(wall.end[1])))
        return (start, end) if start <= end else (end, start)

    @staticmethod
    def _rng(*values: int) -> random.Random:
        """A random stream fixed by the given integers."""
        seed = 0
        for value in values:
            seed = (seed * 1000003 + value) & 0xFFFFFFFFFFFF
        return random.Random(seed)

    def _repaint(self, walls: Sequence['WallSegment']) -> None:
        """Bring the cached picture up to date with the walls."""
        self.repaint_count += 1
        # One entry per distinct edge, showing the most damaged copy
        segments: Dict[SegmentKey, int] = {}
        for wall in walls:
            if wall.active:
                key = self._key(wall)
                segments[key] = min(segments.get(key, wall.hit_points), wall.hit_points)
        
        previous, self._segments = self._segments, segments
        changed = [key for key in previous.keys() | segments.keys() if previous.get(key) != segments.get(key)]
        patches = [self._patch(key) for key in changed]
        if self._surface is None or not all(self._surface.get_rect().contains(patch) for patch in patches):
            self._paint_everything()
        else:
            # Walls only crack or vanish mid-level, so repainting the patch
            # around each change is far cheaper than starting again
            for patch in patches:
                self._paint_patch(patch)
        for key in changed:
            if key not in segments:
                self._weed_by_segment.pop(key, None)
        self.weeds = list(self._weed_by_segment.values())
    
    def _patch(self, key: SegmentKey) -> pygame.Rect:
        """Area of the cached surface a segment can paint on."""
        margin = int(math.ceil(self.MAX_REACH)) + 2
        (ax, ay), (bx, by) = key
        patch = pygame.Rect(min(ax, bx), min(ay, by), abs(bx - ax) + 1, abs(by - ay) + 1)
        return patch.inflate(2 * margin, 2 * margin).move(-self._origin[0], -self._origin[1])
    
    def _paint_everything(self) -> None:
        """Paint every wall onto a fresh cached surface."""
        self._weed_by_segment = {}
        if not self._segments:
            self._surface = None
            return
        margin = int(math.ceil(self.MAX_REACH)) + 2
        xs = [point[0] for key in self._segments for point in key]
        ys = [point[1] for key in self._segments for point in key]
        self._origin = (min(xs) - margin, min(ys) - margin)
        size = (max(xs) - min(xs) + 2 * margin, max(ys) - min(ys) + 2 * margin)
        self._surface = pygame.Surface(size)
        self._surface.fill(self.TRANSPARENT)
        # No RLE acceleration: it would be re-encoded on every patch repaint
        self._surface.set_colorkey(self.TRANSPARENT)
        self._paint_segments(self._segments.keys())
    
    def _paint_patch(self, patch: pygame.Rect) -> None:
        """Clear one patch of the cached surface and repaint the walls crossing it."""
        self._surface.set_clip(patch)
        self._surface.fill(self.TRANSPARENT)
        self._paint_segments([key for key in self._segments if self._patch(key).colliderect(patch)])
        self._surface.set_clip(None)
    
    def _paint_segments(self, keys) -> None:
        """Paint the given segments and the joints at their ends."""
        keys = list(keys)
        for key in keys:
            self._paint_ridge(self._surface, key, self._segments[key])
        # Knobbly joints go on top so corners look the same from every wall
        for corner in {point for key in keys for point in key}:
            self._paint_joint(self._surface, corner)
    
    def _tint(self, rng: random.Random, shade: float = 1.0) -> Color:
        """Pick a rock color: a blend of two tints with a little brightness noise."""
        first, second = rng.sample(self.TINTS, 2)
        blend = rng.random()
        brightness = rng.uniform(0.9, 1.1) * shade
        return tuple(
            max(0, min(254, int(channel * (a + (b - a) * blend) * brightness)))
            for channel, a, b in zip(config.COLOR_WALLS, first, second)
        )

    def _paint_ridge(self, surface: pygame.Surface, key: SegmentKey, hit_points: int) -> None:
        """Paint one wall as an uneven ridge, cracked if it has been hit."""
        (ax, ay), (bx, by) = key
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            return
        rng = self._rng(ax, ay, bx, by)
        along_x, along_y = (bx - ax) / length, (by - ay) / length
        normal_x, normal_y = -along_y, along_x
        origin_x, origin_y = self._origin
        damaged = hit_points < config.WALL_HIT_POINTS
        shade = self.DAMAGED_SHADE if damaged else 1.0
        half = config.WALL_THICKNESS / 2

        def place(distance: float, sideways: float) -> Point:
            return (
                ax + along_x * distance + normal_x * sideways - origin_x,
                ay + along_y * distance + normal_y * sideways - origin_y,
            )

        # Centre line wanders and thickness varies, but never enough to leave
        # the true segment uncovered
        spans = max(2, int(round(length / self.SAMPLE_SPACING)))
        centres, widths = [], []
        for i in range(spans + 1):
            t = i / spans
            width = half * rng.uniform(*self.THICKNESS_RANGE)
            wander = rng.uniform(-1.0, 1.0) * self.WOBBLE * config.WALL_THICKNESS * math.sin(math.pi * t) ** 0.5
            limit = max(0.0, width - self.COVER_MARGIN)
            centres.append(max(-limit, min(limit, wander)))
            widths.append(width)

        left = [place(length * i / spans, centres[i] + widths[i]) for i in range(spans + 1)]
        right = [place(length * i / spans, centres[i] - widths[i]) for i in range(spans + 1)]

        colors = [self._tint(rng, shade) for _ in range(spans)]
        for i in range(spans):
            pygame.draw.polygon(surface, colors[i], [left[i], left[i + 1], right[i + 1], right[i]])

        # Light falls from the top left
        lit, shadowed = (right, left) if normal_x + normal_y > 0 else (left, right)
        average = tuple(sum(color[c] for color in colors) // spans for c in range(3))
        pygame.draw.lines(surface, interpolate_color(average, (254, 254, 254), 0.4), False, lit, 1)
        pygame.draw.lines(surface, interpolate_color(average, (0, 0, 0), 0.5), False, shadowed, 1)

        # Pores and flecks
        for _ in range(int(length / 6)):
            i = rng.randrange(spans)
            fleck = place(length * (i + rng.random()) / spans, centres[i] + rng.uniform(-0.5, 0.5) * widths[i])
            target = (0, 0, 0) if rng.random() < 0.6 else (254, 254, 254)
            surface.set_at((int(fleck[0]), int(fleck[1])), interpolate_color(colors[i], target, 0.35))

        if rng.random() < self.BARNACLE_CHANCE:
            i = rng.randrange(spans)
            barnacle = place(length * (i + 0.5) / spans, centres[i])
            pygame.draw.circle(surface, self.BARNACLE_COLOR, (int(barnacle[0]), int(barnacle[1])), 2)
            surface.set_at((int(barnacle[0]), int(barnacle[1])), self.CRACK_COLOR)

        if rng.random() < self.WEED_CHANCE:
            i = rng.randrange(1, spans)
            side = rng.choice((-1.0, 1.0))
            base = place(length * i / spans, centres[i] + side * widths[i])
            self._weed_by_segment[key] = Weed(
                base=(base[0] + origin_x, base[1] + origin_y),
                direction=(normal_x * side, normal_y * side),
                blade_lengths=tuple(rng.uniform(5.0, 9.0) for _ in range(rng.randint(2, 3))),
                phase=rng.uniform(0, 2 * math.pi),
                color=rng.choice(self.WEED_COLORS),
            )

        if damaged:
            # A separate stream, so cracks appear without reshaping the rock
            crack_rng = self._rng(ax, ay, bx, by, 7919)
            for _ in range(max(2, int(length / 22))):
                i = crack_rng.randrange(spans)
                distance = length * (i + crack_rng.random()) / spans
                jog = crack_rng.uniform(-3.0, 3.0)
                crack = [
                    place(distance, centres[i] + widths[i]),
                    place(distance + jog, centres[i] + crack_rng.uniform(-0.3, 0.3) * widths[i]),
                    place(distance + jog * 0.3, centres[i] - widths[i]),
                ]
                pygame.draw.lines(surface, self.CRACK_COLOR, False, crack, 1)

    def _paint_joint(self, surface: pygame.Surface, corner: Tuple[int, int]) -> None:
        """Paint a knob of rock where walls meet."""
        rng = self._rng(corner[0], corner[1], 104729)
        half = config.WALL_THICKNESS / 2
        radius = half * rng.uniform(0.95, 1.3)
        x, y = corner[0] - self._origin[0], corner[1] - self._origin[1]
        color = self._tint(rng)
        pygame.draw.circle(surface, interpolate_color(color, (0, 0, 0), 0.45), (x, y), int(round(radius)))
        pygame.draw.circle(surface, color, (x, y), max(1, int(round(radius)) - 1))
        surface.set_at((x - 1, y - 1), interpolate_color(color, (254, 254, 254), 0.45))

    def _draw_weeds(self, screen: pygame.Surface, time_seconds: float) -> None:
        """Draw each tuft of weed, swaying."""
        for weed in self.weeds:
            direction_x, direction_y = weed.direction
            for blade, blade_length in enumerate(weed.blade_lengths):
                sway = math.sin(time_seconds * self.WEED_SWAY_SPEED + weed.phase + blade * 0.9) * self.WEED_SWAY
                # Blades fan out a little, and bend more towards the tip
                fan = (blade - (len(weed.blade_lengths) - 1) / 2) * 1.5
                middle = (
                    weed.base[0] + direction_x * blade_length * 0.5 - direction_y * (fan * 0.5 + sway * 0.35),
                    weed.base[1] + direction_y * blade_length * 0.5 + direction_x * (fan * 0.5 + sway * 0.35),
                )
                tip = (
                    weed.base[0] + direction_x * blade_length - direction_y * (fan + sway),
                    weed.base[1] + direction_y * blade_length + direction_x * (fan + sway),
                )
                pygame.draw.lines(screen, weed.color, False, [weed.base, middle, tip], 1)
