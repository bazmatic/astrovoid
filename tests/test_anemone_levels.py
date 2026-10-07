"""Anemones arrive at level 4 and build up slowly; a level file can override the number."""
import pytest

import level_config
from level_rules import EnemyCounts, anemones_that_fit, get_anemone_count, get_enemy_counts


@pytest.mark.parametrize('level, expected', [
    (1, 0), (3, 0), (4, 4), (5, 4), (6, 5), (7, 5), (8, 6), (10, 7), (12, 8), (16, 8), (50, 8)])
def test_schedule(level, expected):
    assert get_anemone_count(level) == expected
    assert get_enemy_counts(level).anemone == expected


def test_counts_default_to_no_anemones():
    counts = EnemyCounts(total=0, static=0, patrol=0, aggressive=0, replay=0, flocker=0, flighthouse=0, egg=0)
    assert counts.anemone == 0


def test_level_file_can_override(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'enemies': {'anemone': 2}})
    assert level_config.get_level_enemy_counts(1).anemone == 2


def test_level_file_without_the_key_uses_the_schedule(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'static': 1}, 'maze': {'grid_size': 40}})
    assert level_config.get_level_enemy_counts(3).anemone == 0
    assert level_config.get_level_enemy_counts(9).anemone == 6


@pytest.mark.parametrize('grid_size, expected', [(10, 1), (12, 1), (20, 4), (25, 6), (30, 9), (40, 16)])
def test_how_many_fit_depends_on_the_size_of_the_maze(grid_size, expected):
    # Their fields together cover no more than a set share of the maze
    assert anemones_that_fit(grid_size) == expected


def test_small_mazes_get_fewer_than_the_schedule_asks_for(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'maze': {'grid_size': 12}})
    assert get_anemone_count(12) == 8
    assert level_config.get_level_anemone_count(12) == 1
    assert level_config.get_level_anemone_count(2) == 0


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


def test_level_four_is_a_gentle_introduction():
    # Its level file asks for fewer than the schedule would give
    assert level_config.get_level_enemy_counts(4).anemone == 3
    assert level_config.get_level_enemy_counts(5).anemone == 4
