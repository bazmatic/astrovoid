# tests/test_layout_play.py
import math

import pygame
import pytest

import config
import level_config
from entities.jev_beacon import JevBeacon
from entities.rules_hunter import RulesHunter
from level_layout import parse_layout
from maze.config import MazeComplexity
from maze.generator import Maze
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_rules_hunter import SilentWorker

# The shared `game` fixture stubs these level_config functions; a layout is read through the real ones.
REAL = {name: getattr(level_config, name) for name in
        ('get_maze_complexity', 'get_maze_grid_size', 'get_level_seed', 'get_level_hunter_config')}


def real_level_config(monkeypatch):
    for name, function in REAL.items():
        monkeypatch.setattr(level_config, name, function)

LAYOUT = {
    'walls': [[3, 3], [4, 3]],
    'start': [1, 1], 'exit': [7, 7],
    'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'flocker', 'cell': [2, 6]},
                {'type': 'replay', 'cell': [6, 4]}, {'type': 'rules_hunter', 'cell': [6, 2]}],
    'beacon': [3, 5],
}


def file(layout=LAYOUT):
    return {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'enemies': {'static': 5},
            'layout': layout}


def test_a_maze_is_built_from_a_layout():
    pygame.init()
    pygame.display.set_mode((320, 240))
    layout = parse_layout(LAYOUT, 9)
    maze = Maze(3, complexity=MazeComplexity.EMPTY, grid_size=9, layout=layout)
    assert maze.grid == layout.grid()
    calc = maze.position_calculator
    assert calc.screen_to_grid(*maze.start_pos) == (1, 1)
    assert calc.screen_to_grid(maze.exit.x, maze.exit.y) == (7, 7)
    assert (3, 3) in maze.blocks and (3, 5) not in maze.blocks


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file() if level == 3 else None)
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def cells(game, items):
    calc = game.maze.position_calculator
    return [calc.screen_to_grid(*item.get_pos()) for item in items]


def test_start_and_exit_and_rock_are_where_the_layout_says(played):
    calc = played.maze.position_calculator
    assert calc.screen_to_grid(played.ship.x, played.ship.y) == (1, 1)
    assert calc.screen_to_grid(played.maze.exit.x, played.maze.exit.y) == (7, 7)
    assert played.maze.grid == parse_layout(LAYOUT, 9).grid()


def test_each_enemy_is_at_its_cell_and_only_those_exist(played):
    assert cells(played, played.enemies) == [(5, 5)]
    assert cells(played, played.flockers) == [(2, 6)]
    assert cells(played, played.replay_enemies) == [(6, 4)]
    assert cells(played, played.rules_hunters) == [(6, 2)] and isinstance(played.rules_hunters[0], RulesHunter)
    assert len(list(played.entity_manager.get_all_enemies())) == 4
    assert played.enemies[0].type == 'static'


def test_the_beacon_lies_at_its_cell(played):
    beacons = [c for c in played.powerup_crystals if isinstance(c, JevBeacon)]
    assert [played.maze.position_calculator.screen_to_grid(*b.get_pos()) for b in beacons] == [(3, 5)]


def test_it_is_a_boss_level_because_a_rules_hunter_is_on_it(played):
    assert played.boss_level and not played.ship.ammo_policy.charges_for_shots()


def test_restarting_does_not_pile_up_enemies(played):
    played.start_level()
    assert len(list(played.entity_manager.get_all_enemies())) == 4


def test_a_broken_layout_falls_back_to_the_generated_level(game, monkeypatch, caplog):  # noqa: F811
    real_level_config(monkeypatch)
    broken = dict(LAYOUT, start=[0, 0])
    monkeypatch.setattr(level_config, '_warned_layouts', set())      # warned once per process otherwise
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file(broken) if level == 3 else None)
    game.level = 3
    game.start_level()
    assert game.maze.grid != parse_layout(LAYOUT, 9).grid()
    assert sum(e.type == 'static' for e in game.enemies) == 5               # the file's own `static: 5`
    assert 'ignoring its layout' in caplog.text


def test_the_beacon_lies_exactly_where_the_layout_puts_it_even_where_automatic_placement_would_refuse(
        played, monkeypatch):
    # The automatic placement refuses spots near walls or the player (on fine grids, cells beside the start);
    # a layout's beacon is where its author put it, so it must not go through that check
    def refuse(*args, **kwargs):
        raise ValueError('too close')
    monkeypatch.setitem(type(played).start_level.__globals__, 'resolve_hunter_spawn', refuse)
    played.start_level()
    beacons = [c for c in played.powerup_crystals if isinstance(c, JevBeacon)]
    assert [played.maze.position_calculator.screen_to_grid(*b.get_pos()) for b in beacons] == [(3, 5)]
