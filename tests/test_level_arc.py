"""The designed arc, levels 1 to 24: every level has a file and the files keep the pacing rules."""
import math
from unittest.mock import Mock

import pygame
import pytest

import config
import level_config
import level_rules
from level_rules import anemones_that_fit

ARC = range(1, 25)
BOSS_LEVELS = [6, 12, 18, 24]
ORDINARY = [level for level in ARC if level not in BOSS_LEVELS]
BOSSES = ('split_boss', 'mother_boss')
TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone') + BOSSES


def enemies(level):
    return level_config.load_level_config(level)['enemies']


def enemy_count(level):
    return sum(n for name, n in enemies(level).items() if name not in BOSSES)


@pytest.mark.parametrize('level', ARC)
def test_every_arc_level_has_a_complete_file(level):
    data = level_config.load_level_config(level)
    assert data is not None, f'levels/{level}.json is missing or does not parse'
    assert data['seed'] == 100 + level
    assert set(data['enemies']) == set(TYPES)
    assert all(type(n) is int and n >= 0 for n in data['enemies'].values())
    assert data['maze']['complexity'] in ('empty', 'simple', 'normal', 'complex', 'extreme')
    assert type(data['maze']['grid_size']) is int


def test_bosses_appear_only_on_the_boss_levels():
    assert [level for level in ARC if level_config.is_boss_level(level)] == BOSS_LEVELS


@pytest.mark.parametrize('level, split, mother', [(6, 1, 0), (12, 2, 0), (18, 0, 1), (24, 1, 1)])
def test_each_boss_level_has_its_bosses_in_an_open_arena(level, split, mother):
    assert (enemies(level)['split_boss'], enemies(level)['mother_boss']) == (split, mother)
    maze = level_config.load_level_config(level)['maze']
    assert maze['complexity'] == 'empty' and maze['grid_size'] <= 16


def test_at_most_one_enemy_type_is_new_on_any_level():
    seen = set()
    for level in ARC:
        new = {name for name, n in enemies(level).items() if n} - seen
        assert len(new) <= 1, f'level {level} introduces {sorted(new)}'
        seen |= new
    assert seen == set(TYPES)


def test_the_enemy_count_rises_gently_between_ordinary_levels():
    for earlier, later in zip(ORDINARY, ORDINARY[1:]):
        step = enemy_count(later) - enemy_count(earlier)
        assert -1 <= step <= 2, f'level {earlier} to {later} changes the count by {step}'


def test_the_arc_starts_small_and_ends_at_24():
    assert enemy_count(1) == 4
    assert enemy_count(23) == 24


def test_ordinary_mazes_never_shrink_and_stop_at_32():
    sizes = [level_config.get_maze_grid_size(level) for level in ORDINARY]
    assert sizes == sorted(sizes)
    assert sizes[0] == 10 and sizes[-1] == 32


@pytest.mark.parametrize('level', ARC)
def test_anemones_fit_the_maze(level):
    assert enemies(level)['anemone'] <= anemones_that_fit(level_config.get_maze_grid_size(level))


def test_the_hunter_flies_from_level_four_except_on_boss_levels():
    without = [level for level in ARC if not level_config.level_has_hunter(level)]
    assert without == [1, 2, 3] + BOSS_LEVELS


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    from profiles import ProfileManager

    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
    monkeypatch.delenv('START_LEVEL', raising=False)
    manager = ProfileManager(tmp_path / 'profiles.json')
    monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
    monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
    monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: False)
    game = Game(screen)
    yield game
    game._close_hunter()


@pytest.mark.parametrize('level', list(ARC) + [25, 30, 36, 42, 47, 66])
def test_every_enemy_the_level_asks_for_is_placed_clear_of_the_start(game, level):
    counts = level_config.get_level_enemy_counts(level) or level_rules.get_enemy_counts(level)
    asked_for = {
        'enemies': counts.static + counts.patrol + counts.aggressive,
        'replay_enemies': counts.replay, 'flockers': counts.flocker, 'flighthouses': counts.flighthouse,
        'eggs': counts.egg, 'anemones': level_config.get_level_anemone_count(level),
        'split_bosses': level_config.get_level_split_boss_count(level),
        'mother_bosses': level_config.get_level_mother_boss_count(level)}
    game.level = level

    game.start_level()

    placed = {name: len(getattr(game.entity_manager, name)) for name in asked_for}
    assert placed == asked_for
    for enemy in game.entity_manager.get_all_enemies():
        assert math.dist(enemy.get_pos(), game.maze.start_pos) >= config.ENEMY_START_CLEARANCE
