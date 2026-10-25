"""Trace the cave field's rock outline, one maze tile at a time.

Marching squares on the sample grid at THRESHOLD. Segments run with rock on the right of travel
(clockwise around rock in screen coordinates, y down), like GridToWallsConverter.face. Crossing
points are interpolated along a sample edge in a fixed direction, so the two tiles sharing an
edge compute identical points.
"""
from typing import Dict, List, Tuple

import numpy as np

from maze.cave_field import THRESHOLD, Cell, SampleGrid

Point = Tuple[float, float]

# Square edges clockwise on screen: top, right, bottom, left
_TOP, _RIGHT, _BOTTOM, _LEFT = range(4)


def tile_polylines(values: np.ndarray, samples: SampleGrid, tile: Cell,
                   tolerance: float) -> List[List[Point]]:
    """The rock outline inside `tile`, in px, simplified to `tolerance` px.

    Each polyline has rock on its right. It either starts and ends on the tile border, or is
    closed (first point repeated as the last)."""
    col, row = tile
    y0, x0 = row*samples.per_y, col*samples.per_x
    window = values[y0:y0+samples.per_y+1, x0:x0+samples.per_x+1] >= THRESHOLD
    tl, tr = window[:-1, :-1], window[:-1, 1:]
    bl, br = window[1:, :-1], window[1:, 1:]
    case = tl*1 + tr*2 + br*4 + bl*8
    active = np.argwhere((case != 0) & (case != 15))

    segments: Dict[tuple, Tuple[tuple, Point, Point]] = {}  # start edge id -> (end id, start, end)
    for sy, sx in active:
        iy, ix = y0 + int(sy), x0 + int(sx)
        for start, end in _square_segments(values, samples, iy, ix):
            segments[start[0]] = (end[0], start[1], end[1])
    return [_simplify(line, tolerance) for line in _chain(segments)]


def _square_segments(values, samples, iy, ix):
    """Segments of one square as ((edge id, point), (edge id, point)) pairs, rock on the right."""
    v = (values[iy, ix], values[iy, ix+1], values[iy+1, ix+1], values[iy+1, ix])  # TL TR BR BL
    inside = [x >= THRESHOLD for x in v]
    # Edge e joins corner e to corner (e+1) % 4. Crossings in clockwise order: (edge, rock->open?)
    crossings = [(e, inside[e]) for e in range(4) if inside[e] != inside[(e+1) % 4]]
    if not crossings:
        return []
    if len(crossings) == 4:
        connected = sum(v) / 4 >= THRESHOLD  # saddle: the centre average decides
    else:
        connected = True
    out = []
    for i, (edge, leaving) in enumerate(crossings):
        if not leaving:
            continue
        other = crossings[(i+1) % len(crossings)] if connected else crossings[i-1]
        out.append((_crossing(values, samples, iy, ix, edge), _crossing(values, samples, iy, ix, other[0])))
    return out


def _crossing(values, samples, iy, ix, edge):
    """(edge id, px point) where the field crosses THRESHOLD on a square's edge. The id names the
    sample edge, so a neighbouring square sees the same crossing."""
    if edge == _TOP:
        a, b, horizontal = (iy, ix), (iy, ix+1), True
    elif edge == _BOTTOM:
        a, b, horizontal = (iy+1, ix), (iy+1, ix+1), True
    elif edge == _LEFT:
        a, b, horizontal = (iy, ix), (iy+1, ix), False
    else:
        a, b, horizontal = (iy, ix+1), (iy+1, ix+1), False
    va, vb = float(values[a]), float(values[b])
    t = (THRESHOLD - va) / (vb - va)
    px, py = samples.point(*a)
    point = (px + t*samples.h_x, py) if horizontal else (px, py + t*samples.h_y)
    return ((horizontal, a), point)


def _chain(segments: Dict[tuple, Tuple[tuple, Point, Point]]) -> List[List[Point]]:
    """Join segments end to start. Open chains begin where no segment arrives (the tile border)."""
    arrivals = {end for end, _, _ in segments.values()}
    lines = []
    used = set()

    def follow(first):
        key, line = first, []
        while key in segments and key not in used:
            used.add(key)
            end, start, stop = segments[key]
            if not line:
                line.append(start)
            line.append(stop)
            key = end
        return line

    for key in [k for k in segments if k not in arrivals]:
        lines.append(follow(key))
    for key in list(segments):
        if key not in used:
            lines.append(follow(key))  # closed loop: ends where it began
    return lines


def _simplify(line: List[Point], tolerance: float) -> List[Point]:
    if tolerance <= 0 or len(line) <= 2:
        return line
    pts = np.asarray(line)
    if line[0] == line[-1]:
        # A loop: split at the point farthest from its start so both halves have fixed ends
        far = int(np.argmax(np.hypot(*(pts - pts[0]).T)))
        keep = _rdp(pts[:far+1], tolerance) + _rdp(pts[far:], tolerance)[1:]
    else:
        keep = _rdp(pts, tolerance)
    return keep


def _rdp(pts: np.ndarray, tolerance: float) -> List[Point]:
    """Ramer-Douglas-Peucker; the end points always stay. Returns tuples of the original floats."""
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts)-1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        d = pts[b] - pts[a]
        rel = pts[a+1:b] - pts[a]
        length = np.hypot(*d)
        if length == 0:
            dist = np.hypot(rel[:, 0], rel[:, 1])
        else:
            dist = np.abs(d[0]*rel[:, 1] - d[1]*rel[:, 0]) / length
        i = int(np.argmax(dist))
        if dist[i] > tolerance:
            m = a + 1 + i
            keep[m] = True
            stack += [(a, m), (m, b)]
    return [(float(x), float(y)) for x, y in pts[keep]]
