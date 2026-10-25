"""The cave field: a smooth rock/open scalar field over the maze cells.

Cell occupancy is blurred and roughened with value noise, then clamped so the anti-goals hold:
wall cores stay rock, open-cell centres, links and gate swings stay open, steel stays square,
no floating rock or sealed pockets, and every corridor keeps the clearance a creature needs.
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
    """Per-axis sample bookkeeping (x or y), so 2D work is broadcasting of 1D arrays."""

    def __init__(self, count: int, per: int, cells: int, size: float, start: float):
        index = np.arange(count)
        self.pos = start + index * (size / per)  # px
        self.cell = np.minimum(index // per, cells-1)  # containing cell, clamped
        self.local = self.pos - (start + self.cell*size)  # px from the containing cell's start
        self.cells, self.size, self.start = cells, size, start
        self.centres = np.arange(cells)*per + per//2  # sample index of each cell centre
        border = index[index % per == 0]
        # The cells a sample touches, as (cell per sample, sample indices) runs: every sample's
        # own cell, then the previous cell for samples on a cell border. A cell may be -1 or
        # `cells`, outside the grid.
        self.touched_runs = ((index // per, index), (border // per - 1, border))


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

    def required_clearance(self) -> float:
        s = self.samples
        return min(self.settings.clearanceRadius, 0.5*min(s.cell_w, s.cell_h) - 1.0)

    # Building

    def rebuild(self) -> np.ndarray:
        """Recompute after `grid` changed; returns a (rows, cols) mask of tiles whose rock changed."""
        s, cfg = self.samples, self.settings
        walls = np.asarray(self.grid) == 1
        steel = np.zeros_like(walls)
        for c, r in self.strong:
            steel[r, c] = True

        wall_sample = self._touches(walls, outside=True)  # occupancy
        open_sample = ~wall_sample
        values = self._blur(wall_sample.astype(np.float32)) + self._noise

        # Wall cores: the skeleton through wall centres, linked to wall neighbours and the outside
        core = wall_sample & self._near_skeleton(walls, True, cfg.wallCoreCells*self._unit)
        np.maximum(values, _ROCK, out=values, where=core)

        # Open space the clamps promise (gate swings, steel faces) must survive the hole cleanup
        kept_open = np.zeros(s.shape, bool)
        for (cx, cy), radius in self.keep_clear:
            kept_open |= ((self._x.pos[None, :]-cx)**2 + (self._y.pos[:, None]-cy)**2) <= radius**2
        kept_open &= open_sample
        np.minimum(values, _OPEN, out=values, where=kept_open)

        links = self._near_skeleton(~walls, False, cfg.linkClearance)
        np.minimum(values, _OPEN, out=values, where=links & open_sample)

        if steel.any():
            values[self._touches(steel, outside=False)] = 1.0
            near_steel, _ = self._nearest_cell(steel)
            steel_face = open_sample & (near_steel <= 0.5*min(s.cell_w, s.cell_h))
            np.minimum(values, _OPEN, out=values, where=steel_face)
            kept_open |= steel_face

        centres = self._open_centres(walls)
        self._cleanup(values, core, centres, kept_open)
        self._clear_corridors(values, walls, open_sample)
        self._cleanup(values, core, centres, kept_open)

        rock = values >= THRESHOLD
        changed = np.ones_like(rock) if self.rock is None else rock != self.rock
        self.values, self.rock = values, rock
        self.owner = self._nearest_cell(walls & ~steel)[1]
        return self._tiles(changed)

    def _touches(self, cells: np.ndarray, outside: bool) -> np.ndarray:
        """Per sample: does it touch (lie in or on the border of) any cell in `cells`?"""
        padded = np.pad(cells, 1, constant_values=outside)
        out = np.zeros(self.samples.shape, bool)
        for ty, rows in self._y.touched_runs:
            for tx, cols in self._x.touched_runs:
                out[np.ix_(rows, cols)] |= padded[np.ix_(ty+1, tx+1)]
        return out

    def _blur(self, occupancy: np.ndarray) -> np.ndarray:
        sigma = self.settings.blurCells * self._unit
        kernels, pads = [], []
        for h in (self.samples.h_x, self.samples.h_y):
            sd = sigma / h
            radius = max(1, math.ceil(3*sd))
            k = np.exp(-0.5*(np.arange(-radius, radius+1)/sd)**2)
            kernels.append((k/k.sum()).astype(np.float32))
            pads.append(radius)
        px, py = pads
        padded = np.pad(occupancy, ((py, py), (px, px)), constant_values=1.0)  # outside is rock
        blurred = cv2.sepFilter2D(padded, cv2.CV_32F, kernels[0], kernels[1], borderType=cv2.BORDER_REPLICATE)
        return blurred[py:-py, px:-px]

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

    def _near_skeleton(self, cells: np.ndarray, outside: bool, reach: float) -> np.ndarray:
        """Per sample: within `reach` px of the skeleton of `cells`? The skeleton is each centre,
        plus lines to the centres of orthogonal neighbours in `cells` (`outside` says whether
        the virtual cells beyond the grid count). Only cells the sample touches are considered."""
        padded = np.pad(cells, 1, constant_values=outside)
        left, right = padded[1:-1, :-2] & cells, padded[1:-1, 2:] & cells
        up, down = padded[:-2, 1:-1] & cells, padded[2:, 1:-1] & cells
        out = np.zeros(self.samples.shape, bool)
        # The containing cell for every sample; the previous cell only matters on borders
        for ty, rows in self._y.touched_runs:
            dy = (self._y.pos[rows] - (self._y.start + (ty+0.5)*self._y.size))[:, None]
            row = np.clip(ty, 0, self._y.cells-1)
            valid_y = ((ty >= 0) & (ty < self._y.cells))[:, None]
            for tx, cols in self._x.touched_runs:
                dx = (self._x.pos[cols] - (self._x.start + (tx+0.5)*self._x.size))[None, :]
                col = np.clip(tx, 0, self._x.cells-1)
                at = np.ix_(row, col)
                near = (dx*dx + dy*dy <= reach*reach)
                near |= (np.abs(dy) <= reach) & (((dx < 0) & left[at]) | ((dx > 0) & right[at]))
                near |= (np.abs(dx) <= reach) & (((dy < 0) & up[at]) | ((dy > 0) & down[at]))
                near &= cells[at] & valid_y & ((tx >= 0) & (tx < self._x.cells))[None, :]
                out[np.ix_(rows, cols)] |= near
        return out

    def _nearest_cell(self, cells: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Per sample: px rect distance to the nearest cell in `cells` among the 3x3 around its
        containing cell, and that cell's row*cols + col (inf and -1 if none). The containing cell
        wins ties."""
        rows, cols = cells.shape
        x, y = self._x, self._y
        dist2 = np.full(self.samples.shape, np.inf, np.float32)
        owner = np.full(self.samples.shape, -1, np.int32)
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
        np.minimum(values, _OPEN, out=values, where=~anchored[labels])

        space = values < THRESHOLD
        count, labels = cv2.connectedComponents(space.astype(np.uint8), connectivity=4)
        reached = np.zeros(count, bool)
        reached[labels[centres]] = True
        reached[labels[kept_open]] = True
        reached[0] = True  # the rock background
        np.maximum(values, _ROCK, out=values, where=~reached[labels])

    def _clear_corridors(self, values: np.ndarray, walls: np.ndarray, open_sample: np.ndarray) -> None:
        """Clamp a tube between adjacent open cells whose centres a disc of required_clearance()
        cannot travel between, staying inside the two cells."""
        s = self.samples
        radius = self.required_clearance()
        free = self._free_space(values >= THRESHOLD, radius)
        open_cells = ~walls
        x, y = self._x, self._y
        for horizontal in (True, False):
            if horizontal:
                ra, ca = np.nonzero(open_cells[:, :-1] & open_cells[:, 1:])
                blocked = np.cumsum(~free[y.centres, :], axis=1)
                lines, start, end = blocked[ra], x.centres[ca], x.centres[ca] + s.per_x
            else:
                ra, ca = np.nonzero(open_cells[:-1, :] & open_cells[1:, :])
                blocked = np.cumsum(~free[:, x.centres], axis=0).T
                lines, start, end = blocked[ca], y.centres[ra], y.centres[ra] + s.per_y
            # A straight free run between the centres is a path; only the rest need components
            count = lines[np.arange(len(ra)), end] - np.where(start > 0, lines[np.arange(len(ra)), start-1], 0)
            for r, c in zip(ra[count > 0], ca[count > 0]):
                rb, cb = (r, c+1) if horizontal else (r+1, c)
                y0, y1, x0, x1 = r*s.per_y, (rb+1)*s.per_y + 1, c*s.per_x, (cb+1)*s.per_x + 1
                crop = free[y0:y1, x0:x1].astype(np.uint8)
                _, labels = cv2.connectedComponents(crop, connectivity=4)
                la = labels[y.centres[r]-y0, x.centres[c]-x0]
                lb = labels[y.centres[rb]-y0, x.centres[cb]-x0]
                if la and la == lb:
                    continue
                ax, ay = x.pos[x.centres[c]], y.pos[y.centres[r]]
                bx, by = x.pos[x.centres[cb]], y.pos[y.centres[rb]]
                px, py = x.pos[x0:x1][None, :], y.pos[y0:y1][:, None]
                gx = np.maximum(0, np.maximum(ax - px, px - bx))
                gy = np.maximum(0, np.maximum(ay - py, py - by))
                tube = (np.hypot(gx, gy) <= radius) & open_sample[y0:y1, x0:x1]
                window = values[y0:y1, x0:x1]
                np.minimum(window, _OPEN, out=window, where=tube)

    def _free_space(self, rock: np.ndarray, radius: float) -> np.ndarray:
        """Samples with no rock sample closer than `radius` px. The samples are not square, so
        this dilates by an ellipse in sample units rather than thresholding a distance transform."""
        s = self.samples
        ky, kx = math.ceil(radius / s.h_y), math.ceil(radius / s.h_x)
        oy, ox = np.mgrid[-ky:ky+1, -kx:kx+1]
        kernel = (((oy*s.h_y)**2 + (ox*s.h_x)**2) < radius**2).astype(np.uint8)
        return cv2.dilate(rock.astype(np.uint8), kernel) == 0

    def _tiles(self, changed: np.ndarray) -> np.ndarray:
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
