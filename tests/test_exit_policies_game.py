"""Each level's exit and ammo policies in play, the hunter's levels, and the endless arena."""
import pytest

import config
import level_config


def level_file(policies=None, **enemies):
    """A loader that gives every level the same file."""
    return lambda level: {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
                          'enemies': {'static': 0, 'patrol': 0, 'aggressive': 0, 'replay': 0, 'flocker': 0,
                                      'flighthouse': 0, 'egg': 0, 'anemone': 0,
                                      'split_boss': 0, 'mother_boss': 0, **enemies},
                          **(policies or {})}


ALL_CLEARED = {'exit_policy': {'type': 'all_cleared'}}


def no_level_files(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: None)


def test_no_hunter_before_its_first_level(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(1, 6) if level_config.level_has_hunter(level)] == [4, 5]


def test_a_level_file_can_forbid_the_hunter(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'hunter': False})
    assert not level_config.level_has_hunter(9)


def test_a_level_file_can_place_a_hunter_early(monkeypatch):
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


def test_an_exit_with_no_policy_is_open_whatever_is_alive(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, egg=2))
    start(game, 6)
    assert game.maze.exit.is_activated


def test_all_cleared_holds_the_exit_until_every_enemy_is_dead(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(ALL_CLEARED, split_boss=1, replay=2))
    start(game, 3)
    assert not game.maze.exit.is_activated
    kill(game.split_bosses)
    game.update(1.0)
    assert not game.maze.exit.is_activated
    kill(game.replay_enemies)
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_type_cleared_needs_only_its_types_dead(game, monkeypatch):
    eggs_only = {'exit_policy': {'type': 'type_cleared', 'enemy_types': ['egg']}}
    monkeypatch.setattr(level_config, 'load_level_config', level_file(eggs_only, egg=2, static=2))
    start(game, 3)
    assert not game.maze.exit.is_activated
    kill(game.eggs)
    game.update(1.0)
    assert game.maze.exit.is_activated
    assert sum(enemy.active for enemy in game.enemies) == 2


def test_the_timer_waits_for_the_first_move(game, monkeypatch):
    one_second = {'exit_policy': {'type': 'timer', 'seconds': 1}}
    monkeypatch.setattr(level_config, 'load_level_config', level_file(one_second))
    start(game, 3)
    for _ in range(120):
        game.update(1.0)
    assert not game.maze.exit.is_activated
    game.player_has_moved = True
    for _ in range(61):
        game.update(1.0)
    assert game.maze.exit.is_activated


def test_the_exit_stays_open_once_opened(game, monkeypatch):
    from entities.replay_enemy_ship import ReplayEnemyShip
    monkeypatch.setattr(level_config, 'load_level_config', level_file(ALL_CLEARED, replay=1))
    start(game, 3)
    kill(game.replay_enemies)
    game.update(1.0)
    assert game.maze.exit.is_activated
    game.replay_enemies.append(ReplayEnemyShip((600.0, 400.0), game.command_recorder))
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_restarting_a_level_shuts_the_exit_and_resets_the_timer(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(ALL_CLEARED, replay=1))
    start(game, 3)
    game.player_has_moved = True
    kill(game.replay_enemies)
    game.update(1.0)
    assert game.maze.exit.is_activated and game.play_seconds > 0
    start(game, 3)
    assert not game.maze.exit.is_activated
    assert game.play_seconds == 0.0


def test_the_ammo_policy_comes_from_the_level_file(game, monkeypatch):
    unlimited = {'ammo_policy': {'type': 'unlimited'}}
    monkeypatch.setattr(level_config, 'load_level_config', level_file(unlimited))
    start(game, 3)
    assert not game.ship.ammo_policy.charges_for_shots()
    game.ship.ammo = 0
    assert game.ship.fire()
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    assert game.ship.ammo_policy.charges_for_shots()


def test_a_jev_beacon_can_lie_on_a_level_with_a_boss(game, monkeypatch):
    from entities.jev_beacon import JevBeacon
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 1)
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    assert level_config.level_allows_jev_beacon(6)
    start(game, 6)
    assert any(isinstance(crystal, JevBeacon) for crystal in game.powerup_crystals)


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


def test_a_kill_adds_to_power_but_does_not_upgrade_the_gun(game, monkeypatch):
    from entities.projectile import Projectile
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=2))
    start(game, 3)
    game.player_has_moved = True
    for enemy in game.enemies:
        game.projectiles.append(Projectile(enemy.get_pos(), 0.0))
    game.update(1.0)
    assert not any(enemy.active for enemy in game.enemies)
    assert game.ship.gun_upgrade_level == 0
    assert game.scoring.enemies_destroyed == 2


def test_a_kill_counts_on_the_games_score(game, monkeypatch):
    from entities.projectile import Projectile
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=1))
    game.reset_scoring_to_profile_state()
    start(game, 3)
    game.player_has_moved = True
    game.projectiles.append(Projectile(game.enemies[0].get_pos(), 0.0))
    game.update(1.0)
    assert game.scoring.enemies_destroyed == 1
