"""Incoming-fire geometry shared by the Flocker observation and the training reward."""
import math

HORIZON = 60.          # frames ahead a shot's approach is considered
DANGER_MARGIN = 4.     # pixels beyond both radii that still count as about to be hit


def hostile_shots(enc):
    """Live shots fired by anyone but the Flocker team."""
    return [s for s in enc.world.projectiles if s.active and not s.is_enemy]


def approach(c, shot):
    """Frames until `shot` is closest to `c`, and how near it passes; None when it is moving away or out of reach."""
    rx, ry = shot.x-c.x, shot.y-c.y
    ux, uy = shot.vx-c.vx, shot.vy-c.vy
    speed2 = ux*ux+uy*uy
    if speed2 < 1e-9:
        return None
    t = -(rx*ux+ry*uy)/speed2
    if t < 0 or t > min(HORIZON, shot.lifetime):
        return None
    return t, math.hypot(rx+ux*t, ry+uy*t)


def danger(c, shot):
    """True when the shot will pass within hitting distance of `c` inside the horizon."""
    found = approach(c, shot)
    return found is not None and found[1] <= c.radius+getattr(shot, 'radius', 0.)+DANGER_MARGIN


def threats(enc, c, count, reach=550.):
    """The `count` most urgent incoming shots as (shot, frames, miss): those that will hit first, then the rest by time."""
    found = []
    for s in hostile_shots(enc):
        if math.hypot(s.x-c.x, s.y-c.y) > reach:
            continue
        a = approach(c, s)
        if a is not None:
            found.append((s, *a))
    found.sort(key=lambda f: (f[2] > c.radius+getattr(f[0], 'radius', 0.)+DANGER_MARGIN, f[1]))
    return found[:count]
