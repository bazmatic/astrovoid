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


def free_space(field, radius: float) -> np.ndarray:
    """Samples with no rock sample closer than `radius` px (brute force over offsets)."""
    s = field.samples
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


def outline(field) -> np.ndarray:
    """The field's traced outline as (n, 4) segments x0, y0, x1, y1 (as CaveShape traces it), with
    every steel cell's rect edges added (CaveShape draws steel as square faces)."""
    from maze.cave_contour import tile_polylines
    s = field.samples
    out = []
    for r in range(s.rows):
        for c in range(s.cols):
            for line in tile_polylines(field.values, s, (c, r), field.settings.simplifyTolerance):
                out.extend((*a, *b) for a, b in zip(line, line[1:]) if a != b)
    for c, r in field.strong:
        x0, y0 = s.origin[0] + c*s.cell_w, s.origin[1] + r*s.cell_h
        x1, y1 = x0 + s.cell_w, y0 + s.cell_h
        out.extend([(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)])
    return np.array(out, float).reshape(-1, 4)


def _distance_to(segments: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """(len(ys), len(xs)) px distance from each grid point to the nearest segment (inf if none)."""
    if not len(segments):
        return np.full((len(ys), len(xs)), np.inf)
    px, py = xs[None, :, None], ys[:, None, None]
    ax, ay = segments[:, 0], segments[:, 1]
    dx, dy = segments[:, 2] - ax, segments[:, 3] - ay
    t = np.clip(((px-ax)*dx + (py-ay)*dy) / np.maximum(dx*dx + dy*dy, 1e-12), 0, 1)
    return np.hypot(px - (ax + t*dx), py - (ay + t*dy)).min(axis=2)


def corridor_clearance_violations(field, segments=None, radius: Optional[float] = None, step: float = 1.0
                                  ) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Adjacent open cells whose centres a disc of `radius` px (required_clearance() by default)
    cannot travel between, staying inside the two cells, measured against the real outline.

    `segments`: anything with .start and .end (a maze's walls), or an (n, 4) array; the field's own
    traced outline by default. The disc's centre moves on a `step` px grid. A pair is passed
    without measuring when the samples alone show room for the radius plus two sample spacings and
    the simplification tolerance (the outline lies within a sample of a rock sample)."""
    s = field.samples
    radius = field.required_clearance() if radius is None else radius
    if segments is None:
        segments = outline(field)
    elif not isinstance(segments, np.ndarray):
        segments = np.array([(w.start[0], w.start[1], w.end[0], w.end[1]) for w in segments], float).reshape(-1, 4)
    lo_x, hi_x = np.minimum(segments[:, 0], segments[:, 2]), np.maximum(segments[:, 0], segments[:, 2])
    lo_y, hi_y = np.minimum(segments[:, 1], segments[:, 3]), np.maximum(segments[:, 1], segments[:, 3])
    sure = free_space(field, radius + 2*max(s.h_x, s.h_y) + field.settings.simplifyTolerance)
    bad = []
    for a, b in _open_pairs(field):
        (ax, ay), (bx, by) = _centre(field, a), _centre(field, b)
        if field.is_rock(ax, ay) or field.is_rock(bx, by):
            bad.append((a, b))
            continue
        ia, ja = _index(field, ax, ay)
        ib, jb = _index(field, bx, by)
        if sure[ia:ib+1, ja:jb+1].all():
            continue  # the samples alone show room along the straight line
        y0, x0 = a[1]*s.per_y, a[0]*s.per_x
        y1, x1 = (b[1]+1)*s.per_y, (b[0]+1)*s.per_x
        (left, top), (right, bottom) = s.point(y0, x0), s.point(y1, x1)
        near = (hi_x >= left-radius) & (lo_x <= right+radius) & (hi_y >= top-radius) & (lo_y <= bottom+radius)
        # Grid points through both centres
        xs = np.concatenate([np.arange(ax, left-1e-9, -step)[::-1], np.arange(ax+step, right+1e-9, step)])
        ys = np.concatenate([np.arange(ay, top-1e-9, -step)[::-1], np.arange(ay+step, bottom+1e-9, step)])
        pa = (int(np.argmin(abs(ys-ay))), int(np.argmin(abs(xs-ax))))
        pb = (int(np.argmin(abs(ys-by))), int(np.argmin(abs(xs-bx))))
        line_x = xs[pa[1]:pb[1]+1] if pa[0] == pb[0] else xs[pa[1]:pa[1]+1]
        line_y = ys[pa[0]:pb[0]+1] if pa[1] == pb[1] else ys[pa[0]:pa[0]+1]
        if (_distance_to(segments[near], line_x, line_y) >= radius).all():
            continue  # room along the straight line
        room = (_distance_to(segments[near], xs, ys) >= radius).astype(np.uint8)
        _, labels = cv2.connectedComponents(room, connectivity=4)
        if not room[pa] or labels[pa] != labels[pb]:
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


def steel_face_violations(field) -> List[Tuple[int, int]]:
    """(iy, ix) of samples breaking square steel: open samples touching a strong cell, or rock
    samples in open cells within half a cell of a strong cell's rect."""
    s = field.samples
    rows, cols = s.shape
    xs = s.origin[0] + np.arange(cols)*s.h_x
    ys = s.origin[1] + np.arange(rows)*s.h_y
    open_samples = _samples_of_open_cells(field)
    reach = 0.5 * min(s.cell_w, s.cell_h)
    bad = []
    for c, r in field.strong:
        x0, y0 = s.origin[0] + c*s.cell_w, s.origin[1] + r*s.cell_h
        gx = np.maximum(0, np.maximum(x0 - xs, xs - (x0 + s.cell_w)))
        gy = np.maximum(0, np.maximum(y0 - ys, ys - (y0 + s.cell_h)))
        d = np.hypot(gx[None, :], gy[:, None])
        bad.extend(map(tuple, np.argwhere((d <= 1e-6) & ~field.rock)))
        bad.extend(map(tuple, np.argwhere((d <= reach) & open_samples & field.rock)))
    return bad


def watertight_violations(grid, calc, segments) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """(open cell, wall cell) pairs of orthogonal neighbours where the line between their centres
    crosses no wall segment, i.e. a gap in the outline. `calc` is the MazePositionCalculator;
    `segments` anything with .start and .end."""
    from utils.math_utils import line_line_collision
    rows, cols = len(grid), len(grid[0])
    if not segments:
        return [((c, r), (c, r)) for r in range(rows) for c in range(cols) if grid[r][c] == 1]
    ends = np.array([(s.start[0], s.start[1], s.end[0], s.end[1]) for s in segments], float)
    lo_x, hi_x = np.minimum(ends[:, 0], ends[:, 2]), np.maximum(ends[:, 0], ends[:, 2])
    lo_y, hi_y = np.minimum(ends[:, 1], ends[:, 3]), np.maximum(ends[:, 1], ends[:, 3])

    def centre(c, r):
        x, y = calc.grid_to_screen(c, r)
        return (x + 0.5*calc.cell_size_x, y + 0.5*calc.cell_size_y)

    bad = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] != 1:
                continue
            q = centre(c, r)
            for dc, dr in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                oc, orow = c + dc, r + dr
                if not (0 <= oc < cols and 0 <= orow < rows) or grid[orow][oc] == 1:
                    continue
                p = centre(oc, orow)
                near = np.nonzero((hi_x >= min(p[0], q[0])) & (lo_x <= max(p[0], q[0]))
                                  & (hi_y >= min(p[1], q[1])) & (lo_y <= max(p[1], q[1])))[0]
                if not any(line_line_collision(p, q, segments[i].start, segments[i].end) for i in near):
                    bad.append(((oc, orow), (c, r)))
    return bad
