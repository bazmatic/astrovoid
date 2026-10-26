"""The cave field: a smooth rock/open field over the maze cells that later becomes curved walls."""
import dataclasses
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


def build(grid, *, strong=frozenset(), keep_clear=(), seed=7, settings=config.CAVE):
    rows, cols = len(grid), len(grid[0])
    samples = SampleGrid.for_maze(MazePositionCalculator(cols, rows), cols, rows, settings)
    return CaveField(grid, samples, strong=frozenset(strong), keep_clear=keep_clear, seed=seed,
                     settings=settings)


SMOOTH = dataclasses.replace(config.CAVE, noiseAmplitude=0.0)  # deterministic shapes from blur alone


def walled(cols, rows, open_cells):
    return [[0 if (c, r) in open_cells else 1 for c in range(cols)] for r in range(rows)]


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


def test_anti_goals_on_the_real_display(monkeypatch):
    """The checks above, on the real fullscreen display (1352x878), where cells are about a third
    of the default screen's and the clearance is capped by the cell."""
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    grid = generated(32)  # the largest grids, whose cells are about 26 px tall here
    rows, cols = len(grid), len(grid[0])
    pin = next((c, r) for r in range(2, rows-2) for c in range(2, cols-2)
               if not grid[r][c] and grid[r][c+2] and not grid[r][c+1])
    plain = build(grid)
    keep_clear = [(centre(plain, pin), 1.5 * math.sqrt(plain.samples.cell_w * plain.samples.cell_h))]
    steel_grid = bordered(10)
    steel = {(4, 4), (5, 4), (4, 5)}
    for c, r in steel:
        steel_grid[r][c] = 1
    fields = {'maze': build(grid, keep_clear=keep_clear),
              'serpentine': build([[int(ch) for ch in line] for line in SERPENTINE]),
              'steel': build(steel_grid, strong=steel)}
    assert fields['maze'].samples.cell_h < 27
    for name, field in fields.items():
        assert cave_checks.corridor_clearance_violations(field) == [], name
        assert cave_checks.centre_and_link_violations(field) == [], name
        assert cave_checks.wall_core_violations(field) == [], name
        assert cave_checks.rock_island_violations(field) == [], name
        assert cave_checks.gate_swing_violations(field) == [], name
        assert cave_checks.steel_face_violations(field) == [], name


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
    assert cave_checks.steel_face_violations(build(grid, strong=steel)) == []


def test_gate_swing_cut_off_by_rock_stays_clear():
    # A small swing in the inner corner of an open room: the blurred corner fill is rock all
    # round it, so without the anchor the hole cleanup would refill the clamped swing
    grid = bordered(10)
    plain = build(grid, settings=SMOOTH)
    s = plain.samples
    corner = (s.origin[0] + s.cell_w, s.origin[1] + s.cell_h)
    keep_clear = [(corner, 0.25*min(s.cell_w, s.cell_h))]
    assert cave_checks.gate_swing_violations(plain, keep_clear) != []
    assert cave_checks.gate_swing_violations(build(grid, keep_clear=keep_clear, settings=SMOOTH)) == []


# One-cell corridors so narrow (against the blur) that their middles are rock except the
# centre-line tubes, ending at steel. The clamped band at the steel face is far from the tubes,
# so without the anchor the hole cleanup would refill it.
STEEL_FACES = {
    'beside': (walled(10, 40, {(c, 20) for c in range(2, 9)}), {(1, 20)}),
    'above': (walled(100, 10, {(50, r) for r in range(2, 9)}), {(50, 1)}),
    'below': (walled(100, 10, {(50, r) for r in range(1, 8)}), {(50, 8)}),
}


@pytest.mark.parametrize('side', STEEL_FACES)
def test_steel_face_cut_off_by_rock_stays_clear(side):
    grid, steel = STEEL_FACES[side]
    assert cave_checks.steel_face_violations(build(grid, strong=steel, settings=SMOOTH)) == []


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
