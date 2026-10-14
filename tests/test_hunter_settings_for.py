import pytest
import config
from config import SETTINGS
from hunter.model import HunterSettings
from hunter.rule_params import DEFAULT, RULES
from hunter.settings_for import hunter_settings_for
from tests.test_hunter_powerups import game, playing   # a real Game with a level running


@pytest.mark.parametrize('mode', ['jev'])
def test_jev_keeps_the_default_hunter(mode):
    assert hunter_settings_for(mode) == HunterSettings()


def test_the_rules_pilot_gets_the_tuned_hunter():
    rules = hunter_settings_for('rules')
    assert rules.turn_rate_multiplier == RULES.turn_rate_multiplier == 2.0
    assert rules.thrust_multiplier == RULES.thrust_multiplier
    assert rules.sensor_range_fraction == RULES.sensor_range_fraction
    # Everything else about the hunter is the shared default.
    from dataclasses import replace
    assert replace(rules, turn_rate_multiplier=HunterSettings().turn_rate_multiplier) == HunterSettings()


def test_only_the_turn_rate_differs_between_the_rules_defaults_and_the_hunters():
    # The lab applies RuleParams to the hunter; the game applies hunter_settings_for. Any hunter
    # property that RuleParams carries must agree between them, or the lab would measure a hunter the
    # game never builds.
    rules = hunter_settings_for('rules')
    for name in ('thrust_multiplier', 'sensor_range_fraction', 'turn_rate_multiplier'):
        assert getattr(rules, name) == getattr(RULES, name), name
    assert DEFAULT.turn_rate_multiplier == HunterSettings().turn_rate_multiplier   # Jev's is unchanged


def test_an_unknown_mode_gets_the_default_hunter():
    assert hunter_settings_for('turbo') == HunterSettings()


@pytest.mark.parametrize('mode,turn', [('rules', 2.0), ('jev', 0.5)])
def test_the_game_builds_the_hunter_for_the_pilot_that_flies_it(game, monkeypatch, mode, turn):
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', mode)
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    hunter = game.hunter
    assert hunter.rotation_speed_multiplier == turn
    assert hunter.settings.turn_rate_multiplier == turn
    assert hunter.current_rotation_speed == pytest.approx(hunter.base_rotation_speed * turn)


def test_the_neural_pilot_gets_its_own_turn_rate_and_nothing_else_changes():
    from dataclasses import replace
    neural = hunter_settings_for('neural')
    assert neural.turn_rate_multiplier == SETTINGS.game.neuralTurnRate
    assert replace(neural, turn_rate_multiplier=HunterSettings().turn_rate_multiplier) == HunterSettings()
