"""Local line-of-sight geometry. Returned segments never extend behind occluders.

This runs on the game thread for every pilot observation, and fire control
calls it every frame, so the inner loops are written out longhand and each
wall is only tested against the walls that share its direction from the
viewer. tests/visibility_reference.py keeps the plain version these must match.

simplify_outline is the one inexact step: it merges curved rock's short walls,
within SIGHT_TOLERANCE, into the wall set sight is worked out from (see
Maze.sight_segments).
"""
import math

EPS = 1e-7
_TWO_PI = 2 * math.pi
_WIDE = 0.25  # radians of half-width beyond which a wall is checked against every other


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
    (ax, ay), (bx, by) = segment
    dx, dy, fx, fy = bx - ax, by - ay, ax - origin[0], ay - origin[1]
    aa = dx*dx + dy*dy
    if aa < EPS**2:
        return None
    bb = 2 * (fx*dx + fy*dy)
    cc = fx*fx + fy*fy - radius*radius
    margin = -1e-6 * radius*radius
    if cc < margin and aa + bb + cc < margin:
        # Both ends well inside: the whole wall, as the roots below would give
        return 0., 1.
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
    ox, oy = origin
    # Well inside the circle, where _clip would keep the whole of a wall
    inside_sq = (radius * (1 - 1e-6)) ** 2
    for segment in segments:
        (ax, ay), (bx, by) = segment
        if ((ax < left and bx < left) or (ax > right and bx > right) or
                (ay < top and by < top) or (ay > bottom and by > bottom)):
            continue
        dx, dy = bx - ax, by - ay
        if ((ax-ox)**2 + (ay-oy)**2 < inside_sq and (bx-ox)**2 + (by-oy)**2 < inside_sq
                and dx*dx + dy*dy >= EPS**2):
            # As _at(a, d, 0) and _at(a, d, 1) would give
            start, end = (ax + dx * 0., ay + dy * 0.), (ax + dx * 1., ay + dy * 1.)
        else:
            clip = _clip(origin, segment, radius)
            if not clip:
                continue
            lo, hi = clip
            start, end = (ax + dx * lo, ay + dy * lo), (ax + dx * hi, ay + dy * hi)
        ends = (start, end) if start <= end else (end, start)
        key = (round(ends[0][0], 7), round(ends[0][1], 7), round(ends[1][0], 7), round(ends[1][1], 7))
        result[key] = ends
    # Maze conversion emits separate edges for every wall cell. Coalesce
    # contiguous collinear edges before visibility work; their union is exact.
    groups, slanted = {}, {}
    for key, (a,b) in result.items():
        if abs(a[0]-b[0]) < EPS:
            groups.setdefault(('v',round(a[0],7)),[]).append((a[1],b[1]))
        elif abs(a[1]-b[1]) < EPS:
            groups.setdefault(('h',round(a[1],7)),[]).append((a[0],b[0]))
        else:
            slanted[key] = (a,b)
    diagonal = list(slanted.values())
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


SIGHT_TOLERANCE = 2.0  # Pixels a merged wall may stray from the corners it cuts off


def simplify_outline(segments, tolerance=SIGHT_TOLERANCE):
    """The walls to see by: segments with each run of slanted walls meeting end to end (curved
    rock's outline) replaced by fewer, longer walls that stay within `tolerance` of every corner
    they cut off. Sight costs grow with the number of walls, and curved rock has many short ones.
    Walls along the axes, and walls not in such a chain, are kept as they are."""
    kept, at, slanted = [], {}, []
    for segment in segments:
        (ax, ay), (bx, by) = a, b = segment
        if abs(ax - bx) < EPS or abs(ay - by) < EPS:
            kept.append((a, b))
            continue
        index = len(slanted)
        slanted.append((a, b))
        at.setdefault(a, []).append(index)
        at.setdefault(b, []).append(index)
    done = [False] * len(slanted)
    # Walk each chain from a free end or a fork, then whatever is left: closed loops
    for corner in [corner for corner, walls in at.items() if len(walls) != 2] + list(at):
        for index in at[corner]:
            if done[index]:
                continue
            points, here = [corner], corner
            while not done[index]:
                done[index] = True
                a, b = slanted[index]
                here = b if a == here else a
                points.append(here)
                walls = at[here]
                if len(walls) != 2:
                    break
                index = walls[0] if walls[1] == index else walls[1]
            _simplify(points, tolerance, kept)
    return kept


