# tests/test_rules_hunter_level.py
import json
from types import SimpleNamespace

import level_config
import level_rules
from policies.ammo import UnlimitedAmmo
from policies.exit import AllCleared
from game_handlers.enemy_roster import EnemyRoster


def fake_hunter(active=True):
    return SimpleNamespace(type='rules_hunter', active=active, get_pos=lambda: (5.0, 6.0), is_dying=False)


def test_the_entity_manager_tracks_rules_hunters_with_the_other_enemies():
    manager = EnemyRoster()
    alive, dead = fake_hunter(), fake_hunter(active=False)
    manager.extend([alive, dead])
    assert list(manager.alive()) == [alive]
    assert alive in manager.all() and dead in manager.all()
    assert (5.0, 6.0) in manager.positions()
    manager.clear()
    assert manager.of_kind('rules_hunter') == []


def test_level_25_has_one_rules_hunter_and_no_other_level_does():
    assert level_config.get_level_rules_hunter_count(25) == 1
    for level in (1, 12, 24, 26, 30, 36):
        assert level_config.get_level_rules_hunter_count(level) == 0


def test_level_25_must_be_cleared_with_unlimited_ammo():
    assert level_config.get_level_exit_policy(25) == AllCleared()
    assert level_config.get_level_ammo_policy(25) == UnlimitedAmmo()


def test_the_boss_rotation_after_level_25_is_unchanged():
    assert level_config.get_level_exit_policy(26) == AllCleared()       # its Neural hunter must die
    assert not level_rules.is_boss_level(29)
    assert level_rules.is_boss_level(30) and level_rules.is_boss_level(36)


def test_a_level_file_can_place_a_rules_hunter_on_any_level(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'rules_hunter': 2}} if level == 7 else None)
    assert level_config.get_level_rules_hunter_count(7) == 2


def test_the_level_25_file_matches_the_design():
    data = json.load(open('levels/25.json'))
    assert data['maze'] == {'complexity': 'complex', 'grid_size': 26}
    enemies = {name: count for name, count in data['enemies'].items() if count}
    assert enemies == {'rules_hunter': 1}
    assert data['hunter'] is False
