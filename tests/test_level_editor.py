# tests/test_level_editor.py
import json
import os

import pygame
import pytest

import config
import level_config
from editor import files
from editor.model import PALETTE
from level_layout import parse_layout
from rendering.level_editor import LevelEditor
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode='')


@pytest.fixture
def editor(game, monkeypatch, tmp_path):  # noqa: F811
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    game.state = config.STATE_EDITOR
    real_level_config(monkeypatch)
    monkeypatch.setattr(files, 'level_path', lambda level: str(tmp_path / f'{level}.json'))
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: (
        json.loads((tmp_path / f'{level}.json').read_text()) if (tmp_path / f'{level}.json').exists() else
        ({'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12}, 'enemies': {'static': 2}}
         if level == 3 else None)))
    ed = LevelEditor(game, screen)
    ed.tmp = tmp_path
    return ed


def open_level(ed, level=3):
    ed.open_picker()
    ed.picker_index = level - 1
    ed.handle_key(key(pygame.K_RETURN))


def test_the_editor_env_var_gates_the_feature(monkeypatch):
    monkeypatch.delenv('ASTROVOID_EDITOR', raising=False)
    assert config.editor_enabled() is False
    monkeypatch.setenv('ASTROVOID_EDITOR', '')
    assert config.editor_enabled() is False
    monkeypatch.setenv('ASTROVOID_EDITOR', '1')
    assert config.editor_enabled() is True


def test_the_main_menu_has_an_editor_item_only_with_the_variable(monkeypatch):
    from rendering.main_menu import MainMenu
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.delenv('ASTROVOID_EDITOR', raising=False)
    assert 'EDITOR' not in MainMenu(screen).menu_options
    monkeypatch.setenv('ASTROVOID_EDITOR', '1')
    options = MainMenu(screen).menu_options
    assert options.index('EDITOR') == options.index('QUIT') - 1


def test_the_picker_chooses_a_level_with_the_arrows_and_opens_it(editor):
    editor.open_picker()
    assert editor.mode == 'picker' and editor.picker_index == 0
    editor.handle_key(key(pygame.K_RIGHT))
    editor.handle_key(key(pygame.K_DOWN))
    assert editor.picker_index == 1 + editor.PICKER_COLUMNS
    editor.picker_index = 2
    editor.handle_key(key(pygame.K_RETURN))
    assert editor.mode == 'edit' and editor.model.level == 3 and editor.model.grid_size == 12


def test_escape_leaves_the_picker_for_the_main_menu(editor):
    editor.open_picker()
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.game.state == config.STATE_MENU


def test_arrows_tab_space_and_delete_edit_the_level(editor):
    open_level(editor)
    model = editor.model
    model.cursor = (1, model.cursor[1])                         # room to move right on any generated maze
    start = model.cursor
    editor.handle_key(key(pygame.K_RIGHT))
    assert model.cursor == (start[0] + 1, start[1])
    editor.handle_key(key(pygame.K_TAB))
    assert model.selected == PALETTE[1]
    editor.handle_key(key(pygame.K_TAB, pygame.KMOD_SHIFT))
    assert model.selected == 'wall'
    editor.handle_key(key(pygame.K_SPACE))
    assert model.contents(model.cursor) == 'wall' and model.dirty
    editor.handle_key(key(pygame.K_BACKSPACE))
    assert model.contents(model.cursor) is None


def test_saving_writes_the_layout_and_clears_the_dirty_mark(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_SPACE))                       # something to save (a wall, if it can)
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_s))
    data = json.loads((editor.tmp / '3.json').read_text())
    assert parse_layout(data['layout'], 12) == editor.model.to_layout()
    assert editor.model.dirty is False and 'saved' in editor.flash.lower()


def test_a_save_that_cannot_be_written_says_so_and_keeps_the_edits(editor, monkeypatch):
    open_level(editor)
    editor.model.dirty = True
    monkeypatch.setattr(files, 'level_path', lambda level: str(editor.tmp / 'no' / 'dir' / '3.json'))
    editor.handle_key(key(pygame.K_s))
    assert 'could not' in editor.flash.lower() and editor.model.dirty is True


def test_leaving_with_unsaved_edits_asks_first(editor):
    open_level(editor)
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.mode == 'edit' and editor.confirm is not None
    editor.handle_key(key(pygame.K_n))
    assert editor.confirm is None and editor.mode == 'edit'
    editor.handle_key(key(pygame.K_ESCAPE))
    editor.handle_key(key(pygame.K_y))
    assert editor.mode == 'picker'


def test_leaving_a_clean_level_does_not_ask(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.mode == 'picker' and editor.confirm is None


def test_x_asks_then_reverts_to_the_generated_level(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_s))                           # a layout now exists on disk
    assert (editor.tmp / '3.json').exists()
    editor.handle_key(key(pygame.K_x))
    assert editor.confirm is not None
    editor.handle_key(key(pygame.K_y))
    assert not (editor.tmp / '3.json').exists()                  # the editor made that file, so it is deleted
    assert 'revert' in editor.flash.lower() and editor.model.dirty is False


def test_x_with_no_layout_says_there_is_nothing_to_revert(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_x))
    assert editor.confirm is None and 'nothing' in editor.flash.lower()


def test_every_screen_and_palette_item_draws(editor):
    editor.open_picker()
    editor.update(1.0)
    editor.draw()
    open_level(editor)
    model = editor.model
    free = [(col, row) for row in range(1, model.grid_size - 1) for col in range(1, model.grid_size - 1)
            if model.contents((col, row)) is None]
    for index, item in enumerate(PALETTE):
        model.cursor, model.palette_index = free[index * 2], index
        assert model.place(), item                                # every item lands, so every sprite is drawn
        editor.update(1.0)
        editor.draw()
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_ESCAPE))
    editor.draw()                                                # with the confirmation showing


def test_holding_an_arrow_repeats_and_releasing_stops(editor, monkeypatch):
    open_level(editor)
    editor.model.cursor = (1, editor.model.cursor[1])
    start = editor.model.cursor
    editor.handle_key(key(pygame.K_RIGHT))
    pressed = {pygame.K_RIGHT: True}
    monkeypatch.setattr(pygame.key, 'get_pressed', lambda: type('K', (), {'__getitem__': lambda s, k: pressed.get(k, False)})())
    for _ in range(40):
        editor.update(0.05 * config.FPS)
    assert editor.model.cursor[0] > start[0] + 2
    pressed.clear()
    stopped = editor.model.cursor
    for _ in range(10):
        editor.update(0.05 * config.FPS)
    assert editor.model.cursor == stopped


def test_drawing_does_not_read_the_level_file_every_frame(editor, monkeypatch):
    open_level(editor)
    reads = []
    monkeypatch.setattr(editor, '_saved_layout_exists', lambda: reads.append(1) or False)
    for _ in range(5):
        editor.update(1.0)
        editor.draw()
    assert reads == []


def test_the_palette_offers_the_neural_hunter():
    from rendering.level_editor import LABELS
    assert 'neural_hunter' in PALETTE and LABELS['neural_hunter'] == 'Viber'
    assert LABELS['wall'] == 'Wall' and LABELS['beacon'] == 'Jev beacon'
