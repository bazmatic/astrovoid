"""Local line-of-sight geometry. Returned segments never extend behind occluders.

This runs on the game thread for every pilot observation, and fire control
calls it every frame, so the inner loops are written out longhand and each
wall is only tested against the walls that share its direction from the
viewer. tests/visibility_reference.py keeps the plain version these must match.
"""
import math

EPS = 1e-7
_TWO_PI = 2 * math.pi


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _at(a, d, t):
    return a[0] + d[0] * t, a[1] + d[1] * t


def _intersection(a, d, b, e):
    denom = _cross(d, e)
    if abs(denom) < EPS:
        return None
    offset = _sub(b, a)
    return _cross(offset, e) / denom, _cross(offset, d) / denom


def visible_point(origin, point, segments, radius):
    ox, oy = origin
    dx, dy = point[0] - ox, point[1] - oy
    length_sq = dx**2 + dy**2
    if length_sq > radius**2 + EPS:
        return False
    if length_sq < EPS**2:
        return True
    near_end = 1 - EPS
    past_end = 1 + EPS
    for (ax, ay), (bx, by) in segments:
        ex, ey = bx - ax, by - ay
        fx, fy = ax - ox, ay - oy
        denom = dx * ey - dy * ex
        if abs(denom) >= EPS:
            t = (fx * ey - fy * ex) / denom
            if EPS < t < near_end and -EPS <= (fx * dy - fy * dx) / denom <= past_end:
                return False
        elif abs(fx * dy - fy * dx) < EPS:
            # The wall lies along the line of sight: it hides the point if it overlaps it.
            ta = ((ax-ox)*dx + (ay-oy)*dy) / length_sq
            tb = ((bx-ox)*dx + (by-oy)*dy) / length_sq
            if max(min(ta, tb), EPS) < min(max(ta, tb), near_end):
                return False
    return True


def _clip(origin, segment, radius):
    a, b = segment
    d, f = _sub(b, a), _sub(a, origin)
    aa = d[0]**2 + d[1]**2
    if aa < EPS**2:
        return None
    bb = 2 * (f[0]*d[0] + f[1]*d[1])
    cc = f[0]**2 + f[1]**2 - radius**2
    disc = bb*bb - 4*aa*cc
    if disc < 0:
        return None
    root = math.sqrt(disc)
    lo, hi = max(0., (-bb-root)/(2*aa)), min(1., (-bb+root)/(2*aa))
    return (lo, hi) if hi-lo > EPS else None


def local_segments(origin, segments, radius):
    """Clip and deduplicate local occluders, including reversed duplicate edges."""
    result = {}
    # Most walls are nowhere near: throw those out before any real geometry.
    left, right = origin[0] - radius - 1, origin[0] + radius + 1
    top, bottom = origin[1] - radius - 1, origin[1] + radius + 1
    for segment in segments:
        (ax, ay), (bx, by) = segment
        if ((ax < left and bx < left) or (ax > right and bx > right) or
                (ay < top and by < top) or (ay > bottom and by > bottom)):
            continue
        clip = _clip(origin, segment, radius)
        if clip:
            a, b = segment
            d = _sub(b, a)
            ends = tuple(sorted((_at(a, d, clip[0]), _at(a, d, clip[1]))))
            key = tuple(round(v, 7) for p in ends for v in p)
            result[key] = ends
    # Maze conversion emits separate edges for every wall cell. Coalesce
    # contiguous collinear edges before visibility work; their union is exact.
    groups, diagonal = {}, []
    for a,b in result.values():
        if abs(a[0]-b[0]) < EPS:
            groups.setdefault(('v',round(a[0],7)),[]).append((a[1],b[1]))
        elif abs(a[1]-b[1]) < EPS:
            groups.setdefault(('h',round(a[1],7)),[]).append((a[0],b[0]))
        else:
            diagonal.append((a,b))
    for (axis,fixed),intervals in groups.items():
        merged = []
        for lo,hi in sorted(intervals):
            if merged and lo <= merged[-1][1]+EPS:
                merged[-1] = (merged[-1][0],max(hi,merged[-1][1]))
            else:
                merged.append((lo,hi))
        for lo,hi in merged:
            diagonal.append(((fixed,lo),(fixed,hi)) if axis == 'v' else ((lo,fixed),(hi,fixed)))
    return diagonal


