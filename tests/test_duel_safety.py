import pygame
import pytest

import config
from hunter.neural import loader
from hunter.neural.policy import random_policy
from tests.test_fun_menu import policy_file, to_fun  # noqa: F401 - pytest fixture
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture


def test_a_duel_leaves_the_profile_untouched(game, policy_file, tmp_path):
    path = game.profile_manager.profiles_file if hasattr(game.profile_manager, 'profiles_file') else tmp_path / 'profiles.json'
    before = path.read_bytes() if path.exists() else b''
    level, score = game.profile_manager.get_active_level(), game.scoring.get_total_score()
    to_fun(game)
    key(game, pygame.K_RETURN)
    for _ in range(5):
        game.update(1.0)
    key(game, pygame.K_ESCAPE)
    assert game.profile_manager.get_active_level() == level and game.scoring.get_total_score() == score
    assert (path.read_bytes() if path.exists() else b'') == before


def test_start_game_after_a_duel_behaves_as_before(game, policy_file):
    to_fun(game)
    key(game, pygame.K_RETURN)
    game.update(1.0)
    key(game, pygame.K_ESCAPE)
    game.state = config.STATE_PLAYING
    game.level = 1
    game.start_level()
    assert game.hunter is None and game.projectiles == [] and game.duel is None
    game.update(1.0)
    game.draw()


def test_a_corrupt_weights_file_does_not_crash_the_list(game, monkeypatch, tmp_path):
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'junk')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(bad))
    to_fun(game)
    key(game, pygame.K_RETURN)
    assert game.state == config.STATE_FUN and 'unavailable' in game.fun_menu.notice.lower()


def test_the_normal_hunters_stay_indestructible(game, policy_file):
    from hunter.model import HunterSettings
    from hunter.settings_for import hunter_settings_for
    to_fun(game)
    key(game, pygame.K_RETURN)
    key(game, pygame.K_ESCAPE)
    assert HunterSettings().indestructible and hunter_settings_for('rules').indestructible
    assert hunter_settings_for('neural').indestructible
