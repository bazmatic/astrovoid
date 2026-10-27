"""CaveShape: the cave field's rock outline as the maze's WallSegments.

Each maze tile's contour (maze/cave_contour.py) becomes short WallSegments, rock on the right,
each belonging to the wall cell that owns the rock just behind it, so damage still lands on a
block. Steel strong walls keep the square converter faces. When a block is destroyed, the field
is rebuilt and only the tiles around the change are re-traced; unchanged segments keep their
objects, so callers can patch spatial indexes and caches with the (removed, added) diff.
"""
import math
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pygame

from config import CaveSettings
from maze.cave_contour import tile_polylines
from maze.cave_field import THRESHOLD, CaveField, Cell, SampleGrid
from maze.converter import SIDES, GridToWallsConverter
from maze.positioning import MazePositionCalculator
from maze.wall_segment import WallSegment

Key = Tuple[Tuple[float, float], Tuple[float, float], Cell]


def _key(segment: WallSegment) -> Key:
    return ((round(segment.start[0], 3), round(segment.start[1], 3)),
            (round(segment.end[0], 3), round(segment.end[1], 3)), segment.cell)


class CaveShape:
    def __init__(self, grid: List[List[int]], calc: MazePositionCalculator,
                 converter: GridToWallsConverter, *, strong: FrozenSet[Cell],
                 keep_clear: Sequence[Tuple[Tuple[float, float], float]], seed: int,
                 settings: CaveSettings, hit_points: Callable[[Cell], int]):
        self.grid = grid
        self.calc = calc
        self.converter = converter
        self.strong = frozenset(strong)
        self.settings = settings
        self.hit_points = hit_points
        rows, cols = len(grid), len(grid[0])
        samples = SampleGrid.for_maze(calc, cols, rows, settings)
        self.field = CaveField(grid, samples, strong=self.strong, keep_clear=keep_clear, seed=seed,
                               settings=settings)
        self.version = 0
        self._territory: Dict[Cell, Optional[Tuple[pygame.Rect, pygame.mask.Mask]]] = {}
        self._territory_version = 0
        s = samples
        self._push = min(s.h_x, s.h_y)  # px into the rock to find a segment's owner
        self._steel_reach = max(s.h_x, s.h_y)
        self._steel_rects = np.array([(s.origin[0] + c*s.cell_w, s.origin[1] + r*s.cell_h,
                                       s.origin[0] + (c+1)*s.cell_w, s.origin[1] + (r+1)*s.cell_h)
                                      for c, r in sorted(self.strong)], float).reshape(-1, 4)
        self._fallback: Dict[Cell, set] = {}  # cell -> tiles with segments it owns by _nearest_wall
        self._tiles: Dict[Cell, List[WallSegment]] = {
            (c, r): self._trace((c, r)) for r in range(rows) for c in range(cols)}

    # Queries

    def segments(self) -> List[WallSegment]:
        """The current outline: every tile's segments, row by row."""
        return [segment for tile in self._tiles.values() for segment in tile]

    def is_rock(self, pos: Tuple[float, float]) -> bool:
        return self.field.is_rock(*pos)

    def territory(self, cell: Cell) -> Optional[Tuple[pygame.Rect, pygame.mask.Mask]]:
        """Screen pixels that are rock and owned by `cell`, as (bounding rect, mask over that
        rect); None if there are none (open and steel cells own no rock)."""
        if self._territory_version != self.version:
            self._territory.clear()
            self._territory_version = self.version
        if cell not in self._territory:
            self._territory[cell] = self._make_territory(cell)
        return self._territory[cell]

    # Destroying blocks

    def open_cell(self, cell: Cell) -> Tuple[List[WallSegment], List[WallSegment]]:
        """Rebuild after the caller set grid[row][col] = 0 for `cell`. Returns (removed, added):
        the segment objects that no longer exist, and the new ones."""
        return self.open_cells([cell])

    def open_cells(self, cells: Iterable[Cell]) -> Tuple[List[WallSegment], List[WallSegment]]:
        """open_cell for several cells at once (a blast): one field rebuild and one re-trace."""
        cells = list(dict.fromkeys(cells))
        field = self.field
        old_values, old_owner = field.values, field.owner
        field.rebuild()
        # A tile's segments depend on the values in its closed rect and on the owners at most
        # one sample beyond it (the midpoint pushed into rock, rounded to a sample). So re-trace
        # the tiles within a sample of a changed value or owner: like re-tracing the changed
        # tiles and their 8 neighbours, but at sample rather than tile granularity.
        moved = (field.values != old_values) | (field.owner != old_owner)
        retrace = field.tiles_of(_dilate(moved))
        for cell in cells:
            retrace[cell[1], cell[0]] = True
            for side in SIDES:
                beside = (cell[0]+side[0], cell[1]+side[1])
                if beside in self.strong:
                    retrace[beside[1], beside[0]] = True  # a newly exposed steel face
            for tile in self._fallback.pop(cell, ()):
                retrace[tile[1], tile[0]] = True  # owners found by _nearest_wall can sit further away

        removed: List[WallSegment] = []
        added: List[WallSegment] = []
        for r, c in zip(*np.nonzero(retrace)):
            tile = (int(c), int(r))
            current: Dict[Key, List[WallSegment]] = {}
            for segment in self._tiles[tile]:
                current.setdefault(_key(segment), []).append(segment)
            kept = []
            for segment in self._trace(tile):
                same = current.get(_key(segment))
                if same:
                    kept.append(same.pop())
                else:
                    kept.append(segment)
                    added.append(segment)
            for leftovers in current.values():
                removed.extend(leftovers)
            self._tiles[tile] = kept
        self.version += 1
        return removed, added

    # Building

    def _trace(self, tile: Cell) -> List[WallSegment]:
        """The segments for one tile: its rock contour, plus the faces of a steel cell there."""
        out = []
        tolerance = self.settings.simplifyTolerance
        for line in tile_polylines(self.field.values, self.field.samples, tile, tolerance):
            for start, end in zip(line, line[1:]):
                if start == end:
                    continue  # a contour through a sample point
                mid = ((start[0]+end[0]) / 2, (start[1]+end[1]) / 2)
                if self._near_steel(mid):
                    continue
                cell = self._owner(start, end, mid, tile)
                out.append(WallSegment(start, end, self.hit_points(cell), self._destructible(cell), cell))
        if tile in self.strong:
            for side in SIDES:
                if not self.converter.is_wall(self.grid, tile[0]+side[0], tile[1]+side[1]):
                    out.append(self.converter.face(self.grid, tile, side, self.hit_points(tile)))
        return out

    def _destructible(self, cell: Cell) -> bool:
        return not (cell in self.strong or self.converter.on_perimeter(self.grid, *cell))

    def _near_steel(self, point: Tuple[float, float]) -> bool:
        if not len(self._steel_rects):
            return False
        x, y = point
        rects = self._steel_rects
        gx = np.maximum(0.0, np.maximum(rects[:, 0] - x, x - rects[:, 2]))
        gy = np.maximum(0.0, np.maximum(rects[:, 1] - y, y - rects[:, 3]))
        return bool(np.any(gx*gx + gy*gy <= self._steel_reach**2))

    def _owner(self, start, end, mid, tile: Cell) -> Cell:
        """The wall cell owning the rock just to the right of a segment's midpoint."""
        s, owner = self.field.samples, self.field.owner
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        px, py = mid[0] - dy/length*self._push, mid[1] + dx/length*self._push
        fy, fx = s.fractional(px, py)
        rows, cols = owner.shape
        index = int(owner[min(max(int(round(fy)), 0), rows-1), min(max(int(round(fx)), 0), cols-1)])
        if index >= 0:
            return (index % s.cols, index // s.cols)
        cell = self._nearest_wall(mid)
        self._fallback.setdefault(cell, set()).add(tile)
        return cell

    def _nearest_wall(self, point: Tuple[float, float]) -> Cell:
        """The wall cell whose rect is nearest `point`, preferring non-steel cells."""
        s = self.field.samples
        walls = np.asarray(self.grid) == 1
        for cells in (walls & ~_mask(self.strong, walls.shape), walls):
            rows, cols = np.nonzero(cells)
            if len(rows):
                break
        x, y = point
        x0, y0 = s.origin[0] + cols*s.cell_w, s.origin[1] + rows*s.cell_h
        gx = np.maximum(0.0, np.maximum(x0 - x, x - (x0 + s.cell_w)))
        gy = np.maximum(0.0, np.maximum(y0 - y, y - (y0 + s.cell_h)))
        i = int(np.argmin(gx*gx + gy*gy))
        return (int(cols[i]), int(rows[i]))

    def _make_territory(self, cell: Cell) -> Optional[Tuple[pygame.Rect, pygame.mask.Mask]]:
        field, s = self.field, self.field.samples
        c, r = cell
        if self.grid[r][c] != 1 or cell in self.strong:
            return None
        # Rock is owned by the nearest wall among the 3x3 around it, so it lies in c's 3x3
        # The first pixels whose centres lie inside the maze
        left = max(int(math.floor(s.origin[0] + (c-1)*s.cell_w)), int(math.ceil(s.origin[0] - 0.5)))
        top = max(int(math.floor(s.origin[1] + (r-1)*s.cell_h)), int(math.ceil(s.origin[1] - 0.5)))
        right = min(int(math.ceil(s.origin[0] + (c+2)*s.cell_w)), int(math.floor(s.origin[0] + s.cols*s.cell_w + 0.5)))
        bottom = min(int(math.ceil(s.origin[1] + (r+2)*s.cell_h)), int(math.floor(s.origin[1] + s.rows*s.cell_h + 0.5)))
        if right <= left or bottom <= top:
            return None
        fy = (np.arange(top, bottom) + 0.5 - s.origin[1]) / s.h_y
        fx = (np.arange(left, right) + 0.5 - s.origin[0]) / s.h_x
        values = _bilinear(field.values, fy, fx)
        rows, cols = field.owner.shape
        iy = np.clip(np.rint(fy).astype(int), 0, rows-1)
        ix = np.clip(np.rint(fx).astype(int), 0, cols-1)
        owned = (values >= THRESHOLD) & (field.owner[np.ix_(iy, ix)] == r*s.cols + c)
        ys, xs = np.nonzero(owned)
        if not len(ys):
            return None
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = owned[y0:y1, x0:x1]
        surface = pygame.Surface((x1 - x0, y1 - y0), pygame.SRCALPHA)
        alpha = pygame.surfarray.pixels_alpha(surface)
        alpha[:] = crop.T * 255
        del alpha
        return pygame.Rect(left + x0, top + y0, x1 - x0, y1 - y0), pygame.mask.from_surface(surface)


def _bilinear(values: np.ndarray, fy: np.ndarray, fx: np.ndarray) -> np.ndarray:
    """values sampled at fractional (fy x fx) indices, as a (len(fy), len(fx)) array."""
    rows, cols = values.shape
    fy, fx = np.clip(fy, 0, rows-1), np.clip(fx, 0, cols-1)
    iy, ix = np.minimum(fy.astype(int), rows-2), np.minimum(fx.astype(int), cols-2)
    ty, tx = (fy - iy)[:, None], (fx - ix)[None, :]
    a, b = values[np.ix_(iy, ix)], values[np.ix_(iy, ix+1)]
    c, d = values[np.ix_(iy+1, ix)], values[np.ix_(iy+1, ix+1)]
    top, bottom = a + (b-a)*tx, c + (d-c)*tx
    return top + (bottom-top)*ty


def _dilate(mask: np.ndarray) -> np.ndarray:
    """mask grown by one element in all 8 directions."""
    return cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0


def _mask(cells, shape) -> np.ndarray:
    out = np.zeros(shape, bool)
    for c, r in cells:
        out[r, c] = True
    return out
