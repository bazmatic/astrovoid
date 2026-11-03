"""An explicit level roster can name just the kinds present; omitted kinds mean zero."""
from dataclasses import asdict

import pytest

import level_config
import level_rules


@pytest.mark.parametrize('level', [4, 12, 18, 24, 40])
@pytest.mark.parametrize('enemies', [{}, {'patrol': 2}, {'wallcrawler': 3}])
def test_explicit_roster_does_not_inherit_other_enemy_kinds(monkeypatch, level, enemies):
    monkeypatch.setattr(level_config, 'load_level_config', lambda _: {'enemies': enemies})
    counts = asdict(level_config.get_level_enemy_counts(level))
    assert counts == {name: (enemies.get('patrol', 0) if name in ('patrol', 'total') else 0)
                      for name in counts}
    for name in ('anemone', 'egg', 'split_boss', 'mother_boss', 'rules_hunter', 'neural_hunter',
                 'boss_viber', 'vibelet', 'belemnite', 'wallcrawler'):
        assert getattr(level_config, f'get_level_{name}_count')(level) == enemies.get(name, 0)


def test_missing_roster_keeps_generated_defaults(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda _: {'seed': 18})
    assert level_config.get_level_enemy_counts(18) is None
    assert level_config.get_level_egg_count(18) == level_rules.get_enemy_counts(18).egg
    assert level_config.get_level_split_boss_count(18) == level_rules.get_split_boss_count(18)
    assert level_config.get_level_mother_boss_count(18) == level_rules.get_mother_boss_count(18)
    assert level_config.get_level_wallcrawler_count(18) == level_rules.generated_wallcrawler_count(18)


def test_layout_roster_still_wins_over_the_counts_section(monkeypatch):
    data = {'maze': {'grid_size': 10}, 'enemies': {'patrol': 8},
            'layout': {'walls': [], 'start': [1, 1], 'exit': [8, 8],
                       'enemies': [{'type': 'wallcrawler', 'cell': [6, 6]}]}}
    monkeypatch.setattr(level_config, 'load_level_config', lambda _: data)
    counts = level_config.get_level_enemy_counts(11)
    assert counts.patrol == 0 and counts.total == 0
    assert level_config.get_level_wallcrawler_count(11) == 1
