"""Bounded shot shaping from visible geometry at launch, separate from accepted hits."""
import math
from creatures.traits.rooted import wall_between

ACCURACY_WEIGHT = .02
SHOT_COST = .05


def shot_quality(shot, targets, maze):
    """Best predicted hull proximity over the remaining lifetime, in [0, 1].

    Linear target motion rewards leading a shot. Predictions are not hit events;
    blocked, unreachable, behind and unseen targets provide no shaping signal.
    """
    best = 0.
    for target in targets:
        if target is None or not target.active or getattr(target, 'observer', False):
            continue
        if getattr(target, 'is_shield_active', lambda: False)():
            continue
        rx, ry = target.x-shot.x, target.y-shot.y
        if math.hypot(rx, ry) > getattr(shot,'aim_range',550) or wall_between(shot.get_pos(),target.get_pos(),maze):
            continue
        vx, vy = shot.vx-target.vx, shot.vy-target.vy
        speed2 = vx*vx+vy*vy
        if speed2 < 1e-9:
            continue
        time = (rx*vx+ry*vy)/speed2
        if not 0 < time <= shot.lifetime:
            continue
        intercept = (shot.x+shot.vx*time,shot.y+shot.vy*time)
        if wall_between(shot.get_pos(),intercept,maze):
            continue
        miss = max(0.,math.hypot(rx-vx*time,ry-vy*time)-target.radius-shot.radius)
        quality = math.exp(-.5*(miss/max(target.radius,1.))**2)
        best = max(best, quality)
    return best
