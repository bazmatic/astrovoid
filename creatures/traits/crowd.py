"""Crowd traits: run once a frame with every live creature of a kind."""
import math

from creatures.trait import Trait

SEPARATION_PASSES = 20  # a crowd can need a few rounds of pushing before nobody overlaps


def keep_apart(creatures) -> None:
    """Push overlapping creatures apart, each by half the overlap, until they only touch."""
    for _ in range(SEPARATION_PASSES):
        moved = False
        for i, a in enumerate(creatures):
            for b in creatures[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                distance = math.hypot(dx, dy)
                overlap = a.radius + b.radius - distance
                if overlap <= 0:
                    continue
                if distance == 0:                          # exactly on top of each other: part them sideways
                    dx, dy, distance = 1.0, 0.0, 1.0
                push_x, push_y = dx / distance * overlap / 2, dy / distance * overlap / 2
                a.x, a.y = a.x - push_x, a.y - push_y
                b.x, b.y = b.x + push_x, b.y + push_y
                moved = True
        if not moved:
            return


class KeepsApart(Trait):
    """Creatures of its kind never overlap: each frame they are pushed apart until they only touch."""
    NAME = 'keepsApart'
    CROWD = True

    def on_crowd(self, creatures, enc, dt):
        keep_apart(creatures)
