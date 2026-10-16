"""Each level's exit and ammo policies, from its file or, without one, from the generation rules."""
import logging

import level_config
import level_rules
from policies.ammo import LimitedAmmo, UnlimitedAmmo
from policies.exit import AllCleared, AlwaysOpen, OpenAfterTime, TypeCleared


def file_says(monkeypatch, data):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: data)


def policies(level):
    return level_config.get_level_exit_policy(level), level_config.get_level_ammo_policy(level)


def is_generated_boss_level(level):
    return level_rules.is_boss_level(level)


def has_generated_eggs(level):
    return level_rules.get_enemy_counts(level).egg > 0


def test_a_file_without_policies_gets_the_defaults(monkeypatch):
    file_says(monkeypatch, {'seed': 1})
    assert policies(9) == (AlwaysOpen(), LimitedAmmo())


def test_a_file_names_its_policies(monkeypatch):
    file_says(monkeypatch, {'exit_policy': {'type': 'timer', 'seconds': 30}, 'ammo_policy': {'type': 'unlimited'}})
    assert policies(9) == (OpenAfterTime(30), UnlimitedAmmo())


def test_a_bad_exit_policy_warns_once_and_falls_back(monkeypatch, caplog):
    file_says(monkeypatch, {'exit_policy': {'type': 'timer', 'seconds': 'soon'}})
    with caplog.at_level(logging.WARNING):
        assert level_config.get_level_exit_policy(9) == AlwaysOpen()
        assert level_config.get_level_exit_policy(9) == AlwaysOpen()
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1 and 'Level 9' in warnings[0].getMessage()


def test_a_generated_boss_level_must_be_cleared_with_unlimited_ammo(monkeypatch):
    file_says(monkeypatch, None)
    assert policies(30) == (AllCleared(), UnlimitedAmmo())


def test_a_generated_level_with_eggs_needs_the_eggs_dead(monkeypatch):
    file_says(monkeypatch, None)
    level = next(n for n in range(27, 61) if not is_generated_boss_level(n) and has_generated_eggs(n))
    assert policies(level) == (TypeCleared(('egg',)), LimitedAmmo())


def test_a_generated_level_without_eggs_or_bosses_is_open(monkeypatch):
    file_says(monkeypatch, None)
    level = next(n for n in range(1, 61) if not is_generated_boss_level(n) and not has_generated_eggs(n))
    assert policies(level) == (AlwaysOpen(), LimitedAmmo())


def test_generated_bosses_fall_on_the_rules_boss_levels(monkeypatch):
    """Generated levels keep playing as they did when a boss made a boss level."""
    file_says(monkeypatch, None)
    for level in range(1, 121):
        bosses = (level_config.get_level_split_boss_count(level) + level_config.get_level_mother_boss_count(level)
                  + level_config.get_level_rules_hunter_count(level)
                  + level_config.get_level_neural_hunter_count(level))
        assert level_rules.is_boss_level(level) == (bosses > 0), level
