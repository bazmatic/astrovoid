"""The player starts a level with clear space around the ship, and enemy fire range stops growing."""
import math
import random

import pytest

import config
import level_config
import level_rules
from maze import Maze

LATE_LEVEL = 40


@pytest.fixture(autouse=True)
def real_display_size(monkeypatch):
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)


def late_maze(seed):
    random.seed(seed)
    return Maze(LATE_LEVEL, complexity=level_rules.get_maze_complexity(LATE_LEVEL),
                grid_size=level_rules.get_maze_grid_size(LATE_LEVEL))


@pytest.mark.parametrize("seed", range(10))
def test_no_spawn_position_inside_the_start_clearance(seed):
    maze = late_maze(seed)

    positions = maze.get_valid_spawn_positions(60, start_clearance=config.ENEMY_START_CLEARANCE)

    nearest = min(math.dist(pos, maze.start_pos) for pos in positions)
    assert nearest >= config.ENEMY_START_CLEARANCE


@pytest.mark.parametrize("seed", range(10))
def test_start_clearance_still_leaves_room_for_every_enemy(seed):
    maze = late_maze(seed)

    positions = maze.get_valid_spawn_positions(60, start_clearance=config.ENEMY_START_CLEARANCE)

    assert len(positions) == 60


def test_start_clearance_does_not_widen_the_gap_between_enemies():
    maze = late_maze(0)

    positions = maze.get_valid_spawn_positions(60, start_clearance=config.ENEMY_START_CLEARANCE)

    closest_pair = min(math.dist(a, b) for i, a in enumerate(positions) for b in positions[i + 1:])
    assert closest_pair < config.ENEMY_START_CLEARANCE


def test_start_clearance_is_wider_than_the_spacing_between_enemies():
    assert config.ENEMY_START_CLEARANCE > 100


def test_fire_range_still_grows_through_the_early_levels():
    early = level_rules.get_enemy_fire_range(config.TUTORIAL_LEVELS + 1)
    later = level_rules.get_enemy_fire_range(config.TUTORIAL_LEVELS + 5)

    assert config.ENEMY_FIRE_RANGE == early < later < config.ENEMY_MAX_FIRE_RANGE


@pytest.mark.parametrize("level", [20, 30, 40, 100])
def test_fire_range_stops_at_the_cap_on_late_levels(level):
    assert level_rules.get_enemy_fire_range(level) == config.ENEMY_MAX_FIRE_RANGE


@pytest.fixture
def game(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import pygame
    from game import Game
    from profiles import ProfileManager

    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
    monkeypatch.delenv('START_LEVEL', raising=False)
    manager = ProfileManager(tmp_path / 'profiles.json')
    monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
    monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
    monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: False)
    game = Game(screen)
    yield game
    game._close_hunter()


@pytest.mark.parametrize("level", [20, 30, 40])
def test_a_late_level_starts_with_no_enemy_inside_the_start_clearance(game, level):
    game.level = level

    game.start_level()

    enemies = list(game.entity_manager.get_all_enemies())
    nearest = min(math.dist(enemy.get_pos(), game.maze.start_pos) for enemy in enemies)
    assert nearest >= config.ENEMY_START_CLEARANCE
