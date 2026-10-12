import logging
import numpy as np
import pytest
from config import SETTINGS
from hunter.neural import loader
from hunter.neural.controller import NeuralController
from hunter.neural.policy import random_policy
from hunter.settings_for import hunter_settings_for
from tests.test_hunter_powerups import game, playing


def test_the_neural_hunter_has_its_own_turn_rate_and_decision_rate():
    assert SETTINGS.game.neuralDecisionFrames == 6 and SETTINGS.game.neuralTurnRate == 1.0
    assert hunter_settings_for('neural').turn_rate_multiplier == SETTINGS.game.neuralTurnRate


def test_the_loader_returns_none_and_warns_for_a_missing_or_bad_file(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert loader.load_neural_policy(tmp_path / 'absent.npz') is None
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'junk')
    assert loader.load_neural_policy(bad) is None
    good = tmp_path / 'good.npz'
    random_policy(0).save(good)
    assert loader.load_neural_policy(good) is not None


def test_the_game_builds_a_neural_controller_for_the_neural_pilot(game, monkeypatch, tmp_path):
    good = tmp_path / 'good.npz'
    random_policy(1).save(good)
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(good))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    assert isinstance(game.hunter_controller, NeuralController)
    assert game.hunter.rotation_speed_multiplier == SETTINGS.game.neuralTurnRate
    assert game.hunter_controller.unavailable is False


def test_a_missing_policy_leaves_the_hunter_unavailable_and_still(game, monkeypatch, tmp_path):
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(tmp_path / 'absent.npz'))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    game.player_has_moved = True
    x, y = game.hunter.x, game.hunter.y
    for _ in range(30):
        game._update_hunter(1.0)
    assert game.hunter_controller.status == 'unavailable'
    assert (game.hunter.x, game.hunter.y) == (x, y)


def test_a_neural_hunter_moves_under_the_games_update_with_plain_controls(game, monkeypatch, tmp_path):
    good = tmp_path / 'good.npz'
    random_policy(2).save(good)
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(good))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    game.player_has_moved = True
    seen = []
    original = game.hunter.step
    game.hunter.step = lambda dt, action, solution=None: (seen.append(action), original(dt, action, solution))[1]
    for _ in range(60):
        game._update_hunter(1.0)
    assert seen and all(not (a.track or a.course or a.worked_burn) and a.burn_heading is None for a in seen)
