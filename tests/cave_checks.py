"""Anti-goal checks for a CaveField: plain functions, reused on full mazes by later tests.

Each returns a list of violations; an empty list means the check passes. They are written
independently of maze/cave_field.py's own clamps, so they catch a clamp that does not hold.
"""
import math
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np


def _cells(field, wall: bool) -> List[Tuple[int, int]]:
    s = field.samples
    return [(c, r) for r in range(s.rows) for c in range(s.cols) if (field.grid[r][c] == 1) == wall]


def _centre(field, cell) -> Tuple[float, float]:
    s = field.samples
    return (s.origin[0] + (cell[0]+0.5)*s.cell_w, s.origin[1] + (cell[1]+0.5)*s.cell_h)


def _index(field, x: float, y: float) -> Tuple[int, int]:
    fy, fx = field.samples.fractional(x, y)
    return int(round(fy)), int(round(fx))


def _open_pairs(field):
    s = field.samples
    for c, r in _cells(field, wall=False):
        for b in ((c+1, r), (c, r+1)):
            if b[0] < s.cols and b[1] < s.rows and field.grid[b[1]][b[0]] != 1:
                yield (c, r), b


def _samples_of_open_cells(field) -> np.ndarray:
    """True for samples that touch no wall cell (and are not on the outer border)."""
    s = field.samples
    rows, cols = s.shape
    walls = np.ones((s.rows+2, s.cols+2), bool)
    walls[1:-1, 1:-1] = np.asarray(field.grid) == 1
    out = np.ones((rows, cols), bool)
    iy, ix = np.arange(rows), np.arange(cols)
    # Touched cells: the containing one, and the one before it when on a cell border (-1 and
    # rows/cols land on the padding, which counts as wall)
    for ty in (iy // s.per_y, iy // s.per_y - (iy % s.per_y == 0)):
        for tx in (ix // s.per_x, ix // s.per_x - (ix % s.per_x == 0)):
            out &= ~walls[np.ix_(ty+1, tx+1)]
    return out


def free_space(field) -> np.ndarray:
    """Samples with no rock sample closer than required_clearance() px (brute force over offsets)."""
    s = field.samples
    radius = field.required_clearance()
    rock = field.rock
    free = np.ones_like(rock)
    ky, kx = int(math.ceil(radius / s.h_y)), int(math.ceil(radius / s.h_x))
    padded = np.pad(rock, ((ky, ky), (kx, kx)), constant_values=False)
    rows, cols = rock.shape
    for dy in range(-ky, ky+1):
        for dx in range(-kx, kx+1):
            if (dy*s.h_y)**2 + (dx*s.h_x)**2 < radius**2:
                free &= ~padded[ky+dy:ky+dy+rows, kx+dx:kx+dx+cols]
    return free


def corridor_clearance_violations(field) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Adjacent open cells whose centres a disc of required_clearance() cannot travel between,
    staying inside the two cells."""
    s = field.samples
    free = free_space(field)
    bad = []
    for a, b in _open_pairs(field):
        y0, x0 = a[1]*s.per_y, a[0]*s.per_x
        y1, x1 = (b[1]+1)*s.per_y, (b[0]+1)*s.per_x
        crop = free[y0:y1+1, x0:x1+1].astype(np.uint8)
        _, labels = cv2.connectedComponents(crop, connectivity=4)
        ia, ja = _index(field, *_centre(field, a))
        ib, jb = _index(field, *_centre(field, b))
        la, lb = labels[ia-y0, ja-x0], labels[ib-y0, jb-x0]
        if not crop[ia-y0, ja-x0] or la != lb:
            bad.append((a, b))
    return bad


def centre_and_link_violations(field, positions: int = 10) -> List[Tuple[float, float]]:
    """Points that are rock: open-cell centres, and evenly spaced points on adjacent open links."""
    bad = [p for p in (_centre(field, cell) for cell in _cells(field, wall=False)) if field.is_rock(*p)]
    for a, b in _open_pairs(field):
        (ax, ay), (bx, by) = _centre(field, a), _centre(field, b)
        for i in range(positions):
            t = i / (positions-1)
            p = (ax + t*(bx-ax), ay + t*(by-ay))
            if field.is_rock(*p):
                bad.append(p)
    return bad


def wall_core_violations(field) -> List[Tuple[float, float]]:
    """Points that are open: wall-cell centres, and every sample-spaced point on the line between
    the centres of orthogonally adjacent wall cells."""
    s = field.samples
    bad = []
    for cell in _cells(field, wall=True):
        ax, ay = _centre(field, cell)
        if not field.is_rock(ax, ay):
            bad.append((ax, ay))
        c, r = cell
        for b, steps in (((c+1, r), s.per_x), ((c, r+1), s.per_y)):
            if b[0] < s.cols and b[1] < s.rows and field.grid[b[1]][b[0]] == 1:
                bx, by = _centre(field, b)
                for i in range(1, steps+1):
                    p = (ax + i/steps*(bx-ax), ay + i/steps*(by-ay))
                    if not field.is_rock(*p):
                        bad.append(p)
    return bad


def rock_island_violations(field) -> List[int]:
    """Labels of rock components that contain no wall-cell centre (floating rock)."""
    count, labels = cv2.connectedComponents(field.rock.astype(np.uint8), connectivity=4)
    anchored = {int(labels[_index(field, *_centre(field, cell))]) for cell in _cells(field, wall=True)}
    return [label for label in range(1, count) if label not in anchored]


def gate_swing_violations(field, keep_clear: Optional[Sequence[Tuple[Tuple[float, float], float]]] = None
                          ) -> List[Tuple[int, int]]:
    """(iy, ix) of rock samples in open cells inside a gate's swing circle."""
    s = field.samples
    open_samples = _samples_of_open_cells(field)
    rows, cols = s.shape
    xs = s.origin[0] + np.arange(cols)*s.h_x
    ys = s.origin[1] + np.arange(rows)*s.h_y
    bad = []
    for (cx, cy), radius in (field.keep_clear if keep_clear is None else keep_clear):
        inside = (xs[None, :]-cx)**2 + (ys[:, None]-cy)**2 <= radius**2
        bad.extend(map(tuple, np.argwhere(inside & open_samples & field.rock)))
    return bad
