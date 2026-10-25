"""The cave field: a smooth rock/open field over the maze cells that later becomes curved walls."""
import math
import random

import numpy as np
import pytest

import config
from maze.cave_field import CaveField, SampleGrid
from maze.config import MazeComplexity, MazeComplexityPresets
from maze.generator import RecursiveBacktrackingGenerator
from maze.positioning import MazePositionCalculator
from tests import cave_checks


def test_cave_settings_load_from_settings_json():
    assert config.CAVE.enabled is True
    assert config.CAVE.blurCells == 0.34
    assert config.CAVE.noiseScalesCells == (0.85, 0.35)
    assert config.CAVE.clearanceRadius == 16.0


def generated(size=26, seed=125):
    state = random.getstate()
    try:
        random.seed(seed)
        return RecursiveBacktrackingGenerator(
            MazeComplexityPresets.get_config(MazeComplexity.COMPLEX), size, size, 25).generate()
    finally:
        random.setstate(state)


def bordered(size):
    """An open grid of the given size with a wall all round."""
    return [[1 if r in (0, size-1) or c in (0, size-1) else 0 for c in range(size)] for r in range(size)]


def build(grid, *, strong=frozenset(), keep_clear=(), seed=7):
    rows, cols = len(grid), len(grid[0])
    samples = SampleGrid.for_maze(MazePositionCalculator(cols, rows), cols, rows, config.CAVE)
    return CaveField(grid, samples, strong=frozenset(strong), keep_clear=keep_clear, seed=seed,
                     settings=config.CAVE)


def centre(field, cell):
    s = field.samples
    return (s.origin[0] + (cell[0]+0.5)*s.cell_w, s.origin[1] + (cell[1]+0.5)*s.cell_h)


@pytest.fixture(scope='module')
def maze_field():
    return build(generated())


def test_deterministic_for_seed():
    grid = generated()
    first, again, other = build(grid, seed=3), build(grid, seed=3), build(grid, seed=4)
    assert np.array_equal(first.values, again.values)
    assert not np.array_equal(first.values, other.values)


def test_does_not_touch_global_random():
    grid = generated()
    state = random.getstate()
    build(grid, seed=11)
    assert random.getstate() == state


PATTERN = ["11100",
           "11000",
           "10001",
           "00011",
           "00111"]


def differing_fraction(size):
    grid = bordered(size)
    for r, line in enumerate(PATTERN):
        for c, ch in enumerate(line):
            grid[2+r][2+c] = int(ch)
    field = build(grid)
    s = field.samples
    rows, cols = s.shape
    raw = np.zeros((rows, cols), bool)
    for r in range(s.rows):
        for c in range(s.cols):
            if grid[r][c]:
                raw[r*s.per_y:(r+1)*s.per_y+1, c*s.per_x:(c+1)*s.per_x+1] = True
    region = (slice(2*s.per_y, 7*s.per_y+1), slice(2*s.per_x, 7*s.per_x+1))
    return np.mean(field.rock[region] != raw[region])


def test_curve_scales_with_cell():
    small, large = differing_fraction(10), differing_fraction(30)
    assert small > 0.02  # there is a visible curve at all
    assert abs(small - large) <= 0.25 * max(small, large)


def test_wall_cores_stay_rock(maze_field):
    assert cave_checks.wall_core_violations(maze_field) == []
    grid = bordered(12)
    for c in range(2, 10):
        grid[5][c] = 1  # a one-cell-thick wall line
    for r in range(6, 10):
        grid[r][7] = 1
    assert cave_checks.wall_core_violations(build(grid)) == []


def test_cell_centres_and_links_stay_open(maze_field):
    assert cave_checks.centre_and_link_violations(maze_field) == []


SERPENTINE = ["1111111111",
              "1000000001",
              "1111111101",
              "1000000001",
              "1011111111",
              "1000000001",
              "1111111101",
              "1000000001",
              "1011111111",
              "1111111111"]


def test_corridor_clearance(maze_field):
    assert cave_checks.corridor_clearance_violations(maze_field) == []
    corridors = build([[int(ch) for ch in line] for line in SERPENTINE])
    assert cave_checks.corridor_clearance_violations(corridors) == []


def test_no_rock_islands(maze_field):
    assert cave_checks.rock_island_violations(maze_field) == []


def test_gate_swing_kept_clear():
    grid = generated()
    rows, cols = len(grid), len(grid[0])
    # An open cell beside a wall, so rock would bulge into the swing without the clamp
    pin = next((c, r) for r in range(2, rows-2) for c in range(2, cols-2)
               if not grid[r][c] and grid[r][c+2] and not grid[r][c+1])
    plain = build(grid)
    radius = 1.5 * math.sqrt(plain.samples.cell_w * plain.samples.cell_h)
    keep_clear = [(centre(plain, pin), radius)]
    assert cave_checks.gate_swing_violations(plain, keep_clear) != []  # the clamp is what keeps it clear
    gated = build(grid, keep_clear=keep_clear)
    assert cave_checks.gate_swing_violations(gated) == []


def test_steel_cells_stay_square():
    grid = bordered(10)
    steel = {(4, 4), (5, 4), (4, 5)}
    for c, r in steel:
        grid[r][c] = 1
    field = build(grid, strong=steel)
    s = field.samples
    for c, r in steel:
        assert field.rock[r*s.per_y:(r+1)*s.per_y+1, c*s.per_x:(c+1)*s.per_x+1].all()
    # The open cell right of (5, 4): samples within half a cell of the steel face are open
    reach = 0.5 * min(s.cell_w, s.cell_h)
    face_x = s.origin[0] + 6*s.cell_w
    top, bottom = 4*s.per_y + 1, 5*s.per_y  # off the borders shared with other walls
    for iy in range(top, bottom):
        for ix in range(6*s.per_x + 1, 7*s.per_x):
            x, _ = s.point(iy, ix)
            if x - face_x <= reach:
                assert not field.rock[iy, ix], (iy, ix)


def test_rebuild_matches_fresh_build():
    grid = generated()
    rows, cols = len(grid), len(grid[0])
    field = build(grid)
    c, r = next((c, r) for r in range(1, rows-1) for c in range(1, cols-1)
                if grid[r][c] and not grid[r][c+1])
    grid[r][c] = 0
    changed = field.rebuild()
    fresh = build([row[:] for row in grid])
    assert np.allclose(field.values, fresh.values, atol=1e-5)
    assert np.array_equal(field.rock, fresh.rock)
    assert changed.shape == (rows, cols)
    assert changed[r, c]
