import pygame
import pytest
from unittest.mock import Mock
import config
import level_config
from game import Game
from game_handlers.entity_manager import EntityManager
from game_handlers.spawn_manager import SpawnManager
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.collision_handler import CollisionHandler
from entities.command_recorder import CommandRecorder
from scoring.system import ScoringSystem
from maze.config import MazeComplexity
from hunter.model import PilotResult, PilotDecision, ACTIONS
from tests.test_hunter_controller import Worker


@pytest.fixture
def game(monkeypatch):
    pygame.init()
    pygame.display.set_mode((320,240))
    g = Game.__new__(Game)
    g.level = 1
    g.scoring = ScoringSystem()
    g.sound_manager = Mock()
    g.command_recorder = CommandRecorder()
    g.entity_manager = EntityManager()
    for name in ('enemies','replay_enemies','flockers','flighthouses','split_bosses','mother_bosses','babies','eggs'):
        setattr(g,name,getattr(g.entity_manager,name))
    g.spawn_manager = SpawnManager(g.entity_manager)
    g.enemy_updater = EnemyUpdater()
    g.collision_handler = CollisionHandler(g.sound_manager,g.scoring,g.command_recorder)
    g.star_indicator = Mock()
    g.hunter = g.hunter_controller = g.hunter_perception = None
    g.hunter_worker = None
    monkeypatch.setattr(level_config,'get_maze_complexity',lambda _:MazeComplexity.EMPTY)
    monkeypatch.setattr(level_config,'get_maze_grid_size',lambda _:10)
    monkeypatch.setattr(level_config,'get_level_seed',lambda _:1)
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:{'spawn_cell':[4,4]})
    yield g
    g._close_hunter()
    pygame.quit()


def test_hunter_flies_every_third_level_and_wherever_a_level_places_one(game,monkeypatch):
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:None)
    monkeypatch.setattr(config,'HUNTER_LEVEL_INTERVAL',3)
    for level in range(1,10):
        game.level = level
        game.start_level()
        assert (game.hunter is not None) == (level % 3 == 0)
    assert game.hunter_worker is not None
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:{'spawn_cell':[4,4]})
    game.level = 1
    game.start_level()
    assert game.hunter is not None
    # An invalid override still gets a hunter at a safe default cell.
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:{'spawn_cell':[-1,0]})
    game.start_level()
    assert game.hunter is not None
    monkeypatch.setattr(config,'HUNTER_LEVEL_INTERVAL',0)
    monkeypatch.setattr(level_config,'get_level_hunter_config',lambda _:None)
    game.level = 3
    game.start_level()
    assert game.hunter is None


def test_hunter_moves_only_on_decision_and_resets_on_level_restart(game):
    game.hunter_worker = Worker()
    game.start_level()
    assert game.hunter is not None
    assert game.hunter not in list(game.entity_manager.get_all_active_enemies())
    game._update_hunter(1)
    assert not game.hunter_worker.sent  # Waiting for player's first move.
    game.player_has_moved = True
    game._update_hunter(1)
    obs = game.hunter_worker.sent[-1]
    assert not game.hunter.vx
    game.hunter_worker.result = PilotResult(obs.generation,obs.snapshot_at,obs.snapshot_at,
                                            PilotDecision(ACTIONS['none_thrust_fire']))
    game._update_hunter(1)
    assert game.hunter.vx > 0
    assert any(p.source == 'hunter' for p in game.projectiles)
    old = game.hunter
    game.start_level()
    assert game.hunter is not old
    assert game.hunter.health == 3
    assert not game.hunter_perception.contacts


def test_real_update_pauses_requests_and_keeps_dead_hunter_dead(game):
    game.hunter_worker = Worker()
    game.start_level()
    game.state = config.STATE_PLAYING
    game.game_frozen = game.game_over_active = False
    game.input_handler = Mock(key_mappings={})
    game.input_handler.process_controller_input.return_value = []
    game.input_handler.is_controller_shield_pressed.return_value = False
    game.input_handler.is_controller_fire_pressed.return_value = False
    game.update(1)
    assert not game.hunter_worker.sent
    game.player_has_moved = True
    game.update(1)
    assert len(game.hunter_worker.sent) == 1
    generation = game.hunter_controller.generation
    game.state = config.STATE_QUIT_CONFIRM
    game.update(1)
    assert game.hunter_controller.generation != generation
    assert not game.hunter_worker.busy
    game.state = config.STATE_PLAYING
    game.update(1)
    assert len(game.hunter_worker.sent) == 2
    dead = game.hunter
    dead.active = False
    game.update(1)
    assert game.hunter is dead
    assert game.hunter_controller.closed
