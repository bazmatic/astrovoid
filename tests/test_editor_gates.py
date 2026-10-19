# tests/test_editor_gates.py
import json

import pygame

from editor import files
from editor.model import PALETTE, EditorModel
from level_layout import GatePlacement, Layout, parse_layout
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_level_editor import editor, key, open_level  # noqa: F401 - pytest fixtures and helpers


def model_with(**kwargs):
    layout = Layout(12, frozenset(kwargs.pop('walls', ())), (1, 1), (10, 10), tuple(kwargs.pop('enemies', ())),
                    kwargs.pop('beacon', None), tuple(kwargs.pop('gates', ())))
    return EditorModel(1, layout)


def select(model, item):
    model.palette_index = PALETTE.index(item)


def test_the_palette_has_both_gates_after_the_beacon():
    assert PALETTE[-3:] == ('beacon', 'gate', 'motor_gate')


def test_placing_turning_and_flipping_a_gate(tmp_path):
    model = model_with()
    model.cursor = (5, 5)
    select(model, 'motor_gate')
    assert model.place() and model.contents((5, 5)) == 'motor_gate'
    assert model.gates[(5, 5)] == GatePlacement((5, 5), 0, 'cw')
    assert model.turn_gate() and model.gates[(5, 5)].angle == 45
    assert model.flip_gate() and model.gates[(5, 5)].motor == 'ccw'
    layout = model.to_layout()
    assert layout.gates == (GatePlacement((5, 5), 45, 'ccw'),)
    path = str(tmp_path / '1.json')
    files.save_layout(path, layout, {'seed': 1})
    reloaded = parse_layout(json.loads(open(path).read())['layout'], 12)
    assert reloaded == layout
    assert EditorModel(1, reloaded).gates == model.gates


def test_turning_wraps_at_180_and_a_free_gate_cannot_flip():
    model = model_with(gates=[GatePlacement((5, 5), 135)])
    model.cursor = (5, 5)
    assert model.turn_gate() and model.gates[(5, 5)].angle == 0
    assert model.flip_gate() is False and model.gates[(5, 5)].motor is None
    model.cursor = (6, 6)
    assert model.turn_gate() is False and model.flip_gate() is False


def test_a_gate_replaces_the_other_kind():
    model = model_with(gates=[GatePlacement((5, 5), 90)])
    model.cursor = (5, 5)
    select(model, 'motor_gate')
    assert model.place() and model.gates[(5, 5)] == GatePlacement((5, 5), 0, 'cw')
    select(model, 'gate')
    assert model.place() and model.gates[(5, 5)] == GatePlacement((5, 5))


def test_a_gate_cannot_go_across_a_wall():
    model = model_with(walls=[(6, 5)])
    model.cursor = (5, 5)
    select(model, 'gate')
    assert model.place() is False and model.gates == {} and not model.dirty
    model = model_with(walls=[(6, 6)], gates=[GatePlacement((5, 5))])
    model.cursor = (5, 5)
    assert model.turn_gate() is False and model.gates[(5, 5)].angle == 0


def test_a_gate_cannot_reach_the_border():
    model = model_with()
    model.cursor = (1, 5)
    select(model, 'gate')
    assert model.place() is False


def test_a_wall_cannot_go_across_a_plank():
    model = model_with(gates=[GatePlacement((5, 5))])
    model.cursor = (6, 5)
    select(model, 'wall')
    assert model.place() is False and (6, 5) not in model.walls
    model.cursor = (5, 5)
    assert model.place() is False
    model.cursor = (6, 7)
    assert model.place() is True


def test_a_gate_cannot_share_a_cell_and_can_be_removed():
    model = model_with(enemies=[('static', (4, 4))], beacon=(7, 7), gates=[GatePlacement((5, 5), 0, 'cw')])
    select(model, 'gate')
    for cell in ((1, 1), (10, 10), (7, 7), (4, 4)):
        model.cursor = cell
        assert model.place() is False
    for item in ('static', 'start', 'exit', 'beacon'):
        model.cursor = (5, 5)
        select(model, item)
        assert model.place() is False
    model.cursor = (5, 5)
    assert model.remove() and model.gates == {} and model.contents((5, 5)) is None


def test_r_and_f_turn_and_flip_in_the_editor(editor):  # noqa: F811
    open_level(editor)
    model = editor.model
    model.cursor = (5, 5)
    model.walls.clear()
    select(model, 'motor_gate')
    editor.handle_key(key(pygame.K_SPACE))
    editor.handle_key(key(pygame.K_r))
    editor.handle_key(key(pygame.K_f))
    assert model.gates[(5, 5)] == GatePlacement((5, 5), 45, 'ccw')


def test_the_preview_draws_gates(editor):  # noqa: F811
    open_level(editor)
    model = editor.model
    model.walls.clear()
    model.enemies.clear()
    model.cursor = (2, 2)
    editor.draw()
    before = editor.screen.copy()
    select(model, 'motor_gate')
    editor.handle_key(key(pygame.K_SPACE))
    editor.draw()
    calc = editor._preview[0].position_calculator
    x, y = calc.grid_center_to_screen(2, 2)
    area = pygame.Rect(0, 0, 3 * calc.cell_size_x, 3 * calc.cell_size_y)
    area.center = (x, y)
    area = area.clip(editor.screen.get_rect())
    differ = [(i, j) for i in range(area.left, area.right, 3) for j in range(area.top, area.bottom, 3)
              if before.get_at((i, j)) != editor.screen.get_at((i, j))]
    assert len(differ) > 10
    key_before_turn = editor._preview_key
    editor.handle_key(key(pygame.K_r))              # turning rebuilds the preview
    editor.draw()
    assert editor._preview_key != key_before_turn and editor.model.gates[(2, 2)].angle == 45


def test_a_gate_cannot_be_placed_or_turned_into_another_plank():
    model = model_with(gates=[GatePlacement((5, 5), 0), GatePlacement((7, 5), 90)])
    select(model, 'gate')
    model.cursor = (6, 5)
    assert model.place() is False and (6, 5) not in model.gates
    model.cursor = (7, 5)
    assert model.turn_gate() is True and model.gates[(7, 5)].angle == 135    # still clear of (4..6, 5)
    assert model.turn_gate() is False and model.gates[(7, 5)].angle == 135   # at 0 its tip would reach (6, 5)


def test_planks_that_share_no_cell_are_fine_and_a_gate_can_replace_its_own_kind():
    model = model_with(gates=[GatePlacement((5, 5), 0), GatePlacement((7, 5), 90)])
    model.cursor = (5, 5)
    select(model, 'motor_gate')
    assert model.place() is True and model.gates[(5, 5)] == GatePlacement((5, 5), 0, 'cw')
