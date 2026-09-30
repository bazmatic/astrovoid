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
    assert resolve_hunter_spawn({'spawn_cell':[2, 3]}, maze, player) == (250,350)
    for cell in ([0,0], [-1,1], [5,1]):
        with pytest.raises(ValueError):
            resolve_hunter_spawn({'spawn_cell':cell}, maze, player)
    assert reserve_hunter_clearance([(250,350),(251,350),(900,900)], (250,350), 20) == [(900,900)]