def _simplify(points, tolerance, out):
    """Append to out the walls of a polyline, each reaching as far along it as it can while every
    corner it skips stays within tolerance of its line, and no further from its start than its end."""
    count = len(points)
    i = 0
    while i < count - 1:
        ax, ay = points[i]
        # The directions a wall from points[i] may take and keep every skipped corner in tolerance
        reference = math.atan2(points[i + 1][1] - ay, points[i + 1][0] - ax)
        lo, hi, furthest = -math.pi, math.pi, 0.0
        j = i + 1
        while True:
            px, py = points[j][0] - ax, points[j][1] - ay
            distance = math.hypot(px, py)
            if distance > furthest:
                furthest = distance
            if distance > tolerance:
                angle = (math.atan2(py, px) - reference + math.pi) % _TWO_PI - math.pi
                spread = math.asin(tolerance / distance)
                lo, hi = max(lo, angle - spread), min(hi, angle + spread)
            if j + 1 >= count:
                break
            qx, qy = points[j + 1][0] - ax, points[j + 1][1] - ay
            reach = math.hypot(qx, qy)
            angle = (math.atan2(qy, qx) - reference + math.pi) % _TWO_PI - math.pi
            if reach < furthest or not lo <= angle <= hi:
                break
            j += 1
        out.append((points[i], points[j]))
        i = j


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
    ox, oy = origin
    # Each wall's arc of directions from the viewer (see _bearing_span), and its nearest and
    # furthest distance, worked out longhand
    spans, nearest, furthest = [], [], []
    for (ax, ay), (bx, by) in walls:
        ax, ay, bx, by = ax - ox, ay - oy, bx - ox, by - oy
        if (abs(ax) < EPS and abs(ay) < EPS) or (abs(bx) < EPS and abs(by) < EPS):
            spans.append(None)
        else:
            start = math.atan2(ay, ax)
            sweep = (math.atan2(by, bx) - start + math.pi) % _TWO_PI - math.pi
            spans.append(None if abs(sweep) > math.pi - 1e-6 else (start + sweep / 2, abs(sweep) / 2))
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        t = 0.0 if length_sq <= 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
        nearest.append(math.hypot(ax + dx * t, ay + dy * t))
        furthest.append(max(math.hypot(ax, ay), math.hypot(bx, by)))
    # A wall can only hide, cut or cross another if the two lie in overlapping
    # directions from the viewer, so each is tested against just those. A wall
    # whose arc only touches this one's, such as the next wall along a chain of
    # rock, can do none of that either. Nor can a wall wholly further away than
    # this one's far end: dropping it removes only cuts where nothing changes.
    candidates = _span_window(spans)
    pi, two_pi = math.pi, _TWO_PI
    everyone = range(len(walls))
    result = []
    append = result.append
    for index, ((a, b), span) in enumerate(zip(walls, spans)):
        beyond = furthest[index] * (1 + 1e-9) + 1e-6
        if span is None:
            near = [walls[i] for i in everyone if nearest[i] <= beyond]
        else:
            centre, half = span
            reach = half + _TOUCH
            near = []
            for i in candidates(index):
                if nearest[i] <= beyond:
                    other = spans[i]
                    if other is None or abs((other[0] - centre + pi) % two_pi - pi) < reach + other[1]:
                        near.append(walls[i])
        dx, dy = b[0] - a[0], b[1] - a[1]
        for lo, hi in _merge(_intervals(origin, (a, b), near, radius)):
            append(((a[0] + dx * lo, a[1] + dy * lo), (a[0] + dx * hi, a[1] + dy * hi)))
    return result


# Radians by which two walls' arcs must overlap for one to matter to the other: far more than
# rounding in atan2, far less than any real overlap
_TOUCH = -1e-9


def _span_window(spans):
    """candidates(i): the indices of the walls whose direction could overlap wall i's.

    A superset of the walls the exact test keeps: every wall without a span, every wide one, and the
    narrow walls sharing a bearing bin with wall i, each narrow wall being filed in every bin its
    arc (plus a margin) touches. With many short walls (curved rock) this avoids testing every pair."""
    everyone = range(len(spans))
    if len(spans) < 24:
        return lambda index: everyone
    # Walls without a span, or wide ones (often the nearest), are candidates for everyone
    always = [i for i, span in enumerate(spans) if span is None or span[1] > _WIDE]
    # About two walls to a bin
    count = 16
    while count < 2 * len(spans) and count < 1024:
        count *= 2
    width = _TWO_PI / count
    bins = [[] for _ in range(count)]
    covers = [None] * len(spans)
    for i, span in enumerate(spans):
        if span is None or span[1] > _WIDE:
            continue
        centre, half = span
        lo = int((centre - half - 1e-5) // width)
        hi = int((centre + half + 1e-5) // width)
        covers[i] = (lo, hi)
        for k in range(lo, hi + 1):
            bins[k % count].append(i)

    def candidates(index):
        cover = covers[index]
        if cover is None:
            return everyone
        lo, hi = cover
        if lo == hi:
            found = bins[lo % count]
            return always + found if always else found
        found = set(always)
        for k in range(lo, hi + 1):
            found.update(bins[k % count])
        return found
    return candidates
