# tests/test_rules_hunter_level.py
import json
from types import SimpleNamespace

import level_config
from game_handlers.entity_manager import EntityManager


def fake_hunter(active=True):
    return SimpleNamespace(active=active, get_pos=lambda: (5.0, 6.0), is_dying=False)


def test_the_entity_manager_tracks_rules_hunters_with_the_other_enemies():
    manager = EntityManager()
    alive, dead = fake_hunter(), fake_hunter(active=False)
    manager.rules_hunters.extend([alive, dead])
    assert list(manager.get_all_active_enemies()) == [alive]
    assert alive in manager.get_all_enemies() and dead in manager.get_all_enemies()
    assert (5.0, 6.0) in manager.get_all_enemy_positions()
    manager.clear_all()
    assert manager.rules_hunters == []


def test_level_25_has_one_rules_hunter_and_no_other_level_does():
    assert level_config.get_level_rules_hunter_count(25) == 1
    for level in (1, 12, 24, 26, 30, 36):
        assert level_config.get_level_rules_hunter_count(level) == 0


def test_level_25_is_a_boss_level_without_a_jev_beacon():
    assert level_config.is_boss_level(25)
    assert not level_config.level_allows_jev_beacon(25)
    assert not level_config.level_has_hunter(25)


def test_the_boss_rotation_after_level_25_is_unchanged():
    assert not level_config.is_boss_level(26)
    assert not level_config.is_boss_level(29)
    assert level_config.is_boss_level(30) and level_config.is_boss_level(36)


def test_a_level_file_can_place_a_rules_hunter_on_any_level(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'rules_hunter': 2}} if level == 7 else None)
    assert level_config.get_level_rules_hunter_count(7) == 2
    assert level_config.is_boss_level(7)


def test_the_level_25_file_matches_the_design():
    data = json.load(open('levels/25.json'))
    assert data['maze'] == {'complexity': 'complex', 'grid_size': 26}
    enemies = {name: count for name, count in data['enemies'].items() if count}
    assert enemies == {'anemone': 3, 'rules_hunter': 1}
    assert 'hunter' not in data
