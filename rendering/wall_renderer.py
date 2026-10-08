"""Rough, reef-like drawing for maze walls.

Walls collide as straight line segments. This module draws each one as an
uneven ridge of rock instead of a ruled line: it wanders slightly, varies in
thickness and color, and has a lit and a shadowed edge. Each hit darkens it
and cracks it further. Some walls carry barnacles or a tuft of swaying weed.

The segments are the exposed faces of solid blocks. Each block is filled with
darker rock, so a wall reads as stone all the way through rather than as an
outline. A shot breaks a bite out of the block's edge where it landed, with
cracks running from it into the rock; another shot nearby opens the same
wound further. A bite is a hollow, not a hole: the rock outside the block's
true edge is gone, but inside it is only blackened, because the whole block
still stops whatever hits it.

A ridge never strays more than MAX_REACH from its true segment and always
covers it, and a block's fill stays inside the block, so what the player sees
is still what they collide with. Each wall's shape is derived from its end
points, so it looks the same every frame.

Walls are painted once onto a cached surface. When one is damaged or destroyed
only the patch around it is repainted. Weed is the only part drawn fresh each
frame.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, TYPE_CHECKING

import pygame
import config
from rendering.visual_effects import interpolate_color

if TYPE_CHECKING:
    from maze.wall_segment import WallSegment

Point = Tuple[float, float]
Color = Tuple[int, int, int]
SegmentKey = Tuple[Tuple[int, int], Tuple[int, int]]
BlockRect = Tuple[int, int, int, int]  # Left, top, width, height
Wound = Tuple[int, int]  # Point on a block's edge where a shot landed


@dataclass
class Weed:
    """A tuft of weed growing from a wall."""
    base: Point
    direction: Point  # Unit vector pointing away from the wall
    blade_lengths: Tuple[float, ...]
    phase: float
    color: Color


@dataclass
class Bite:
    """A chunk broken out of one edge of a block by one or more shots."""
    start: Tuple[int, int]  # Corner the edge runs from
    along: Tuple[int, int]  # Unit step along the edge
    inward: Tuple[int, int]  # Unit step into the block
    length: int  # Of the edge
    distance: float  # Along the edge to the first shot that landed here
    hits: int = 1
    seed: int = 0
    middle: float = 0.0  # Along the edge to the centre of the bite
    half: float = 0.0  # Half the width of its mouth
    depth: float = 0.0  # Into the block at its deepest
    # The broken face, as (distance along the edge, depth into the block)
    broken: List[Point] = field(default_factory=list)

    def place(self, distance: float, depth: float) -> Point:
        """Screen position of a point given along the edge and into the block."""
        return (
            self.start[0] + self.along[0] * distance + self.inward[0] * depth,
            self.start[1] + self.along[1] * distance + self.inward[1] * depth,
        )


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
    DAMAGE_DARKENING = 0.13  # Brightness a wall loses with each hit
    DARKEST_SHADE = 0.5  # However many hits it takes
    CRACK_SPACING = 30.0  # Pixels of ridge per crack, for each hit taken
    BITE_WIDTH = (0.2, 0.36)  # Of the length of the edge it is broken from
    BITE_DEPTH = (0.16, 0.26)  # Of the block's shorter side
    BITE_WIDENING = 0.4  # Growth in width for each further shot in the same place
    BITE_DEEPENING = 0.45  # And in depth
    BITE_MERGE = 0.22  # Shots this close, as a part of the edge, open the same wound
    BITE_CORNER_MARGIN = 11.0  # Pixels kept whole at each end of an edge, where walls join
    BITE_DARKNESS = 0.9  # How far the hollow of a bite is blackened
    BITE_FACE = 2.5  # Pixels of broken rock face showing around the hollow
    # Unbreakable blocks take any number of hits along a long run of wall, so
    # their bites range from a chip to a gouge, and the rock is stained around
    # each wound rather than darkened from side to side
    UNBREAKABLE_BITE_WIDTH = (0.1, 0.46)
    UNBREAKABLE_BITE_DEPTH = (0.07, 0.36)
    STAIN_SPREAD = 0.2  # Of the block's shorter side
    STAIN_GROWTH = 0.2  # Growth in spread for each further shot in the same place
    STAIN_REACH = 2.2  # Spreads the stain runs to before it has faded out
    STAIN_DARKNESS = 0.5  # Brightness lost at the heart of a stain
    STAIN_BLOTCH_AREA = 30  # Pixels of stain per blotch
    LIGHT = (-0.7071, -0.7071)  # Direction the light comes from: the top left
    FILL_SHADE = 0.5  # Brightness of the rock inside a block, against its faces
    FILL_BLOTCH_AREA = 150  # Pixels of block per blotch of mottling
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
        self._blocks: Dict[BlockRect, int] = {}  # Hit points shown for each filled block
        self._wounds: Dict[BlockRect, Tuple[Wound, ...]] = {}  # Where each block shown has been hit
        self._unbreakable: FrozenSet[BlockRect] = frozenset()  # Blocks that wear without ever going
        self._unbreakable_edges: Set[SegmentKey] = set()
        self._weed_by_segment: Dict[SegmentKey, Weed] = {}
        self._surface: Optional[pygame.Surface] = None
        self._origin = (0, 0)
        self._signature: Optional[Tuple[int, ...]] = None

    def draw(
        self,
        screen: pygame.Surface,
        walls: Sequence['WallSegment'],
        time_seconds: Optional[float] = None,
        animate: bool = True,
        blocks: Optional[Mapping[BlockRect, int]] = None,
        wounds: Optional[Mapping[BlockRect, Sequence[Wound]]] = None,
        unbreakable: Iterable[BlockRect] = ()
    ) -> None:
        """Draw the walls.

        Args:
            screen: The pygame Surface to draw on.
            walls: The maze's wall segments. Inactive ones are skipped.
            time_seconds: Clock for the swaying weed. Defaults to the pygame clock.
            animate: Draw the weed. Without it only the rock is drawn.
            blocks: Solid blocks to fill with rock, as screen area to hit points left.
            wounds: Where shots have landed on each block's edge, oldest first.
            unbreakable: Blocks that can never be destroyed, which show their damage differently.
        """
        blocks = blocks or {}
        unbreakable = frozenset(unbreakable)
        if unbreakable != self._unbreakable:
            self._unbreakable = unbreakable
            self._unbreakable_edges = {edge[0] for rect in unbreakable for edge in self._edges(rect)}
            # Everything is painted afresh
            self._surface = self._signature = None
        # Walls only ever lose hit points or vanish, so this changes whenever
        # the picture should
        count = hit_points = identity = 0
        for wall in walls:
            if wall.active:
                count += 1
                hit_points += wall.hit_points
                identity ^= id(wall)
        signature = (count, hit_points, identity, len(blocks), sum(blocks.values()))
        if signature != self._signature:
            self._signature = signature
            self._repaint(walls, blocks, wounds or {})

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

    def _repaint(
        self,
        walls: Sequence['WallSegment'],
        blocks: Mapping[BlockRect, int],
        wounds: Mapping[BlockRect, Sequence[Wound]]
    ) -> None:
        """Bring the cached picture up to date with the walls and blocks."""
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
        previous_blocks, self._blocks = self._blocks, dict(blocks)
        # A block is only ever wounded as it loses a hit point
        self._wounds = {rect: tuple(wounds.get(rect, ())) for rect in self._blocks}
        patches += [
            self._block_patch(rect) for rect in previous_blocks.keys() | self._blocks.keys()
            if previous_blocks.get(rect) != self._blocks.get(rect)
        ]
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
    
    def _block_patch(self, rect: BlockRect) -> pygame.Rect:
        """Area of the cached surface a block's fill paints on."""
        return pygame.Rect(rect).move(-self._origin[0], -self._origin[1])
    
    def _paint_everything(self) -> None:
        """Paint every wall onto a fresh cached surface."""
        self._weed_by_segment = {}
        if not self._segments and not self._blocks:
            self._surface = None
            return
        margin = int(math.ceil(self.MAX_REACH)) + 2
        xs = [point[0] for key in self._segments for point in key]
        ys = [point[1] for key in self._segments for point in key]
        for left, top, width, height in self._blocks:
            xs += [left, left + width]
            ys += [top, top + height]
        self._origin = (min(xs) - margin, min(ys) - margin)
        # One pixel more than the walls span, so the patch around a wall on the
        # far edge still fits and does not force everything to be repainted
        size = (max(xs) - min(xs) + 2 * margin + 1, max(ys) - min(ys) + 2 * margin + 1)
        self._surface = pygame.Surface(size)
        self._surface.fill(self.TRANSPARENT)
        # No RLE acceleration: it would be re-encoded on every patch repaint
        self._surface.set_colorkey(self.TRANSPARENT)
        self._paint_blocks(self._blocks.keys())
        self._paint_segments(self._segments.keys())
        self._paint_bites(self._blocks.keys())
    
    def _paint_patch(self, patch: pygame.Rect) -> None:
        """Repaint one patch of the cached surface from the walls and blocks crossing it."""
        keys = [key for key in self._segments if self._patch(key).colliderect(patch)]
        # A bite reaches out past its block's edge, over the wall's ridge
        reach = 2 * (int(math.ceil(self.MAX_REACH)) + 2)
        rects = [rect for rect in self._blocks if self._block_patch(rect).inflate(reach, reach).colliderect(patch)]
        # Those walls are painted whole on a scratch surface and the patch
        # copied across. Painting them clipped to the patch instead comes out
        # a few pixels different from how they were first painted
        area = patch.unionall([self._patch(key) for key in keys] + [self._block_patch(rect) for rect in rects])
        scratch = pygame.Surface(area.size)
        scratch.fill(self.TRANSPARENT)
        cache, origin = self._surface, self._origin
        self._surface, self._origin = scratch, (origin[0] + area.x, origin[1] + area.y)
        try:
            self._paint_blocks(rects)
            self._paint_segments(keys)
            self._paint_bites(rects)
        finally:
            self._surface, self._origin = cache, origin
        cache.blit(scratch, patch.topleft, patch.move(-area.x, -area.y))
    
    def _paint_blocks(self, rects) -> None:
        """Fill the given blocks with rock, cracked from wherever they have been hit."""
        surface = self._surface
        for rect in rects:
            left, top, width, height = rect
            if width < 1 or height < 1:
                continue
            shade = self.FILL_SHADE * self._damage_shade(self._darkening(rect))
            rng = self._rng(left, top, width, height)
            x, y = left - self._origin[0], top - self._origin[1]
            # Nothing spills over the block's edge, where there may be open space
            surface.set_clip(pygame.Rect(x, y, width, height))
            base = self._tint(rng, shade)
            surface.fill(base)
            for _ in range(max(3, width * height // self.FILL_BLOTCH_AREA)):
                centre = (x + rng.randrange(width), y + rng.randrange(height))
                pygame.draw.circle(surface, self._tint(rng, shade * rng.uniform(0.75, 1.2)), centre, rng.randint(2, 5))
            edge = interpolate_color(base, (254, 254, 254), 0.22)
            bites = self._bites(rect)
            if rect in self._unbreakable:
                for bite in bites:
                    self._paint_stain(surface, bite, min(width, height), shade)
            for bite in bites:
                self._paint_cracks(surface, bite, min(width, height), edge)
            surface.set_clip(None)
    
    def _darkening(self, rect: BlockRect) -> int:
        """Hits that darken a block from side to side. An unbreakable block is stained instead."""
        if rect in self._unbreakable:
            return 0
        return max(0, config.WALL_HIT_POINTS - self._blocks[rect])

    def _paint_stain(self, surface: pygame.Surface, bite: Bite, size: int, shade: float) -> None:
        """Darken the rock around a bite in a ragged patch that fades out. The surface is clipped to the block."""
        rng = self._rng(bite.start[0], bite.start[1], bite.seed, int(bite.distance), 15485863)
        origin_x, origin_y = self._origin
        spread = size * self.STAIN_SPREAD * (1 + self.STAIN_GROWTH * (bite.hits - 1))
        # Narrower near the end of an edge, so the stain stays within its block
        sideways = min(spread, min(bite.middle, bite.length - bite.middle) / self.STAIN_REACH)
        for _ in range(int(math.pi * sideways * spread * self.STAIN_REACH ** 2 / self.STAIN_BLOTCH_AREA)):
            across, inward = rng.gauss(0.0, 1.0), abs(rng.gauss(0.0, 1.0))
            faded = math.hypot(across, inward) / self.STAIN_REACH
            if faded >= 1.0:
                continue
            darkness = self.STAIN_DARKNESS * (1.0 - faded) * rng.uniform(0.5, 1.0)
            x, y = bite.place(bite.middle + across * sideways, inward * spread)
            pygame.draw.circle(
                surface, self._tint(rng, shade * (1.0 - darkness)),
                (int(x - origin_x), int(y - origin_y)), rng.randint(2, 4)
            )

    @staticmethod
    def _edges(rect: BlockRect) -> List[Tuple[SegmentKey, Tuple[int, int], Tuple[int, int], Tuple[int, int], int]]:
        """The four edges of a block: segment key, start, direction along, direction inward, length."""
        left, top, width, height = rect
        return [
            (((left, top), (left + width, top)), (left, top), (1, 0), (0, 1), width),
            (((left, top + height), (left + width, top + height)), (left, top + height), (1, 0), (0, -1), width),
            (((left, top), (left, top + height)), (left, top), (0, 1), (1, 0), height),
            (((left + width, top), (left + width, top + height)), (left + width, top), (0, 1), (-1, 0), height),
        ]

    def _bites(self, rect: BlockRect) -> List[Bite]:
        """Work out the bites broken from a block by the shots that have hit it.

        Shots that landed close together on one edge share a bite, which is
        wider and deeper for each of them but keeps its shape.
        """
        left, top, width, height = rect
        # Only a face onto open space can have been hit
        edges = [edge for edge in self._edges(rect) if edge[0] in self._segments]
        bites: List[Bite] = []
        for x, y in self._wounds.get(rect, ()):
            if not edges:
                break
            _, start, along, inward, length = min(
                edges, key=lambda edge: abs((x - edge[1][0]) * edge[3][0] + (y - edge[1][1]) * edge[3][1])
            )
            distance = (x - start[0]) * along[0] + (y - start[1]) * along[1]
            for bite in bites:
                if bite.inward == inward and abs(bite.distance - distance) <= length * self.BITE_MERGE:
                    bite.hits += 1
                    break
            else:
                seed = (inward[0] + 1) * 3 + inward[1] + 1
                bites.append(Bite(start, along, inward, length, distance, seed=seed))

        unbreakable = rect in self._unbreakable
        width_range = self.UNBREAKABLE_BITE_WIDTH if unbreakable else self.BITE_WIDTH
        depth_range = self.UNBREAKABLE_BITE_DEPTH if unbreakable else self.BITE_DEPTH
        shaped = []
        for bite in bites:
            rng = self._rng(left, top, width, height, 104723, bite.seed, int(bite.distance))
            further = bite.hits - 1
            across = height if bite.along[0] else width
            bite.half = bite.length * rng.uniform(*width_range) / 2 * (1 + self.BITE_WIDENING * further)
            bite.depth = min(width, height) * rng.uniform(*depth_range) * (1 + self.BITE_DEEPENING * further)
            bite.depth = min(bite.depth, across * 0.6)
            # Corners are left whole, where other walls join. The broken face
            # may undercut the mouth a little at either end
            bite.half = min(bite.half, (bite.length / 2 - self.BITE_CORNER_MARGIN) / 1.2)
            if bite.half < 2.0:
                continue
            room = self.BITE_CORNER_MARGIN + bite.half * 1.2
            bite.middle = max(room, min(bite.length - room, bite.distance))

            # An uneven broken face: steep sides, a ragged floor, a flat
            # shelf somewhere and perhaps an overhang at either lip
            steps = sorted(rng.uniform(-0.85, 0.85) for _ in range(rng.randint(4, 6)))
            depths = [(1.0 - step * step) ** 0.6 * rng.uniform(0.55, 1.0) for step in steps]
            shelf = rng.randrange(len(steps) - 1)
            depths[shelf + 1] = depths[shelf]
            if rng.random() < 0.6:
                steps[0], depths[0] = -1.0 - rng.uniform(0.05, 0.2), max(depths[0], 0.4)
            if rng.random() < 0.6:
                steps[-1], depths[-1] = 1.0 + rng.uniform(0.05, 0.2), max(depths[-1], 0.4)
            deepest = max(depths)
            bite.broken = (
                [(bite.middle - bite.half, 0.0)]
                + [(bite.middle + step * bite.half, bite.depth * depth / deepest) for step, depth in zip(steps, depths)]
                + [(bite.middle + bite.half, 0.0)]
            )
            shaped.append(bite)
        return shaped

    def _paint_cracks(self, surface: pygame.Surface, bite: Bite, size: int, edge: Color) -> None:
        """Run cracks into the rock from the broken face of a bite. The surface is clipped to the block."""
        rng = self._rng(bite.start[0], bite.start[1], bite.seed, int(bite.distance), 7919)
        origin_x, origin_y = self._origin
        mouth = bite.place(bite.middle, 0.0)
        reach = 1 + 0.3 * (bite.hits - 1)
        for _ in range(min(5, 2 + bite.hits)):
            # Each starts somewhere on the broken face and heads away from the mouth
            x, y = bite.place(*bite.broken[rng.randrange(1, len(bite.broken) - 1)])
            heading = math.atan2(y - mouth[1], x - mouth[0]) + rng.uniform(-0.5, 0.5)
            crack = [(x - origin_x, y - origin_y)]
            for _ in range(rng.randint(3, 5)):
                heading += rng.uniform(-0.6, 0.6)
                stride = size * rng.uniform(0.07, 0.13) * reach
                x, y = x + math.cos(heading) * stride, y + math.sin(heading) * stride
                crack.append((x - origin_x, y - origin_y))
            # A pale line beside the dark one, so it reads as a split in the rock
            pygame.draw.lines(surface, edge, False, [(px + 1, py + 1) for px, py in crack], 1)
            pygame.draw.lines(surface, self.CRACK_COLOR, False, crack, 1)
            if bite.hits > 1:
                # Wider where it leaves a wound that has been struck again
                pygame.draw.lines(surface, self.CRACK_COLOR, False, crack[:3], 2)

    def _paint_bites(self, rects) -> None:
        """Break bites out of the edges of the given blocks, where shots have landed."""
        surface = self._surface
        origin_x, origin_y = self._origin
        reach = int(math.ceil(self.MAX_REACH)) + 1
        for rect in rects:
            left, top, width, height = rect
            if width < 1 or height < 1:
                continue
            bites = self._bites(rect)
            if not bites:
                continue
            # The same rock the block was filled with
            base = self._tint(
                self._rng(left, top, width, height), self.FILL_SHADE * self._damage_shade(self._darkening(rect))
            )
            hollow = interpolate_color(base, (0, 0, 0), self.BITE_DARKNESS)
            face = interpolate_color(base, (0, 0, 0), 0.45)
            inside = pygame.Rect(left - origin_x, top - origin_y, width, height)
            for bite in bites:
                def place(distance: float, depth: float) -> Point:
                    x, y = bite.place(distance, depth)
                    return (x - origin_x, y - origin_y)

                # The wall's ridge goes entirely, outside the block's true edge
                pygame.draw.polygon(surface, self.TRANSPARENT, [
                    place(bite.middle - bite.half, 0), place(bite.middle + bite.half, 0),
                    place(bite.middle + bite.half + 1, -reach), place(bite.middle - bite.half - 1, -reach),
                ])
                surface.set_clip(inside)
                mouth = [(bite.middle + bite.half, -2.0), (bite.middle - bite.half, -2.0)]
                # A band of broken rock face, then the hollow itself set
                # back from it towards the mouth
                pygame.draw.polygon(surface, face, [place(*point) for point in mouth + bite.broken])
                hollowed = []
                for distance, depth in bite.broken:
                    away = math.hypot(distance - bite.middle, depth)
                    keep = max(0.0, away - self.BITE_FACE) / away if away > 0 else 0.0
                    hollowed.append((bite.middle + (distance - bite.middle) * keep, depth * keep))
                pygame.draw.polygon(surface, hollow, [place(*point) for point in mouth + hollowed])

                # Each stretch of the broken face is lit by how squarely it
                # is turned to the light, and shadowed if turned away
                points = [place(*point) for point in bite.broken]
                centre = place(bite.middle, bite.depth * 0.3)
                for first, second in zip(points, points[1:]):
                    span = math.hypot(second[0] - first[0], second[1] - first[1])
                    if span < 0.5:
                        continue
                    normal = ((second[1] - first[1]) / span, (first[0] - second[0]) / span)
                    middle = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
                    # Facing out of the rock, into the hollow
                    if normal[0] * (centre[0] - middle[0]) + normal[1] * (centre[1] - middle[1]) < 0:
                        normal = (-normal[0], -normal[1])
                    light = normal[0] * self.LIGHT[0] + normal[1] * self.LIGHT[1]
                    if light > 0.15:
                        color = interpolate_color(base, (254, 254, 254), 0.25 + 0.45 * light)
                    else:
                        color = interpolate_color(base, (0, 0, 0), 0.7)
                    pygame.draw.line(surface, color, first, second, 1)
                surface.set_clip(None)

    def _paint_segments(self, keys) -> None:
        """Paint the given segments and the joints at their ends."""
        keys = list(keys)
        for key in keys:
            self._paint_ridge(self._surface, key, self._segments[key])
        # Knobbly joints go on top so corners look the same from every wall
        for corner in {point for key in keys for point in key}:
            self._paint_joint(self._surface, corner)
    
    def _damage_shade(self, damage: int) -> float:
        """Brightness of rock that has taken the given number of hits."""
        return max(self.DARKEST_SHADE, 1.0 - self.DAMAGE_DARKENING * damage)

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
        """Paint one wall as an uneven ridge, cracked by the hits it has taken."""
        (ax, ay), (bx, by) = key
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            return
        rng = self._rng(ax, ay, bx, by)
        along_x, along_y = (bx - ax) / length, (by - ay) / length
        normal_x, normal_y = -along_y, along_x
        origin_x, origin_y = self._origin
        # The face of an unbreakable block only shows damage where it was hit
        damage = 0 if key in self._unbreakable_edges else max(0, config.WALL_HIT_POINTS - hit_points)
        shade = self._damage_shade(damage)
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

        if damage:
            # A separate stream, so cracks appear without reshaping the rock
            crack_rng = self._rng(ax, ay, bx, by, 7919)
            for _ in range(damage * max(1, int(length / self.CRACK_SPACING))):
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
