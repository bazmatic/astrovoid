"""Generated anemones respect maze capacity; explicit level overrides take priority."""
import level_config
from level_rules import EnemyCounts, anemones_that_fit


def test_counts_default_to_no_anemones():
    counts = EnemyCounts(total=0, static=0, patrol=0, aggressive=0, replay=0, flocker=0, flighthouse=0, egg=0)
    assert counts.anemone == 0


def test_level_file_can_override(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'enemies': {'anemone': 2}})
    assert level_config.get_level_enemy_counts(1).anemone == 2


def test_explicit_enemy_roster_without_anemones_has_none(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'static': 1}, 'maze': {'grid_size': 40}})
    assert level_config.get_level_enemy_counts(3).anemone == 0
    assert level_config.get_level_enemy_counts(9).anemone == 0


def test_small_mazes_get_fewer_than_the_schedule_asks_for(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'maze': {'grid_size': 12}})
    capacity=anemones_that_fit(12)
    monkeypatch.setattr(level_config, 'get_anemone_count', lambda level: capacity+1)
    assert level_config.get_level_anemone_count(47) == capacity
    monkeypatch.setattr(level_config, 'get_anemone_count', lambda level: 0)
    assert level_config.get_level_anemone_count(47) == 0


def test_a_level_file_number_is_taken_as_given_even_on_a_small_maze(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'anemone': 5}, 'maze': {'grid_size': 12}})
    assert level_config.get_level_anemone_count(12) == 5
    assert level_config.get_level_enemy_counts(12).anemone == 5


def test_anemones_are_not_part_of_the_regular_enemy_total(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'static': 1, 'patrol': 1, 'aggressive': 1, 'anemone': 3}})
    assert level_config.get_level_enemy_counts(1).total == 3


def test_negative_override_spawns_none(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'enemies': {'anemone': -2}})
    assert level_config.get_level_enemy_counts(9).anemone == 0


def test_larger_mazes_never_reduce_anemone_capacity():
    capacities=[anemones_that_fit(size) for size in (10,12,20,30,40)]
    assert all(type(count) is int and count>=1 for count in capacities)
    assert capacities==sorted(capacities)
    assert capacities[-1]>capacities[0]
