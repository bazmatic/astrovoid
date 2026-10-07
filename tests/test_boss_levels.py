"""Boss levels: which levels they are, who flies on them, and the locked exit."""
import pytest

import config
import level_config


def level_file(**enemies):
    """A loader that gives every level the same file."""
    return lambda level: {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
                          'enemies': {'static': 0, 'patrol': 0, 'aggressive': 0, 'replay': 0, 'flocker': 0,
                                      'flighthouse': 0, 'egg': 0, 'anemone': 0,
                                      'split_boss': 0, 'mother_boss': 0, **enemies}}


def no_level_files(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: None)


def test_without_a_file_every_sixth_level_is_a_boss_level(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(25, 50) if level_config.is_boss_level(level)] == [30, 36, 42, 48]


@pytest.mark.parametrize('boss', ['split_boss', 'mother_boss'])
def test_a_level_file_with_a_boss_makes_any_level_a_boss_level(monkeypatch, boss):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(**{boss: 1}))
    assert level_config.is_boss_level(7)


def test_a_level_file_without_bosses_makes_a_sixth_level_ordinary(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=3))
    assert not level_config.is_boss_level(30)


def test_no_hunter_before_its_first_level(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(1, 6) if level_config.level_has_hunter(level)] == [4, 5]


def test_no_hunter_on_boss_levels(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(28, 38) if not level_config.level_has_hunter(level)] == [30, 36]


def test_no_hunter_on_a_boss_level_made_by_a_level_file(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    assert not level_config.level_has_hunter(7)


def test_a_level_file_can_forbid_the_hunter(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'hunter': False})
    assert not level_config.level_has_hunter(9)


def test_a_level_file_can_place_a_hunter_early_or_on_a_boss_level(monkeypatch):
    placed = {'hunter': {'spawn_cell': [4, 4]}}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: placed)
    assert level_config.level_has_hunter(1)
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {**level_file(split_boss=1)(level), **placed})
    assert level_config.level_has_hunter(6)


def test_the_hunter_interval_still_applies_from_the_first_level(monkeypatch):
    no_level_files(monkeypatch)
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)
    assert not level_config.level_has_hunter(9)
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 5)
    assert [level for level in range(1, 21) if level_config.level_has_hunter(level)] == [5, 10, 15, 20]
from unittest.mock import Mock

import pygame


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
    game = Game(screen)
    yield game
    game._close_hunter()


def start(game, level):
    game.level = level
    game.state = config.STATE_PLAYING
    game.start_level()
    game.update(1.0)


def kill(entities):
    for entity in entities:
        entity.active = False


def test_the_exit_is_locked_while_a_split_boss_lives(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, replay=2))
    start(game, 6)
    assert len(game.split_bosses) == 1
    assert not game.maze.exit.is_activated


def test_the_exit_is_locked_while_a_mother_boss_lives_even_with_no_eggs(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(mother_boss=1))
    start(game, 18)
    assert not any(egg.active for egg in game.eggs)
    assert not game.maze.exit.is_activated


def test_killing_the_boss_opens_the_exit_even_with_its_escort_alive(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, replay=2))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert any(ship.active for ship in game.replay_enemies)
    assert game.maze.exit.is_activated


def test_every_boss_must_die(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=2))
    start(game, 12)
    kill(game.split_bosses[:1])
    game.update(1.0)
    assert not game.maze.exit.is_activated


def test_a_mother_boss_level_needs_the_boss_and_the_eggs_dead(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(mother_boss=1, egg=2))
    start(game, 18)
    assert not game.maze.exit.is_activated
    kill(game.mother_bosses)
    game.update(1.0)
    assert not game.maze.exit.is_activated  # eggs remain
    kill(game.eggs)
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_a_boss_on_any_level_locks_the_exit(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, static=2))
    start(game, 7)
    assert not game.maze.exit.is_activated
    assert game.hunter is None


def test_restarting_a_boss_level_locks_the_exit_again(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert game.maze.exit.is_activated
    start(game, 6)
    assert not game.maze.exit.is_activated


def test_an_ordinary_level_has_an_open_exit(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=3))
    start(game, 3)  # before the hunter's first level, so no pilot is started
    assert game.maze.exit.is_activated
