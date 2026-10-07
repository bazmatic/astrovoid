"""Formulas for levels that have no level file: the endless game and the safety net below it."""
import pytest

import config
import level_rules
from maze.config import MazeComplexity


def mix(level):
    return level_rules.get_enemy_mix(level)


@pytest.mark.parametrize('level, expected', [
    (25, 25), (26, 25), (27, 26), (29, 27), (31, 28), (35, 30), (47, 36), (49, 36), (1000, 36)])
def test_endless_enemy_count_rises_every_second_level_and_stops(level, expected):
    assert level_rules.get_enemy_count(level) == expected
    assert sum(mix(level).values()) == expected


def test_endless_mix_starts_from_the_end_of_the_arc():
    assert mix(25) == {'static': 4, 'patrol': 3, 'aggressive': 5, 'replay': 3, 'flocker': 3,
                       'flighthouse': 2, 'egg': 1, 'anemone': 4}


def test_endless_mix_grows_one_type_at_a_time():
    assert mix(35) == {'static': 5, 'patrol': 4, 'aggressive': 5, 'replay': 4, 'flocker': 4,
                       'flighthouse': 2, 'egg': 1, 'anemone': 5}


def test_endless_mix_at_the_cap_is_balanced():
    assert mix(47) == {'static': 6, 'patrol': 5, 'aggressive': 6, 'replay': 5, 'flocker': 5,
                       'flighthouse': 2, 'egg': 1, 'anemone': 6}
    assert mix(1000) == mix(47)


def test_enemy_counts_carry_the_mix():
    counts = level_rules.get_enemy_counts(47)
    assert (counts.static, counts.patrol, counts.aggressive) == (6, 5, 6)
    assert counts.total == 17  # static + patrol + aggressive, as the spawner expects
    assert (counts.replay, counts.flocker, counts.flighthouse, counts.egg, counts.anemone) == (5, 5, 2, 1, 6)


@pytest.mark.parametrize('level', [25, 29, 31, 47, 1001])
def test_ordinary_endless_levels_have_no_bosses(level):
    assert not level_rules.is_boss_level(level)
    assert level_rules.get_boss_counts(level) == (0, 0)


@pytest.mark.parametrize('level, split, mother', [
    (30, 2, 0), (36, 0, 1), (42, 1, 1),
    (48, 3, 0), (54, 0, 2), (60, 2, 1),
    (66, 3, 0), (72, 0, 3), (78, 2, 1), (984, 3, 0)])
def test_every_sixth_level_is_a_boss_level_and_the_bosses_build_up_to_three(level, split, mother):
    assert level_rules.is_boss_level(level)
    assert level_rules.get_boss_counts(level) == (split, mother)
    assert level_rules.get_split_boss_count(level) == split
    assert level_rules.get_mother_boss_count(level) == mother


@pytest.mark.parametrize('level, escort', [
    (30, {'flocker': 6}), (36, {'egg': 4}), (42, {'replay': 2, 'flocker': 2, 'egg': 2})])
def test_boss_levels_carry_only_their_escort(level, escort):
    assert {name: n for name, n in mix(level).items() if n} == escort
    assert level_rules.get_enemy_count(level) == sum(escort.values())


def test_boss_levels_are_small_open_arenas():
    assert level_rules.get_maze_grid_size(30) == 16
    assert level_rules.get_maze_complexity(30) == MazeComplexity.EMPTY


@pytest.mark.parametrize('level, grid, complexity', [
    (1, 10, MazeComplexity.EMPTY), (2, 12, MazeComplexity.SIMPLE), (5, 18, MazeComplexity.SIMPLE),
    (7, 22, MazeComplexity.NORMAL), (11, 30, MazeComplexity.NORMAL), (13, 32, MazeComplexity.COMPLEX),
    (17, 32, MazeComplexity.COMPLEX), (19, 32, MazeComplexity.EXTREME), (1000, 32, MazeComplexity.EXTREME)])
def test_ordinary_mazes_grow_steadily_and_stop_at_32(level, grid, complexity):
    assert level_rules.get_maze_grid_size(level) == grid
    assert level_rules.get_maze_complexity(level) == complexity


@pytest.mark.parametrize('level', [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 17, 23])
def test_an_arc_level_without_a_file_uses_only_types_already_introduced(level):
    first = {'static': 1, 'patrol': 2, 'aggressive': 3, 'replay': 5, 'anemone': 7,
             'flocker': 8, 'flighthouse': 10, 'egg': 13}
    level_mix = mix(level)
    assert sum(level_mix.values()) == min(24, 3 + level)
    assert all(level >= first[name] for name, n in level_mix.items() if n)


def test_level_one_without_a_file_is_four_static_enemies():
    assert {name: n for name, n in mix(1).items() if n} == {'static': 4}


def test_speed_grows_five_percent_a_level_and_stops_at_two_and_a_half_times():
    base = config.ENEMY_AGGRESSIVE_SPEED
    assert level_rules.get_enemy_speed(4, 'aggressive') == base
    assert level_rules.get_enemy_speed(5, 'aggressive') == base
    assert level_rules.get_enemy_speed(15, 'aggressive') == pytest.approx(base * 1.5)
    assert level_rules.get_enemy_speed(35, 'aggressive') == pytest.approx(base * 2.5)
    assert level_rules.get_enemy_speed(1000, 'aggressive') == pytest.approx(base * 2.5)
    assert level_rules.get_enemy_speed(1000, 'patrol') == pytest.approx(config.ENEMY_PATROL_SPEED * 2.5)
    assert level_rules.get_enemy_speed(1000, 'static') == 0.0


def test_damage_grows_five_percent_a_level_and_stops_at_two_and_a_half_times():
    base = config.ENEMY_DAMAGE
    assert level_rules.get_enemy_damage(4) == base
    assert level_rules.get_enemy_damage(15) == int(base * 1.5)
    assert level_rules.get_enemy_damage(35) == int(base * 2.5)
    assert level_rules.get_enemy_damage(1000) == int(base * 2.5)
