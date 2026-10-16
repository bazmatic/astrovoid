# tests/test_editor_model.py
import pytest

from editor.model import PALETTE, EditorModel
from level_layout import ENEMY_TYPES, parse_layout


def model():
    layout = parse_layout({
        'walls': [[3, 3]], 'start': [1, 1], 'exit': [7, 7],
        'enemies': [{'type': 'static', 'cell': [5, 5]}], 'beacon': [3, 5]}, 9)
    return EditorModel(3, layout)


def at(m, cell, item=None):
    m.cursor = cell
    if item is not None:
        m.palette_index = PALETTE.index(item)


def test_the_palette_lists_everything_placeable():
    assert PALETTE == ('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon')


def test_the_cursor_starts_on_the_start_and_stays_in_the_interior():
    m = model()
    assert m.cursor == (1, 1)
    for _ in range(20):
        m.move(-1, -1)
    assert m.cursor == (1, 1)
    for _ in range(20):
        m.move(1, 1)
    assert m.cursor == (7, 7)                                 # grid 9: cells 1 to 7


def test_stepping_the_palette_wraps_round():
    m = model()
    m.step_palette(-1)
    assert m.selected == 'beacon'
    m.step_palette(1)
    assert m.selected == 'wall'


def test_a_wall_is_placed_on_an_empty_cell_and_removed():
    m = model()
    at(m, (2, 2), 'wall')
    assert m.place() and m.contents((2, 2)) == 'wall' and m.dirty
    assert m.remove() and m.contents((2, 2)) is None


def test_a_wall_replaces_an_enemy_or_the_beacon_but_never_the_start_or_exit():
    m = model()
    at(m, (5, 5), 'wall')
    assert m.place() and m.contents((5, 5)) == 'wall' and (5, 5) not in m.enemies
    at(m, (3, 5), 'wall')
    assert m.place() and m.beacon is None
    at(m, (1, 1), 'wall')
    assert not m.place() and m.contents((1, 1)) == 'start'
    at(m, (7, 7), 'wall')
    assert not m.place() and m.contents((7, 7)) == 'exit'


def test_one_enemy_per_cell_and_a_new_one_replaces_the_old():
    m = model()
    at(m, (5, 5), 'flocker')
    assert m.place() and m.contents((5, 5)) == 'flocker'
    assert list(m.enemies.values()).count('static') == 0


def test_an_enemy_cannot_go_on_a_wall_the_start_or_the_beacon():
    m = model()
    for cell in ((3, 3), (1, 1), (7, 7), (3, 5)):
        at(m, cell, 'egg')
        assert not m.place()
    assert m.dirty is False


def test_start_exit_and_beacon_are_single_so_placing_moves_them():
    m = model()
    at(m, (2, 2), 'start')
    assert m.place() and m.start == (2, 2) and m.contents((1, 1)) is None
    at(m, (6, 6), 'exit')
    assert m.place() and m.exit == (6, 6)
    at(m, (4, 4), 'beacon')
    assert m.place() and m.beacon == (4, 4) and m.contents((3, 5)) is None


def test_start_and_exit_cannot_land_on_each_other_or_on_something():
    m = model()
    at(m, (7, 7), 'start')
    assert not m.place()
    at(m, (3, 3), 'exit')
    assert not m.place()
    at(m, (5, 5), 'start')
    assert not m.place()                                      # an enemy is there


def test_start_and_exit_cannot_be_removed_but_the_beacon_can():
    m = model()
    at(m, (1, 1))
    assert not m.remove()
    at(m, (3, 5))
    assert m.remove() and m.beacon is None


def test_removing_from_an_empty_cell_changes_nothing():
    m = model()
    at(m, (4, 6))
    assert not m.remove() and not m.dirty


def test_the_model_makes_a_valid_layout_of_what_it_holds():
    m = model()
    at(m, (2, 2), 'wall'); m.place()
    at(m, (4, 4), 'patrol'); m.place()
    layout = m.to_layout()
    assert (2, 2) in layout.walls and ('patrol', (4, 4)) in layout.enemies
    assert parse_layout(layout.to_json(), 9) == layout


def test_the_exit_policy_cycles_through_every_policy():
    from policies.exit import AllCleared, AlwaysOpen, OpenAfterTime, TypeCleared
    m = model()
    assert m.exit_policy == AlwaysOpen()
    seen = []
    for _ in range(4):
        m.cycle_exit_policy()
        seen.append(m.exit_policy)
    assert seen == [OpenAfterTime(60), TypeCleared(('egg',)), AllCleared(), AlwaysOpen()]
    assert m.dirty


def test_the_ammo_policy_cycles():
    from policies.ammo import LimitedAmmo, UnlimitedAmmo
    m = model()
    assert m.ammo_policy == LimitedAmmo()
    m.cycle_ammo_policy()
    assert m.ammo_policy == UnlimitedAmmo() and m.dirty
    m.cycle_ammo_policy()
    assert m.ammo_policy == LimitedAmmo()


def test_the_timer_moves_in_steps_and_never_below_ten_seconds():
    from policies.exit import AllCleared, OpenAfterTime
    m = EditorModel(3, model().to_layout(), exit_policy=OpenAfterTime(60))
    assert m.adjust_timer(10) and m.exit_policy == OpenAfterTime(70) and m.dirty
    assert m.adjust_timer(-60) and m.exit_policy == OpenAfterTime(10)
    assert not m.adjust_timer(-10) and m.exit_policy == OpenAfterTime(10)
    m = EditorModel(3, model().to_layout(), exit_policy=AllCleared())
    assert not m.adjust_timer(10) and not m.dirty


def test_enemy_kinds_toggle_in_and_out_of_a_type_cleared_exit():
    from policies.exit import AlwaysOpen, TypeCleared
    m = EditorModel(3, model().to_layout(), exit_policy=TypeCleared(('egg',)))
    assert m.toggle_exit_type('baby') and m.exit_policy == TypeCleared(('egg', 'baby')) and m.dirty
    assert m.toggle_exit_type('egg') and m.exit_policy == TypeCleared(('baby',))
    assert not m.toggle_exit_type('baby') and m.exit_policy == TypeCleared(('baby',))   # keep at least one
    assert not m.toggle_exit_type('wall')
    m = EditorModel(3, model().to_layout(), exit_policy=AlwaysOpen())
    assert not m.toggle_exit_type('egg') and not m.dirty
