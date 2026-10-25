"""Procedural levels have connected flight corridors and continuous masonry."""
import random
from collections import deque

import pytest

from maze.config import MazeComplexity, MazeComplexityPresets
from maze.generator import RecursiveBacktrackingGenerator


def generate(complexity, size, seed):
    state = random.getstate()
    try:
        random.seed(seed)
        return RecursiveBacktrackingGenerator(
            MazeComplexityPresets.get_config(complexity), size, size, 25).generate()
    finally:
        random.setstate(state)


@pytest.mark.parametrize('complexity', list(MazeComplexity))
@pytest.mark.parametrize('size', [5, 10, 26, 50, 100])
def test_every_open_cell_and_all_four_corners_are_connected(complexity, size):
    for seed in range(8):
        grid = generate(complexity,size,seed)
        assert all(grid[0]) and all(grid[-1])
        assert all(row[0] and row[-1] for row in grid)
        open_cells = {(x,y) for y,row in enumerate(grid) for x,v in enumerate(row) if not v}
        assert {(1,1),(size-2,1),(1,size-2),(size-2,size-2)} <= open_cells
        reached = {(1,1)}
        queue = deque(reached)
        while queue:
            x,y = queue.popleft()
            for neighbour in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if neighbour in open_cells and neighbour not in reached:
                    reached.add(neighbour)
                    queue.append(neighbour)
        assert reached == open_cells


@pytest.mark.parametrize('complexity', list(MazeComplexity)[1:])
def test_generated_walls_form_runs_instead_of_isolated_blocks(complexity):
    for seed in range(20):
        grid = generate(complexity,26,seed)
        walls = {(x,y) for y in range(1,25) for x in range(1,25) if grid[y][x]}
        assert len(walls) >= 15
        for x,y in walls:
            assert any(grid[ny][nx] for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)))


def test_seed_reproduces_a_maze_but_different_seeds_change_its_routes():
    first = generate(MazeComplexity.COMPLEX,26,125)
    assert first == generate(MazeComplexity.COMPLEX,26,125)
    assert first != generate(MazeComplexity.COMPLEX,26,126)


def test_empty_levels_remain_open_arenas():
    grid = generate(MazeComplexity.EMPTY,26,125)
    assert all(not cell for row in grid[1:-1] for cell in row[1:-1])
