"""The original, unoptimised line-of-sight code, kept as an oracle for tests.

hunter.visibility was rewritten for speed; its results must match this exactly.
"""
import math

EPS = 1e-7


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
    d = _sub(point, origin)
    length_sq = d[0]**2 + d[1]**2
    if length_sq > radius**2 + EPS:
        return False
    if length_sq < EPS**2:
        return True
    for a, b in segments:
        e = _sub(b, a)
        hit = _intersection(origin, d, a, e)
        if hit:
            t, u = hit
            if EPS < t < 1 - EPS and -EPS <= u <= 1 + EPS:
                return False
        elif abs(_cross(_sub(a, origin), d)) < EPS:
            ts = [((p[0]-origin[0])*d[0] + (p[1]-origin[1])*d[1]) / length_sq
                  for p in (a,b)]
            if max(min(ts), EPS) < min(max(ts), 1-EPS):
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
    for segment in segments:
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
    a, b = segment
    d = _sub(b, a)
    cuts = {clip[0], clip[1]}
    for c, e in walls:
        for endpoint in (c, e):
            hit = _intersection(a, d, origin, _sub(endpoint, origin))
            if hit and clip[0] < hit[0] < clip[1] and hit[1] >= 0:
                cuts.add(hit[0])
        hit = _intersection(a, d, c, _sub(e, c))
        if hit and clip[0] < hit[0] < clip[1] and 0 <= hit[1] <= 1:
            cuts.add(hit[0])
        # Collinear overlap endpoints also change whether an edge is blocked.
        if abs(_cross(d, _sub(c, a))) < EPS and abs(_cross(d, _sub(e, a))) < EPS:
            axis = 0 if abs(d[0]) > abs(d[1]) else 1
            for point in (c, e):
                t = (point[axis] - a[axis]) / d[axis]
                if clip[0] < t < clip[1]:
                    cuts.add(t)
    cuts = sorted(cuts)
    result = []
    for lo, hi in zip(cuts, cuts[1:]):
        if hi-lo <= EPS:
            continue
        mid = _at(a, d, (lo+hi)/2)
        if visible_point(origin, mid, walls, radius):
            result.append((lo, hi))
    return result


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
    result = []
    for a, b in walls:
        for lo, hi in _merge(_intervals(origin, (a,b), walls, radius)):
            result.append((_at(a, _sub(b,a), lo), _at(a, _sub(b,a), hi)))
    return result
