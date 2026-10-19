# tests/test_gate_layout.py
import pytest

from config import ObstacleSettings, SETTINGS
from level_layout import GatePlacement, Layout, LayoutError, parse_layout, plank_cells


def data(**changes):
    base = {'walls': [[3, 3]], 'start': [1, 1], 'exit': [10, 10],
            'enemies': [{'type': 'static', 'cell': [5, 8]}]}
    base.update(changes)
    return base


def test_gates_round_trip_through_json():
    d = data(gates=[{'cell': [5, 5]}, {'cell': [8, 5], 'angle': 90, 'motor': 'ccw'}])
    layout = parse_layout(d, 12)
    assert layout.gates == (GatePlacement((5, 5)), GatePlacement((8, 5), 90, 'ccw'))
    assert parse_layout(layout.to_json(), 12) == layout
    assert layout.to_json()['gates'] == [{'cell': [5, 5]}, {'cell': [8, 5], 'angle': 90, 'motor': 'ccw'}]


def test_a_layout_without_gates_writes_none():
    layout = Layout(12, frozenset(), (1, 1), (10, 10))
    assert 'gates' not in layout.to_json()


def test_the_plank_crosses_its_neighbours():
    assert plank_cells(GatePlacement((5, 5))) == {(4, 5), (5, 5), (6, 5)}
    assert plank_cells(GatePlacement((5, 5), 90)) == {(5, 4), (5, 5), (5, 6)}


def test_a_plank_across_a_wall_is_refused():
    with pytest.raises(LayoutError):
        parse_layout(data(walls=[[6, 5]], gates=[{'cell': [5, 5]}]), 12)
    parse_layout(data(walls=[[6, 5]], gates=[{'cell': [5, 5], 'angle': 90}]), 12)


@pytest.mark.parametrize('gates', [
    [{'cell': [1, 1]}],
    [{'cell': [5, 8]}],
    [{'cell': [5, 5]}, {'cell': [5, 5], 'angle': 90}],
    [{'cell': [5, 5], 'angle': 30}],
    [{'cell': [5, 5], 'angle': 180}],
    [{'cell': [5, 5], 'motor': 'fast'}],
])
def test_bad_gates_are_refused(gates):
    with pytest.raises(LayoutError):
        parse_layout(data(gates=gates), 12)


def test_the_obstacle_settings_have_their_defaults():
    assert SETTINGS.obstacles == ObstacleSettings()
    o = ObstacleSettings()
    assert (o.gateMass, o.gateThicknessCells, o.gateElasticity, o.motorRate) == (16.0, 0.16, 0.4, 1.2)
    assert (o.motorMaxForce, o.bulletImpulse, o.substeps, o.moverReachMargin) == (30_000_000.0, 300.0, 8, 24.0)


@pytest.mark.parametrize('gates', [
    [{'cell': [5, 5], 'angle': 45}, {'cell': [6, 5], 'angle': 135}],      # an X
    [{'cell': [5, 5]}, {'cell': [7, 5]}],                                  # tips meet
])
def test_overlapping_planks_are_refused(gates):
    with pytest.raises(LayoutError, match='overlaps'):
        parse_layout(data(gates=gates), 12)


def test_planks_that_share_no_cell_are_allowed():
    layout = parse_layout(data(gates=[{'cell': [5, 5]}, {'cell': [7, 5], 'angle': 90}]), 12)
    assert len(layout.gates) == 2


@pytest.mark.parametrize('changes', [
    {'start': [4, 5]},
    {'exit': [6, 5]},
    {'enemies': [{'type': 'anemone', 'cell': [4, 5]}]},
    {'enemies': [{'type': 'flighthouse', 'cell': [6, 5]}]},
])
def test_a_plank_cannot_cover_the_start_the_exit_or_an_anchored_enemy(changes):
    with pytest.raises(LayoutError, match='plank'):
        parse_layout(data(gates=[{'cell': [5, 5]}], **changes), 12)
    parse_layout(data(gates=[{'cell': [5, 5], 'angle': 90}], **changes), 12)     # turned, it misses that cell


def test_a_plank_may_cover_an_enemy_that_moves():
    parse_layout(data(gates=[{'cell': [5, 5]}], enemies=[{'type': 'static', 'cell': [4, 5]}]), 12)
