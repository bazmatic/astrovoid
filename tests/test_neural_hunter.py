"""The Neural hunter: the neural pilot's hunter ship, flown as an enemy that hunts only the player."""
import copy
import logging

import pygame
import pytest

import level_config
from entities.hunter_ship import HunterShip
from entities.neural_hunter import NeuralHunter
from entities.rules_hunter import RulesHunter
from hunter.neural.policy import random_policy
from hunter.surroundings import ProtagonistSurroundings
import enemy_kinds
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config
from tests.test_rules_hunter import FakeGame, target, SilentWorker


def make(game=None, policy=None):
    game = game or FakeGame(target())
    return NeuralHunter((500.0, 500.0), policy or random_policy(0), ProtagonistSurroundings(game)), game


def test_it_is_an_enemy_type_a_level_can_place():
    assert 'neural_hunter' in enemy_kinds.kinds()


def test_it_is_magenta_not_the_rules_red_or_the_allied_green():
    assert NeuralHunter.COLOR not in (RulesHunter.COLOR, HunterShip.COLOR)
    red, green, blue = NeuralHunter.COLOR
    assert red > 200 and blue > 200 and green < 120


def test_it_flies_on_the_neural_pilot_and_returns_shots_for_the_game():
    hunter, _ = make()
    for _ in range(60):
        assert isinstance(hunter.fly(1.0), list)
    assert hunter.flight.controller.kind == 'neural'


def test_its_shots_are_enemy_shots():
    hunter, _ = make()
    assert all(s.is_enemy and s.source == 'enemy' for s in hunter._shots())


def test_twelve_hits_destroy_it():
    hunter, _ = make()
    assert [hunter.take_damage() for _ in range(12)] == [False] * 11 + [True]


def test_without_a_policy_it_is_drawn_but_never_flies():
    hunter = NeuralHunter((500.0, 500.0), None, ProtagonistSurroundings(FakeGame(target())))
    assert hunter.flight is None and hunter.fly(1.0) == []
    pygame.init()
    hunter.draw(pygame.Surface((800, 800)))


def test_a_copy_for_the_death_portrait_carries_no_pilot():
    hunter, _ = make()
    clone = copy.deepcopy(hunter)
    assert clone.flight is None and clone.surroundings is None and hunter.flight is not None


LAYOUT = {'walls': [], 'start': [1, 1], 'exit': [7, 7],
          'enemies': [{'type': 'neural_hunter', 'cell': [6, 2]}, {'type': 'rules_hunter', 'cell': [2, 6]}],
          'beacon': None}


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: random_policy(0))
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def test_a_layout_places_a_neural_hunter_at_its_cell(played):
    calc = played.maze.position_calculator
    neural = [h for h in played.enemy_hunters if isinstance(h, NeuralHunter)]
    assert [calc.screen_to_grid(*h.get_pos()) for h in neural] == [(6, 2)]
    assert neural[0] in list(played.roster.alive())


def test_it_hunts_only_the_player(played):
    neural = next(h for h in played.enemy_hunters if isinstance(h, NeuralHunter))
    assert neural.surroundings.enemies() == [played.ship]


def test_the_players_shots_wear_it_down(played):
    from entities.projectile import Projectile
    neural = next(h for h in played.enemy_hunters if isinstance(h, NeuralHunter))
    played.collision_handler.shoot_into(Projectile(neural.get_pos(), 0.0, source='player'), played.roster)
    assert neural.hit_points == 11


def test_the_level_flies_and_draws_it(played):
    for _ in range(30):
        played._fly_enemy_hunters(1.0)
    pygame.init()
    played.roster.draw(pygame.Surface((3840, 2160)))
    played._close_enemy_hunters()


def test_without_a_neural_model_the_level_starts_without_it(game, monkeypatch, caplog):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: None)
    game._rules_worker_factory = SilentWorker
    game.level = 3
    with caplog.at_level(logging.WARNING):
        game.start_level()
    assert not any(isinstance(h, NeuralHunter) for h in game.enemy_hunters)
    assert any(isinstance(h, RulesHunter) for h in game.enemy_hunters)
    assert 'neural' in caplog.text.lower()


def test_a_level_file_can_ask_for_neural_hunters_by_count(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
        'enemies': {'static': 1, 'patrol': 0, 'aggressive': 0, 'neural_hunter': 1}} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: random_policy(0))
    assert level_config.get_level_neural_hunter_count(3) == 1
    game.level = 3
    game.start_level()
    assert sum(isinstance(h, NeuralHunter) for h in game.enemy_hunters) == 1