def _intervals(origin, segment, walls, radius):
    """Split where visibility can change: range, endpoint rays and crossings."""
    clip = _clip(origin, segment, radius)
    if not clip:
        return []
    lo_clip, hi_clip = clip
    a, b = segment
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    ox, oy = origin
    # From the segment's start to the viewer
    vx, vy = ox - ax, oy - ay
    v_cross_d = vx * dy - vy * dx
    cuts = {lo_clip, hi_clip}
    add = cuts.add
    for (cx, cy), (ex, ey) in walls:
        # Rays from the viewer through each end of the wall
        for px, py in ((cx, cy), (ex, ey)):
            rx, ry = px - ox, py - oy
            denom = dx * ry - dy * rx
            if abs(denom) >= EPS:
                t = (vx * ry - vy * rx) / denom
                if lo_clip < t < hi_clip and v_cross_d / denom >= 0:
                    add(t)
        # Where the wall crosses the segment
        wx, wy = ex - cx, ey - cy
        fx, fy = cx - ax, cy - ay
        denom = dx * wy - dy * wx
        if abs(denom) >= EPS:
            t = (fx * wy - fy * wx) / denom
            if lo_clip < t < hi_clip and 0 <= (fx * dy - fy * dx) / denom <= 1:
                add(t)
        # Collinear overlap endpoints also change whether an edge is blocked.
        if abs(dx * fy - dy * fx) < EPS and abs(dx * (ey - ay) - dy * (ex - ax)) < EPS:
            if abs(dx) > abs(dy):
                ts = ((cx - ax) / dx, (ex - ax) / dx)
            else:
                ts = ((cy - ay) / dy, (ey - ay) / dy)
            for t in ts:
                if lo_clip < t < hi_clip:
                    add(t)
    cuts = sorted(cuts)
    result = []
    for lo, hi in zip(cuts, cuts[1:]):
        if hi-lo <= EPS:
            continue
        mid = _at(a, (dx, dy), (lo+hi)/2)
        if visible_point(origin, mid, walls, radius):
            result.append((lo, hi))
    return result


def _bearing_span(origin, segment):
    """The arc of directions a segment covers as seen from origin: (centre, half-width).

    None means every direction, for a segment that runs through the viewer.
    """
    (ax, ay), (bx, by) = segment
    ax, ay, bx, by = ax - origin[0], ay - origin[1], bx - origin[0], by - origin[1]
    if (abs(ax) < EPS and abs(ay) < EPS) or (abs(bx) < EPS and abs(by) < EPS):
        return None
    start = math.atan2(ay, ax)
    sweep = (math.atan2(by, bx) - start + math.pi) % _TWO_PI - math.pi
    if abs(sweep) > math.pi - 1e-6:
        return None
    return start + sweep / 2, abs(sweep) / 2


def _merge(intervals):
    merged = []
    for lo, hi in intervals:
        if merged and abs(merged[-1][1]-lo) < EPS:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))
    return merged


def visible_wall_portions(origin, segments, radius):
    walls = local_segments(origin, segments, radius)
    # A wall can only hide, cut or cross another if the two lie in overlapping
    # directions from the viewer, so each is tested against just those.
    spans = [_bearing_span(origin, wall) for wall in walls]
    result = []
    for (a, b), span in zip(walls, spans):
        if span is None:
            near = walls
        else:
            centre, half = span
            reach = half + 1e-6
            near = [wall for wall, other in zip(walls, spans)
                    if other is None or
                    abs((other[0] - centre + math.pi) % _TWO_PI - math.pi) <= reach + other[1]]
        for lo, hi in _merge(_intervals(origin, (a,b), near, radius)):
            result.append((_at(a, _sub(b,a), lo), _at(a, _sub(b,a), hi)))
    return result
