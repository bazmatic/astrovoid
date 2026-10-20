import pygame
import pytest
from unittest.mock import Mock
import config
import level_config
from game import Game
from profiles import ProfileManager
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.collision_handler import CollisionHandler
from entities.command_recorder import CommandRecorder
from scoring.system import ScoringSystem
from maze.config import MazeComplexity
from hunter.surroundings import GameSurroundings


@pytest.fixture
def game(monkeypatch, tmp_path):
    pygame.init()
    pygame.display.set_mode((320,240))
    g = Game.__new__(Game)
    g.level = 1
    g.profile_manager = ProfileManager(tmp_path / "profiles.json")
    g.scoring = ScoringSystem()
    g.sound_manager = Mock()
    g.command_recorder = CommandRecorder()
    g.roster = EnemyRoster()
    g.spawn_manager = SpawnManager(g.roster)
    g.enemy_updater = EnemyUpdater()
    g.collision_handler = CollisionHandler(g.sound_manager,g.scoring,g.command_recorder)
    g.star_indicator = Mock()
    g.hunter_flight = None
    g.hunter_worker = None
    g.hunter_surroundings = GameSurroundings(g)
    monkeypatch.setattr(level_config,'get_maze_complexity',lambda _:MazeComplexity.EMPTY)
    monkeypatch.setattr(level_config,'get_maze_grid_size',lambda _:10)
    monkeypatch.setattr(level_config,'get_level_seed',lambda _:1)
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:{'spawn_cell':[4,4]})
    # These tests drive the pilot worker, which only the Jev and rules pilots use
    monkeypatch.setattr(config.SETTINGS.game,'hunterPilot','jev')
    yield g
    g._close_hunter()
    pygame.quit()


