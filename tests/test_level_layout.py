# tests/test_level_layout.py
import pytest

import level_config
from level_layout import ENEMY_TYPES, Layout, LayoutError, parse_layout


def data(**changes):
    base = {
        'walls': [[3, 3], [4, 3]],
        'start': [1, 1], 'exit': [7, 7],
        'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'flocker', 'cell': [2, 6]},
                    {'type': 'rules_hunter', 'cell': [6, 2]}],
        'beacon': [3, 5],
    }
    base.update(changes)
    return base


def test_a_layout_parses_and_describes_its_grid():
    layout = parse_layout(data(), 9)
    assert layout.start == (1, 1) and layout.exit == (7, 7) and layout.beacon == (3, 5)
    grid = layout.grid()
    assert len(grid) == 9 and all(len(row) == 9 for row in grid)
    assert grid[0] == [1] * 9 and all(row[0] == 1 and row[8] == 1 for row in grid)   # the border
    assert grid[3][3] == 1 and grid[3][4] == 1 and grid[3][5] == 0                    # [row][col]
    assert layout.counts()['static'] == 1 and layout.counts()['rules_hunter'] == 1
    assert set(layout.counts()) == set(ENEMY_TYPES)


def test_a_layout_round_trips_through_json():
    layout = parse_layout(data(), 9)
    assert parse_layout(layout.to_json(), 9) == layout


def test_a_layout_without_a_beacon_has_none():
    assert parse_layout(data(beacon=None), 9).beacon is None
    without = data()
    del without['beacon']
    assert parse_layout(without, 9).beacon is None


@pytest.mark.parametrize('changes', [
    {'start': [0, 1]},                                            # on the border
    {'exit': [9, 7]},                                             # outside the grid
    {'exit': [1, 1]},                                             # the same cell as the start
    {'walls': [[1, 1]]},                                          # a wall on the start
    {'enemies': [{'type': 'dragon', 'cell': [5, 5]}]},            # unknown type
    {'enemies': [{'type': 'static', 'cell': [3, 3]}]},            # on a wall
    {'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'egg', 'cell': [5, 5]}]},   # two in one cell
    {'enemies': [{'type': 'static'}]},                            # no cell
    {'beacon': [3, 3]},                                           # on a wall
    {'walls': [[3]]},                                             # not a pair
    {'start': [1.5, 1]},                                          # not whole numbers
    {'exit': [1e309, 7]},                                         # far too big (JSON has no limit)
    {'start': [True, 1]},                                         # not a number at all
    {'walls': [['3', 3]]},
])
def test_a_mistaken_layout_is_rejected(changes):
    with pytest.raises(LayoutError):
        parse_layout(data(**changes), 9)


def test_missing_start_is_rejected():
    broken = data()
    del broken['start']
    with pytest.raises(LayoutError):
        parse_layout(broken, 9)


def file_with(layout, **extra):
    return {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9},
            'enemies': {'static': 7, 'egg': 2, 'split_boss': 1}, **extra, **({'layout': layout} if layout else {})}


def test_counts_come_from_the_layout_while_it_exists(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data()))
    counts = level_config.get_level_enemy_counts(3)
    assert (counts.static, counts.flocker, counts.egg, counts.total) == (1, 1, 0, 1)
    assert level_config.get_level_rules_hunter_count(3) == 1
    assert level_config.get_level_split_boss_count(3) == 0
    assert level_config.get_level_egg_count(3) == 0


def test_without_the_layout_the_files_own_counts_return(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(None))
    assert level_config.get_level_layout(3) is None
    assert level_config.get_level_enemy_counts(3).static == 7
    assert level_config.get_level_egg_count(3) == 2
    assert level_config.get_level_split_boss_count(3) == 1


def test_the_beacon_comes_from_the_layout(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data()))
    assert level_config.get_level_hunter_config(3) == {'spawn_cell': [3, 5]}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data(beacon=None)))
    assert level_config.get_level_hunter_config(3) is False


def test_an_invalid_layout_is_ignored_with_a_warning(monkeypatch, caplog):
    monkeypatch.setattr(level_config, '_warned_layouts', set())      # warned once per process otherwise
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data(start=[0, 0])))
    assert level_config.get_level_layout(3) is None
    assert 'layout' in caplog.text.lower()
    assert level_config.get_level_enemy_counts(3).static == 7             # the file's counts apply
