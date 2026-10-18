"""The stars during play follow what the player would get now, and chime when one changes."""
import config
import level_config
from rendering.ui_elements import StarIndicator
from tests.test_exit_policies_game import game, level_file, start  # noqa: F401  (the game fixture)


def indicator():
    changes = []
    stars = StarIndicator(on_star_lost=lambda: changes.append('lost'),
                          on_star_gained=lambda: changes.append('gained'))
    return stars, changes


def test_the_first_update_takes_the_stars_in_without_a_chime():
    stars, changes = indicator()
    stars.update((True, False, False, True, True))
    assert changes == [] and stars.flags == (True, False, False, True, True)


def test_each_star_that_changes_chimes_once():
    stars, changes = indicator()
    stars.update((True, False, False, True, True))
    stars.update((True, True, False, True, True))
    assert changes == ['gained']
    stars.update((True, True, False, False, False))
    assert changes == ['gained', 'lost', 'lost']


def test_no_chime_after_a_reset():
    stars, changes = indicator()
    stars.update((True,) * 5)
    stars.reset()
    stars.update((True, False, False, False, False))
    assert changes == []


def test_the_game_feeds_the_live_stars_and_chimes_a_kill(game, monkeypatch):
    from entities.projectile import Projectile
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=2))
    start(game, 3)
    assert game.star_indicator.flags == (True, False, False, True, True)
    enemy = game.enemies[0]
    game.projectiles.append(Projectile((enemy.x, enemy.y), 0.0, source='player'))
    game.update(1.0)
    assert game.star_indicator.flags[1]
    game.sound_manager.play_star_gained.assert_called()


def test_the_par_star_pulses_in_its_last_five_seconds(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=1))
    start(game, 3)
    game.base_par_seconds = 60.0
    game.play_seconds = 54.0
    assert game.par_pulse() == 0.0
    pulses = set()
    for step in range(20):
        game.play_seconds = 55.2 + step * 0.24
        pulses.add(round(game.par_pulse(), 2))
    assert len(pulses) > 3
    game.play_seconds = game.base_par_seconds + 1
    assert game.par_pulse() == 0.0
