"""The campaign's effective layouts and files introduce threats gradually."""
import math
from unittest.mock import Mock

import pygame
import pytest

import config
import enemy_kinds
import level_config
import level_rules
from level_rules import anemones_that_fit

ARC = range(1, 25)
BOSS_LEVELS = [12, 18, 24]
ORDINARY = [level for level in ARC if level not in BOSS_LEVELS]


def enemies(level):
    layout = level_config.get_level_layout(level)
    if layout is not None:
        return layout.counts()
    return level_config.load_level_config(level)['enemies']


def enemy_count(level):
    return sum(enemies(level).values())


@pytest.mark.parametrize('level', ARC)
def test_every_arc_level_has_a_complete_file_and_valid_layout(level):
    data = level_config.load_level_config(level)
    assert data['seed'] == 100 + level
    assert set(data['enemies']) == set(enemy_kinds.kinds())
    assert all(type(n) is int and n >= 0 for n in data['enemies'].values())
    assert 'layout' not in data or level_config.get_level_layout(level) is not None
    assert {k:v for k,v in enemies(level).items() if v} == {k:v for k,v in data['enemies'].items() if v}


def test_boss_introductions_build_on_the_smaller_creatures():
    assert enemies(6)['split_boss'] == 0
    assert enemies(12)['split_boss'] == 1
    assert enemies(18)['split_boss'] == 2
    assert enemies(24)['mother_boss'] == 1
    assert enemies(24)['neural_hunter'] == 0
    assert enemies(30)['boss_viber'] == 1


def test_at_most_one_enemy_type_is_new_on_any_level():
    seen = set()
    first = {}
    for level in range(1, 31):
        new = {name for name,n in enemies(level).items() if n} - seen
        assert len(new) <= 1, f'level {level} introduces {sorted(new)}'
        for kind in new:
            first[kind] = level
        seen |= new
    assert first == {'static':1, 'patrol':2, 'aggressive':3, 'egg':4, 'flocker':5,
                     'anemone':7, 'replay':8, 'belemnite':9, 'flighthouse':10,
                     'split_boss':12, 'vibelet':19, 'neural_hunter':21,
                     'rules_hunter':23, 'mother_boss':24, 'boss_viber':30}
    # A first encounter is one of the new creature, rather than a swarm or a boss squad.
    assert all(enemies(level)[kind] == 1 for kind,level in first.items() if kind != 'static')


def test_the_enemy_count_rises_gently_between_ordinary_levels():
    for earlier,later in zip(ORDINARY,ORDINARY[1:]):
        assert 0 <= enemy_count(later)-enemy_count(earlier) <= 2
    assert enemy_count(1) == 4 and enemy_count(23) == 24


def test_ordinary_mazes_never_shrink_and_stop_at_32():
    sizes = [level_config.get_maze_grid_size(level) for level in ORDINARY]
    assert sizes == sorted(sizes)
    assert sizes[0] == 10 and sizes[-1] == 32


@pytest.mark.parametrize('level', ARC)
def test_anemones_fit_the_maze(level):
    assert enemies(level)['anemone'] <= anemones_that_fit(level_config.get_maze_grid_size(level))


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


@pytest.mark.parametrize('level', list(ARC) + [25, 26, 30, 36, 42, 47, 66])
def test_every_enemy_the_level_asks_for_is_placed_clear_of_the_start(game, level):
    counts = level_config.get_level_enemy_counts(level) or level_rules.get_enemy_counts(level)
    asked_for = {
        'static': counts.static, 'patrol': counts.patrol, 'aggressive': counts.aggressive,
        'replay': counts.replay, 'flocker': counts.flocker, 'flighthouse': counts.flighthouse,
        'egg': counts.egg, 'anemone': level_config.get_level_anemone_count(level),
        'split_boss': level_config.get_level_split_boss_count(level),
        'mother_boss': level_config.get_level_mother_boss_count(level)}
    game.level = level

    game.start_level()

    placed = {kind: len(game.roster.of_kind(kind)) for kind in asked_for}
    assert placed == asked_for
    for enemy in game.roster.all():
        assert math.dist(enemy.get_pos(), game.maze.start_pos) >= config.ENEMY_START_CLEARANCE
