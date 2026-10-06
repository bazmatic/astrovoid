"""Trailing chains for tentacles.

A chain is a list of world-space points joined by fixed-length segments. Each
frame it is towed by its root like a rope, so it streams out behind a moving
body and swings wide when the body turns, while a pull towards a rest pose
keeps it from going slack.
"""

import math
from typing import Callable, List, Tuple

Point = Tuple[float, float]


def drag_chain(
    chain: List[Point],
    anchor: Point,
    segment: float,
    rest_angle: Callable[[int, float], float],
    stiffness_base: float,
    stiffness_tip: float,
    snap: bool = False
) -> None:
    """Move a chain's root to anchor and drag the rest of it along, in place.
    
    Args:
        chain: Points from root to tip. Updated in place.
        anchor: New position of the root.
        segment: Length of each segment.
        rest_angle: Called with (point index, 0.0-1.0 position along the chain);
            returns the direction in radians that segment points at rest.
        stiffness_base: Pull towards the rest pose at the root (0.0 to 1.0).
        stiffness_tip: Pull towards the rest pose at the tip.
        snap: Jump straight to the rest pose, e.g. on first use or after a teleport.
    """
    chain[0] = anchor
    last = len(chain) - 1
    for i in range(1, len(chain)):
        t = i / last
        angle = rest_angle(i, t)
        prev_x, prev_y = chain[i - 1]
        rest_x = prev_x + math.cos(angle) * segment
        rest_y = prev_y + math.sin(angle) * segment
        
        dx = chain[i][0] - prev_x
        dy = chain[i][1] - prev_y
        length = math.hypot(dx, dy)
        if snap or length < 1e-6:
            chain[i] = (rest_x, rest_y)
            continue
        
        stiffness = stiffness_base + (stiffness_tip - stiffness_base) * t
        # Blend the dragged position towards the rest pose, then restore the
        # segment length
        dx = dx / length * segment
        dy = dy / length * segment
        dx += (rest_x - prev_x - dx) * stiffness
        dy += (rest_y - prev_y - dy) * stiffness
        length = math.hypot(dx, dy)
        if length < 1e-6:
            chain[i] = (rest_x, rest_y)
        else:
            chain[i] = (prev_x + dx / length * segment, prev_y + dy / length * segment)
