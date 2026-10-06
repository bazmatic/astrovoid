import math

import pytest

from game_handlers.spawn_manager import SpawnManager, SpawnConfig


class DummyEntityManager:
    def __init__(self):
        self.flockers = []

    def clear_all(self):
        pass


def _make_flocker(pos, _cr):
    # Minimal placeholder object with get_pos support if needed later
    class Flocker:
        def __init__(self, p):
            self.pos = p

        def get_pos(self):
            return self.pos

    return Flocker(pos)


def max_dist_from_centroid(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return max(math.hypot(p[0] - cx, p[1] - cy) for p in points)


def test_flocker_spawns_are_clustered():
    entity_manager = DummyEntityManager()
    spawn_manager = SpawnManager(entity_manager)

    # Two tight clusters with a far outlier; algorithm should pick the tightest grouping
    available_positions = [
        (0, 0),
        (2, 0),
        (0, 2),
        (2, 2),
        (30, 30),
        (100, 100),  # far outlier
    ]

    config = SpawnConfig(
        count=4,
        entity_list_attr="flockers",
        factory_func=_make_flocker,
        requires_command_recorder=False,
        post_create_hook=None,
    )

    used = spawn_manager._spawn_entities(config, available_positions, command_recorder=None)

    # Should have spawned the requested count
    assert len(entity_manager.flockers) == 4
    assert len(used) == 4

    # The spawned positions should be the tight cluster near the origin, not the outliers
    assert (100, 100) not in used

    # The resulting cluster should have a small maximum distance from its centroid
    max_dist = max_dist_from_centroid(used)
    assert max_dist <= 3.0


