"""The cave field: a smooth rock/open scalar field over the maze cells.

Cell occupancy is blurred and shaped with value noise, then clamped: wall cores stay rock,
open-cell centres, links, gate swings and spawn discs stay open, steel stays square, and there is
no floating rock or sealed pocket. Passages may narrow where the rock bulges (the seed fixes how).
Rock is wherever the field is at least THRESHOLD; later steps trace that outline into walls.

All shape tuning is in cell fractions of sqrt(cell_w*cell_h), so the curve scales with the cell;
clearances are pixel radii. Arrays are indexed [iy, ix] and grids grid[row][col].
"""
import math
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from config import CaveSettings

Cell = Tuple[int, int]  # (col, row), as Maze.blocks keys

THRESHOLD = 0.5
MARGIN = 0.05
_OPEN = THRESHOLD - MARGIN
_ROCK = THRESHOLD + MARGIN
# A clamped wall face: rock, but so barely that the outline between it and a clamped open sample
# sits within a twentieth of a sample of the face (rather than up to a whole sample out from it)
_FACE = THRESHOLD + MARGIN/20


@dataclass(frozen=True)
class SampleGrid:
    """Field samples: per_x by per_y spacings per cell, with samples on every cell border."""
    cols: int
    rows: int
    cell_w: float
    cell_h: float
    origin: Tuple[float, float]
    per_x: int
    per_y: int

    @property
    def shape(self) -> Tuple[int, int]:
        return (self.rows*self.per_y + 1, self.cols*self.per_x + 1)

    @property
    def h_x(self) -> float:
        return self.cell_w / self.per_x

    @property
    def h_y(self) -> float:
        return self.cell_h / self.per_y

    def point(self, iy: int, ix: int) -> Tuple[float, float]:
        return (self.origin[0] + ix*self.h_x, self.origin[1] + iy*self.h_y)

    def fractional(self, x: float, y: float) -> Tuple[float, float]:
        return ((y - self.origin[1]) / self.h_y, (x - self.origin[0]) / self.h_x)

    def cell_of_sample(self, iy: int, ix: int) -> Cell:
        return (min(ix // self.per_x, self.cols-1), min(iy // self.per_y, self.rows-1))

    @classmethod
    def for_maze(cls, calc, cols: int, rows: int, settings: CaveSettings) -> 'SampleGrid':
        def per(size: float) -> int:
            n = max(settings.minSamplesPerCell, math.ceil(size / settings.maxSampleSpacing))
            # Even, so every cell centre and every centre-to-centre link lies on samples
            return n + n % 2
        return cls(cols, rows, calc.cell_size_x, calc.cell_size_y, (calc.offset_x, calc.offset_y),
                   per(calc.cell_size_x), per(calc.cell_size_y))


class _Axis:
    """Per-axis sample bookkeeping (x or y), so 2D work is broadcasting of 1D arrays. It covers
    samples lo..hi-1 (all of them by default); per-sample arrays and sample indices in
    touched_runs are relative to lo, cell numbers are the grid's."""

    def __init__(self, count: int, per: int, cells: int, size: float, start: float,
                 lo: int = 0, hi: Optional[int] = None):
        self.args = (count, per, cells, size, start)
        index = np.arange(lo, count if hi is None else hi)
        self.pos = start + index * (size / per)  # px
        self.cell = np.minimum(index // per, cells-1)  # containing cell, clamped
        self.local = self.pos - (start + self.cell*size)  # px from the containing cell's start
        self.cells, self.size, self.start = cells, size, start
        self.centres = np.arange(cells)*per + per//2  # sample index of each cell centre
        border = index[index % per == 0]
        # The cells a sample touches, as (cell per sample, sample indices) runs: every sample's
        # own cell, then the previous cell for samples on a cell border. A cell may be -1 or
        # `cells`, outside the grid.
        self.touched_runs = ((index // per, index - lo), (border // per - 1, border - lo))

    def window(self, lo: int, hi: int) -> '_Axis':
        return _Axis(*self.args, lo, hi)


class CaveField:
    def __init__(self, grid: List[List[int]], samples: SampleGrid, *, strong: FrozenSet[Cell],
                 keep_clear: Sequence[Tuple[Tuple[float, float], float]], seed: int,
                 settings: CaveSettings):
        self.grid = grid
        self.samples = samples
        self.strong = frozenset(strong)
        self.keep_clear = list(keep_clear)
        self.seed = seed
        self.settings = settings
        rows, cols = samples.shape
        self._x = _Axis(cols, samples.per_x, samples.cols, samples.cell_w, samples.origin[0])
        self._y = _Axis(rows, samples.per_y, samples.rows, samples.cell_h, samples.origin[1])
        self._unit = math.sqrt(samples.cell_w * samples.cell_h)  # px in one "cell" of tuning
        self._noise = self._make_noise()
        self._kernels = self._blur_kernels()
        # Per-sample state before the global cleanup, kept so a rebuild redoes only a window
        self._walls: Optional[np.ndarray] = None
        self._base: Optional[np.ndarray] = None
        self._core: Optional[np.ndarray] = None
        self._kept_open: Optional[np.ndarray] = None
        self.values: Optional[np.ndarray] = None
        self.rock: Optional[np.ndarray] = None
        self.owner: Optional[np.ndarray] = None
        self.rebuild()

    # Queries

    def value_at(self, x: float, y: float) -> float:
        fy, fx = self.samples.fractional(x, y)
        rows, cols = self.values.shape
        fy, fx = min(max(fy, 0.0), rows-1.0), min(max(fx, 0.0), cols-1.0)
        iy, ix = min(int(fy), rows-2), min(int(fx), cols-2)
        ty, tx = fy - iy, fx - ix
        v = self.values
        top = v[iy, ix]*(1-tx) + v[iy, ix+1]*tx
        bottom = v[iy+1, ix]*(1-tx) + v[iy+1, ix+1]*tx
        return float(top*(1-ty) + bottom*ty)

    def is_rock(self, x: float, y: float) -> bool:
        return self.value_at(x, y) >= THRESHOLD

    def outline_margin(self) -> float:
        """How far inside a clamped disc the outline can still reach: it runs between samples, so
        it can lie up to one sample spacing nearer than the nearest rock sample."""
        return max(self.samples.h_x, self.samples.h_y)

    # Building

    def rebuild(self) -> np.ndarray:
        """Recompute after `grid` changed; returns a (rows, cols) mask of tiles whose rock changed.

        The per-sample clamps only reach a few cells, so they are redone in a window around the
        changed cells; the cleanup, which is global, runs on the whole field."""
        s = self.samples
        walls = np.asarray(self.grid) == 1
        steel = np.zeros_like(walls)
        for c, r in self.strong:
            steel[r, c] = True
        rows, cols = s.shape
        if self._walls is None:
            window = owner_window = (0, rows, 0, cols)
            self._base = np.zeros(s.shape, np.float32)
            self._core, self._kept_open = np.zeros(s.shape, bool), np.zeros(s.shape, bool)
            self.owner = np.full(s.shape, -1, np.int32)
        else:
            changed_cells = np.argwhere(walls != self._walls)
            if not len(changed_cells):
                return np.zeros(walls.shape, bool)
            box = (*changed_cells.min(axis=0), *changed_cells.max(axis=0))
            # The blur reaches 3 sigma (plus a sample); skeletons and owners one cell
            reach = 3*self.settings.blurCells*self._unit
            window = self._sample_window(box, math.ceil(reach / s.cell_w) + 1,
                                         math.ceil(reach / s.cell_h) + 1)
            owner_window = self._sample_window(box, 1, 1)
            self.owner = self.owner.copy()  # a new array, so callers can diff against the old one
        self._walls = walls
        y0, y1, x0, x1 = window
        at = (slice(y0, y1), slice(x0, x1))
        self._base[at], self._core[at], self._kept_open[at] = \
            self._local(walls, steel, window, self._x.window(x0, x1), self._y.window(y0, y1))
        y0, y1, x0, x1 = owner_window
        self.owner[y0:y1, x0:x1] = self._nearest_cell(
            walls & ~steel, self._x.window(x0, x1), self._y.window(y0, y1))[1]

        values = self._base.copy()
        centres = self._open_centres(walls)
        self._cleanup(values, self._core, centres, self._kept_open)

        rock = values >= THRESHOLD
        changed = np.ones_like(rock) if self.rock is None else rock != self.rock
        self.values, self.rock = values, rock
        return self.tiles_of(changed)

    def _sample_window(self, box, kx: int, ky: int) -> Tuple[int, int, int, int]:
        """Sample range (y0, y1, x0, x1) of the cells in box (r0, c0, r1, c1) grown by kx, ky."""
        s = self.samples
        rows, cols = s.shape
        r0, c0, r1, c1 = box
        return (max(0, (r0-ky)*s.per_y), min(rows, (r1+ky+1)*s.per_y + 1),
                max(0, (c0-kx)*s.per_x), min(cols, (c1+kx+1)*s.per_x + 1))

    def _local(self, walls: np.ndarray, steel: np.ndarray, window, x: '_Axis', y: '_Axis'):
        """The field before cleanup over a sample window, with the per-sample masks the global
        passes need: (values, core, kept_open)."""
        s, cfg = self.samples, self.settings
        y0, y1, x0, x1 = window
        blurred, wall_sample = self._blur(walls, window)
        open_sample = ~wall_sample
        values = blurred + self._noise[y0:y1, x0:x1]

        # Wall cores: the skeleton through wall centres, linked to wall neighbours and the outside
        core = wall_sample & self._near_skeleton(walls, True, cfg.wallCoreCells*self._unit, x, y)
        np.maximum(values, _ROCK, out=values, where=core)

        # Wall-cell samples on a face towards open space, which a clamp may pin to the face
        steel_sample = self._touches(steel, False, x, y) if steel.any() else np.zeros_like(core)
        face = wall_sample & self._touches(~walls, False, x, y) & ~core & ~steel_sample

        # Open space the clamps promise (gate swings, spawns, steel faces) must survive the hole
        # cleanup. The outline stays out of each disc: open samples within it, plus the outline
        # margin, are clamped open, and wall faces there are pinned so the outline lies on them.
        pinned = np.zeros(values.shape, bool)
        margin = self.outline_margin()
        for (cx, cy), radius in self.keep_clear:
            pinned |= ((x.pos[None, :]-cx)**2 + (y.pos[:, None]-cy)**2) <= (radius + margin)**2
        kept_open = pinned & open_sample
        np.minimum(values, _OPEN, out=values, where=kept_open)
        np.minimum(values, _FACE, out=values, where=pinned & face)

        links = self._near_skeleton(~walls, False, cfg.linkClearance, x, y)
        np.minimum(values, _OPEN, out=values, where=links & open_sample)

        if steel.any():
            values[steel_sample] = 1.0
            near_steel, _ = self._nearest_cell(steel, x, y)
            steel_face = open_sample & (near_steel <= 0.5*min(s.cell_w, s.cell_h))
            np.minimum(values, _OPEN, out=values, where=steel_face)
            kept_open |= steel_face
        return values, core, kept_open

    def _touches(self, cells: np.ndarray, outside: bool, x: '_Axis', y: '_Axis') -> np.ndarray:
        """Per sample: does it touch (lie in or on the border of) any cell in `cells`?"""
        padded = np.pad(cells, 1, constant_values=outside)
        out = np.zeros((len(y.pos), len(x.pos)), bool)
        for ty, rows in y.touched_runs:
            for tx, cols in x.touched_runs:
                out[np.ix_(rows, cols)] |= padded[np.ix_(ty+1, tx+1)]
        return out

    def _blur_kernels(self):
        """Gaussian kernels and their radii in samples, x then y."""
        sigma = self.settings.blurCells * self._unit
        out = []
        for h in (self.samples.h_x, self.samples.h_y):
            sd = sigma / h
            radius = max(1, math.ceil(3*sd))
            k = np.exp(-0.5*(np.arange(-radius, radius+1)/sd)**2)
            out.append(((k/k.sum()).astype(np.float32), radius))
        return out

    def _blur(self, walls: np.ndarray, window) -> Tuple[np.ndarray, np.ndarray]:
        """Blurred wall occupancy over a sample window (outside the grid is rock), and the
        occupancy itself (samples touching a wall cell) over the window."""
        (kx, px), (ky, py) = self._kernels
        rows, cols = self.samples.shape
        y0, y1, x0, x1 = window
        ey0, ey1, ex0, ex1 = max(0, y0-py), min(rows, y1+py), max(0, x0-px), min(cols, x1+px)
        occupancy = self._touches(walls, True, self._x.window(ex0, ex1), self._y.window(ey0, ey1))
        pad = ((py - (y0-ey0), py - (ey1-y1)), (px - (x0-ex0), px - (ex1-x1)))
        padded = np.pad(occupancy.astype(np.float32), pad, constant_values=1.0)
        blurred = cv2.sepFilter2D(padded, cv2.CV_32F, kx, ky, borderType=cv2.BORDER_REPLICATE)
        return blurred[py:-py, px:-px], occupancy[y0-ey0:y1-ey0, x0-ex0:x1-ex0]

    def _make_noise(self) -> np.ndarray:
        cfg = self.settings
        total = np.zeros(self.samples.shape, np.float32)
        for i, (scale, weight) in enumerate(zip(cfg.noiseScalesCells, cfg.noiseWeights)):
            spacing = scale * self._unit
            u = (self._x.pos - self._x.start) / spacing
            v = (self._y.pos - self._y.start) / spacing
            iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
            su, sv = _smoothstep(u - iu), _smoothstep(v - iv)
            size = max(iu.max(), iv.max()) + 2
            lattice = _lattice(np.random.default_rng(self.seed*1009 + i), size)
            a, b = lattice[np.ix_(iv, iu)], lattice[np.ix_(iv, iu+1)]
            c, d = lattice[np.ix_(iv+1, iu)], lattice[np.ix_(iv+1, iu+1)]
            top, bottom = a + (b-a)*su[None, :], c + (d-c)*su[None, :]
            n = top + (bottom-top)*sv[:, None]
            total += (weight * (n - 0.5)).astype(np.float32)
        return cfg.noiseAmplitude * total

    def _near_skeleton(self, cells: np.ndarray, outside: bool, reach: float, x: '_Axis',
                       y: '_Axis') -> np.ndarray:
        """Per sample: within `reach` px of the skeleton of `cells`? The skeleton is each centre,
        plus lines to the centres of orthogonal neighbours in `cells` (`outside` says whether
        the virtual cells beyond the grid count). Only cells the sample touches are considered."""
        padded = np.pad(cells, 1, constant_values=outside)
        left, right = padded[1:-1, :-2] & cells, padded[1:-1, 2:] & cells
        up, down = padded[:-2, 1:-1] & cells, padded[2:, 1:-1] & cells
        out = np.zeros((len(y.pos), len(x.pos)), bool)
        # The containing cell for every sample; the previous cell only matters on borders
        for ty, rows in y.touched_runs:
            dy = (y.pos[rows] - (y.start + (ty+0.5)*y.size))[:, None]
            row = np.clip(ty, 0, y.cells-1)
            valid_y = ((ty >= 0) & (ty < y.cells))[:, None]
            for tx, cols in x.touched_runs:
                dx = (x.pos[cols] - (x.start + (tx+0.5)*x.size))[None, :]
                col = np.clip(tx, 0, x.cells-1)
                at = np.ix_(row, col)
                near = (dx*dx + dy*dy <= reach*reach)
                near |= (np.abs(dy) <= reach) & (((dx < 0) & left[at]) | ((dx > 0) & right[at]))
                near |= (np.abs(dx) <= reach) & (((dy < 0) & up[at]) | ((dy > 0) & down[at]))
                near &= cells[at] & valid_y & ((tx >= 0) & (tx < x.cells))[None, :]
                out[np.ix_(rows, cols)] |= near
        return out

    def _nearest_cell(self, cells: np.ndarray, x: '_Axis', y: '_Axis') -> Tuple[np.ndarray, np.ndarray]:
        """Per sample: px rect distance to the nearest cell in `cells` among the 3x3 around its
        containing cell, and that cell's row*cols + col (inf and -1 if none). The containing cell
        wins ties."""
        rows, cols = cells.shape
        shape = (len(y.pos), len(x.pos))
        dist2 = np.full(shape, np.inf, np.float32)
        owner = np.full(shape, -1, np.int32)
        gap_x = {-1: x.local, 0: np.zeros_like(x.local), 1: x.size - x.local}
        gap_y = {-1: y.local, 0: np.zeros_like(y.local), 1: y.size - y.local}
        for dr, dc in [(0, 0)] + [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]:
            r, c = y.cell + dr, x.cell + dc
            ok_r, ok_c = (r >= 0) & (r < rows), (c >= 0) & (c < cols)
            rc, cc = np.clip(r, 0, rows-1), np.clip(c, 0, cols-1)
            d2 = (gap_y[dr]**2).astype(np.float32)[:, None] + (gap_x[dc]**2).astype(np.float32)[None, :]
            better = cells[np.ix_(rc, cc)] & ok_r[:, None] & ok_c[None, :] & (d2 < dist2)
            dist2[better] = d2[better]
            owner[better] = ((rc*cols)[:, None] + cc[None, :])[better]
        return np.sqrt(dist2), owner

    def _open_centres(self, walls: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        r, c = np.nonzero(~walls)
        return self._y.centres[r], self._x.centres[c]

    def _cleanup(self, values: np.ndarray, core: np.ndarray, centres, kept_open: np.ndarray) -> None:
        """Rock with no wall core becomes open; open space with no open-cell centre and nothing
        kept open by a clamp becomes rock."""
        rock = values >= THRESHOLD
        count, labels = cv2.connectedComponents(rock.astype(np.uint8), connectivity=4)
        anchored = np.zeros(count, bool)
        anchored[labels[core]] = True
        anchored[0] = True  # the open background
        if not anchored.all():
            np.minimum(values, _OPEN, out=values, where=~anchored[labels])

        space = values < THRESHOLD
        count, labels = cv2.connectedComponents(space.astype(np.uint8), connectivity=4)
        reached = np.zeros(count, bool)
        reached[labels[centres]] = True
        reached[labels[kept_open]] = True
        reached[0] = True  # the rock background
        if not reached.all():
            np.maximum(values, _ROCK, out=values, where=~reached[labels])

    def tiles_of(self, changed: np.ndarray) -> np.ndarray:
        """(rows, cols) mask of tiles with a changed sample in their closed rect."""
        s = self.samples
        per_row = changed[:-1].reshape(s.rows, s.per_y, -1).any(axis=1) | changed[s.per_y::s.per_y]
        return per_row[:, :-1].reshape(s.rows, s.cols, s.per_x).any(axis=2) | per_row[:, s.per_x::s.per_x]


def _smoothstep(t: np.ndarray) -> np.ndarray:
    return t*t*(3 - 2*t)


def _lattice(rng: np.random.Generator, size: int) -> np.ndarray:
    """size x size lattice values, drawn in square shells from the corner so each lattice point's
    value does not depend on `size` (noise is identical, in cell units, at every grid size)."""
    values = rng.random(size*size)
    i, j = np.mgrid[0:size, 0:size]
    k = np.maximum(i, j)
    return values[k*k + np.where(i == k, j, k + 1 + i)]
