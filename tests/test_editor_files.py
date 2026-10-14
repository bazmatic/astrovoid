# tests/test_editor_files.py
import json

import pygame
import pytest

import level_config
from editor.files import revert_layout, save_layout
from editor.generated import generated_layout
from level_layout import parse_layout
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config

LAYOUT = parse_layout({'walls': [[3, 3]], 'start': [1, 1], 'exit': [7, 7],
                       'enemies': [{'type': 'static', 'cell': [5, 5]}], 'beacon': None}, 9)
DEFAULTS = {'seed': 3, 'maze': {'complexity': 'empty', 'grid_size': 9}}


def test_saving_adds_the_layout_and_keeps_every_other_key(tmp_path):
    path = tmp_path / '3.json'
    path.write_text(json.dumps({'seed': 7, 'maze': {'complexity': 'normal', 'grid_size': 9},
                                'enemies': {'static': 2}, 'hunter': False}))
    save_layout(str(path), LAYOUT, DEFAULTS)
    data = json.loads(path.read_text())
    assert data['seed'] == 7 and data['enemies'] == {'static': 2} and data['hunter'] is False
    assert parse_layout(data['layout'], 9) == LAYOUT
    assert 'created_by_editor' not in data


def test_saving_a_level_without_a_file_creates_one(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    data = json.loads(path.read_text())
    assert data['seed'] == 3 and data['maze'] == DEFAULTS['maze'] and data['created_by_editor'] is True
    assert parse_layout(data['layout'], 9) == LAYOUT


def test_the_saved_file_keeps_each_cell_on_one_line(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert '"start": [1, 1]' in path.read_text()


def test_reverting_removes_only_the_layout(tmp_path):
    path = tmp_path / '3.json'
    path.write_text(json.dumps({'seed': 7, 'enemies': {'static': 2}}))
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert revert_layout(str(path)) is True
    assert json.loads(path.read_text()) == {'seed': 7, 'enemies': {'static': 2}}


def test_reverting_a_file_the_editor_made_deletes_it(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert revert_layout(str(path)) is True
    assert not path.exists()


def test_reverting_with_nothing_to_revert_changes_nothing(tmp_path):
    path = tmp_path / '3.json'
    assert revert_layout(str(path)) is False
    path.write_text(json.dumps({'seed': 7}))
    assert revert_layout(str(path)) is False
    assert json.loads(path.read_text()) == {'seed': 7}


def test_an_unwritable_path_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        save_layout(str(tmp_path / 'no' / 'such' / 'dir' / '3.json'), LAYOUT, DEFAULTS)


def test_a_generated_level_loads_as_the_layout_it_plays_as(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12},
        'enemies': {'static': 2, 'flocker': 1, 'egg': 1}} if level == 3 else None)
    layout = generated_layout(game, 3)
    assert layout.grid_size == 12
    assert layout.grid() == game.maze.grid
    calc = game.maze.position_calculator
    assert layout.start == calc.screen_to_grid(game.ship.x, game.ship.y)
    assert layout.exit == calc.screen_to_grid(game.maze.exit.x, game.maze.exit.y)
    assert layout.counts()['static'] == 2 and layout.counts()['flocker'] == 1 and layout.counts()['egg'] == 1
    assert layout == parse_layout(layout.to_json(), 12)                      # and it is a playable layout


def test_playing_the_loaded_layout_gives_the_same_level(game, monkeypatch, tmp_path):  # noqa: F811
    real_level_config(monkeypatch)
    plain = {'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12},
             'enemies': {'static': 2, 'flocker': 1}}
    files = {3: dict(plain)}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: files.get(level))
    layout = generated_layout(game, 3)
    before = (list(game.maze.grid), sorted(e.get_pos() for e in game.entity_manager.get_all_enemies()))
    files[3]['layout'] = layout.to_json()
    game.level = 3
    game.start_level()
    after = (list(game.maze.grid), sorted(e.get_pos() for e in game.entity_manager.get_all_enemies()))
    assert after[0] == before[0]
    # positions are cell centres now, so compare cells
    calc = game.maze.position_calculator
    cell = lambda pos: calc.screen_to_grid(*pos)
    assert sorted(map(cell, after[1])) == sorted(map(cell, before[1]))
