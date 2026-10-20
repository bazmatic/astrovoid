import pytest
import config
from config import SETTINGS
from hunter.model import HunterSettings
from hunter.rule_params import DEFAULT, RULES
from hunter.settings_for import hunter_settings_for
from tests.test_hunter_powerups import game   # a real Game with a level running


@pytest.mark.parametrize('mode', ['jev'])
def test_jev_keeps_the_default_hunter(mode):
    assert hunter_settings_for(mode) == HunterSettings()


def test_the_rules_pilot_gets_the_tuned_hunter():
    rules = hunter_settings_for('rules')
    assert rules.turn_rate_multiplier == RULES.turn_rate_multiplier == 2.0
    assert rules.thrust_multiplier == RULES.thrust_multiplier
    assert rules.sensor_range_fraction == RULES.sensor_range_fraction
    # Everything else about the hunter, apart from its single shots, is the shared default.
    from dataclasses import replace
    assert replace(rules, turn_rate_multiplier=HunterSettings().turn_rate_multiplier,
                   burst_size=HunterSettings().burst_size) == HunterSettings()


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


def test_the_neural_pilot_gets_its_own_turn_rate_and_nothing_else_changes():
    from dataclasses import replace
    neural = hunter_settings_for('neural')
    assert neural.turn_rate_multiplier == SETTINGS.game.neuralTurnRate
    # Its hunter can also be destroyed (test below) and fires single shots; everything else is the shared default.
    assert replace(neural, turn_rate_multiplier=HunterSettings().turn_rate_multiplier,
                   indestructible=True, health=HunterSettings().health,
                   wall_energy=HunterSettings().wall_energy,
                   burst_size=HunterSettings().burst_size) == HunterSettings()


def test_the_neural_hunter_can_be_destroyed_and_the_others_cannot():
    neural = hunter_settings_for('neural')
    assert not neural.indestructible and neural.health == SETTINGS.game.neuralHunterHealth > 0
    assert hunter_settings_for('jev').indestructible and hunter_settings_for('rules').indestructible


def test_the_rules_and_vibes_pilots_fire_one_shot_at_a_time():
    assert hunter_settings_for('rules').burst_size == 1
    assert hunter_settings_for('neural').burst_size == 1
