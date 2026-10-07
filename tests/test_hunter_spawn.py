from types import SimpleNamespace
import pytest
import config
from hunter.spawn import parse_hunter_cell, resolve_hunter_spawn, reserve_hunter_clearance


@pytest.mark.parametrize('bad', [True, 1, [], {}, {'spawn_cell': [True, 3]},
                                     {'spawn_cell': [2.5, 3]}, {'spawn_cell': ['2', 3]}])
def test_bad_hunter_configs_rejected(bad):
    with pytest.raises(ValueError):
        parse_hunter_cell(bad)


def test_optional_hunter_and_clearance():
    assert parse_hunter_cell(None) is None
    assert parse_hunter_cell({'spawn_cell': [2, 3]}) == (2, 3)
    maze = SimpleNamespace(grid_width=5, grid_height=5, grid=[[0]*5 for _ in range(5)],
        walls=[], position_calculator=SimpleNamespace(grid_center_to_screen=lambda x,y:(x*100+50,y*100+50)))
    player = SimpleNamespace(x=50, y=50, radius=config.SHIP_SIZE)
    assert resolve_hunter_spawn(None, maze, player) == (450,450)
    assert resolve_hunter_spawn({'spawn_cell':[2, 3]}, maze, player) == (250,350)
    for cell in ([0,0], [-1,1], [5,1]):
        with pytest.raises(ValueError):
            resolve_hunter_spawn({'spawn_cell':cell}, maze, player)
    assert reserve_hunter_clearance([(250,350),(251,350),(900,900)], (250,350), 20) == [(900,900)]


def open_maze(blocked=()):
    grid = [[0]*5 for _ in range(5)]
    for col, row in blocked:
        grid[row][col] = 1
    return SimpleNamespace(grid_width=5, grid_height=5, grid=grid, walls=[],
        position_calculator=SimpleNamespace(grid_center_to_screen=lambda x,y:(x*100+50,y*100+50)))


@pytest.mark.parametrize('player_pos, expected', [
    ((50, 50), (450, 450)), ((450, 450), (50, 50)), ((450, 50), (50, 450)), ((250, 250), (50, 50))])
def test_automatic_spawn_is_the_open_cell_furthest_from_the_player(player_pos, expected):
    player = SimpleNamespace(x=player_pos[0], y=player_pos[1], radius=config.SHIP_SIZE)
    assert resolve_hunter_spawn(None, open_maze(), player) == expected


def test_automatic_spawn_skips_unusable_cells_but_stays_far_away():
    player = SimpleNamespace(x=50, y=50, radius=config.SHIP_SIZE)
    # The far corner is solid, and a wall cuts through the next-furthest cell
    maze = open_maze(blocked=[(4, 4)])
    maze.walls = [SimpleNamespace(active=True, start=(445, 300), end=(445, 400))]
    assert resolve_hunter_spawn(None, maze, player) == (350, 450)
