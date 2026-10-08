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


def test_killing_the_boss_does_not_open_the_exit_while_its_escort_lives(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, replay=2))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert any(ship.active for ship in game.replay_enemies)
    assert not game.maze.exit.is_activated
    kill(game.replay_enemies)
    game.update(1.0)
    assert game.maze.exit.is_activated


@pytest.mark.parametrize('escort, group', [
    ('static', 'enemies'), ('patrol', 'enemies'), ('aggressive', 'enemies'), ('replay', 'replay_enemies'),
    ('flocker', 'flockers'), ('flighthouse', 'flighthouses'), ('anemone', 'anemones')])
def test_every_kind_of_enemy_holds_a_boss_level_exit_shut(game, monkeypatch, escort, group):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, **{escort: 1}))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert not game.maze.exit.is_activated
    kill(getattr(game, group))
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_ships_and_babies_that_arrive_during_a_boss_level_hold_the_exit_shut(game, monkeypatch):
    from entities.baby import Baby
    from entities.replay_enemy_ship import ReplayEnemyShip
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    start(game, 6)
    kill(game.split_bosses)
    game.replay_enemies.append(ReplayEnemyShip((600.0, 400.0), game.command_recorder))  # as a dying boss leaves
    game.update(1.0)
    assert not game.maze.exit.is_activated
    kill(game.replay_enemies)
    game.babies.append(Baby((600.0, 400.0), game.command_recorder))  # as a hatching egg leaves
    game.update(1.0)
    assert not game.maze.exit.is_activated
    kill(game.babies)
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_enemies_do_not_hold_an_ordinary_level_exit_shut(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=2, patrol=1, replay=1))
    start(game, 3)
    assert sum(enemy.active for enemy in game.entity_manager.get_all_enemies()) == 4
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
    kill(game.split_bosses)
    game.update(1.0)
    assert not game.maze.exit.is_activated  # the two static enemies remain
    kill(game.enemies)
    game.update(1.0)
    assert game.maze.exit.is_activated


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


def interior_wall_cells(maze):
    return sum(bool(maze.grid[row][col])
               for row in range(1, maze.grid_height - 1) for col in range(1, maze.grid_width - 1))


@pytest.mark.parametrize('level', [30, 36, 42])
def test_an_endless_boss_level_is_played_in_an_open_arena(game, monkeypatch, level):
    no_level_files(monkeypatch)
    start(game, level)
    assert game.maze.grid_width == 16
    assert interior_wall_cells(game.maze) == 0


def test_a_level_without_a_file_gets_its_maze_complexity_from_the_rules(monkeypatch):
    from maze.config import MazeComplexity
    no_level_files(monkeypatch)
    assert level_config.get_maze_complexity(3) == MazeComplexity.SIMPLE
    assert level_config.get_maze_complexity(9) == MazeComplexity.NORMAL
    assert level_config.get_maze_complexity(30) == MazeComplexity.EMPTY
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'maze': {'complexity': 'nonsense'}})
    assert level_config.get_maze_complexity(9) == MazeComplexity.NORMAL


def test_ammo_never_runs_out_on_a_boss_level(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(mother_boss=3))
    start(game, 72)
    for _ in range(config.INITIAL_AMMO + 30):
        assert game.ship.fire()
    assert game.ship.ammo == config.INITIAL_AMMO


def test_ammo_still_runs_out_on_an_ordinary_level(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=3))
    start(game, 3)
    for _ in range(config.INITIAL_AMMO):
        assert game.ship.fire()
    assert game.ship.fire() is None


def test_a_boss_placed_by_a_level_file_on_any_level_gives_infinite_ammo(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    start(game, 7)
    game.ship.ammo = 0
    assert game.ship.fire()
