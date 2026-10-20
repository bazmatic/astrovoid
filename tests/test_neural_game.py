import logging
import numpy as np
import pytest
from config import SETTINGS
from hunter.neural import loader
from hunter.neural.policy import random_policy
from hunter.settings_for import hunter_settings_for
from tests.test_hunter_powerups import game  # noqa: F401 - pytest fixture


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
