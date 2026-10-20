"""Par time: how long a level reasonably takes when every enemy is killed and every crystal collected."""

from collections import deque
from typing import Mapping, Optional, Sequence, Tuple

import config
import enemy_kinds


def route_cells(grid: Sequence[Sequence[int]], start: Tuple[int, int],
                end: Tuple[int, int]) -> Optional[int]:
    """Steps on the shortest four-way path between two (col, row) cells through open cells, or None."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    def is_open(col: int, row: int) -> bool:
        return 0 <= row < rows and 0 <= col < cols and (grid[row][col] == 0 or (col, row) in (start, end))

    if not (is_open(*start) and is_open(*end)):
        return None
    steps = {start: 0}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == end:
            return steps[cell]
        col, row = cell
        for nxt in ((col + 1, row), (col - 1, row), (col, row + 1), (col, row - 1)):
            if nxt not in steps and is_open(*nxt):
                steps[nxt] = steps[cell] + 1
                queue.append(nxt)
    return None


def par_seconds(route_px: float, enemy_counts: Mapping[str, int], crystals: int,
                timer_seconds: Optional[float] = None, settings=None) -> float:
    """Par from the route length, the enemies on the level at its start and the crystals dropped."""
    settings = settings or config.SETTINGS.game
    speed = settings.parSpeedShare * config.SHIP_MAX_SPEED * config.FPS
    # Bosses that keep making enemies: each adds a flat allowance for itself and what it spawns
    bosses = sum(count for kind, count in enemy_counts.items() if enemy_kinds.kind(kind).par_weight == 'spawningBoss')
    others = sum(enemy_counts.values()) - bosses
    par = (route_px / speed
           + settings.parSecondsPerSpawningBoss * bosses
           + settings.parSecondsPerEnemy * others
           + settings.parSecondsPerCrystal * crystals)
    if timer_seconds is not None:
        par = max(par, timer_seconds + settings.parTimerMargin)
    return par
