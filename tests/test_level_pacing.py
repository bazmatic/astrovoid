"""Generated levels remain internally consistent and bounded as difficulty increases."""
import pytest

import config
import enemy_kinds
import level_rules
from maze.config import MazeComplexity

# Cover the introductory range, multiple boss cycles, and a distant endless level.
LEVELS = (*range(1, 100), 1000, 1001)


def test_generated_rosters_have_valid_counts_and_consistent_spawner_totals():
    for level in LEVELS:
        mix = level_rules.get_enemy_mix(level)
        assert set(mix) <= set(enemy_kinds.kinds())
        assert all(type(count) is int and count >= 0 for count in mix.values())
        assert sum(mix.values()) == level_rules.get_enemy_count(level)
        counts = level_rules.get_enemy_counts(level)
        for kind, count in mix.items():
            assert getattr(counts, kind) == count
        # The spawner's regular-enemy total deliberately excludes special kinds.
        assert counts.total == counts.static + counts.patrol + counts.aggressive


def test_ordinary_levels_grow_without_exceeding_population_or_maze_limits():
    ordinary = [level for level in LEVELS if not level_rules.is_boss_level(level)]
    populations = [level_rules.get_enemy_count(level) for level in ordinary]
    sizes = [level_rules.get_maze_grid_size(level) for level in ordinary]
    assert populations == sorted(populations)
    assert all(0 < count <= config.MAX_ENEMY_COUNT for count in populations)
    assert sizes == sorted(sizes)
    assert all(0 < size <= config.MAX_MAZE_SIZE for size in sizes)
    assert all(level_rules.get_boss_counts(level) == (0, 0) for level in ordinary)


def test_boss_levels_have_bounded_boss_counts_and_open_arenas():
    bosses = [level for level in LEVELS if level_rules.is_boss_level(level)]
    assert bosses
    for level in bosses:
        split, mother = level_rules.get_boss_counts(level)
        assert type(split) is int and type(mother) is int
        assert split >= 0 and mother >= 0
        assert 0 < split + mother <= level_rules.MAX_BOSSES
        assert level_rules.get_split_boss_count(level) == split
        assert level_rules.get_mother_boss_count(level) == mother
        assert level_rules.get_maze_complexity(level) == MazeComplexity.EMPTY
        assert 0 < level_rules.get_maze_grid_size(level) <= config.MAX_MAZE_SIZE


@pytest.mark.parametrize('kind', ['patrol', 'aggressive'])
def test_mobile_enemy_speed_grows_from_base_and_respects_its_ceiling(kind):
    base = config.ENEMY_PATROL_SPEED if kind == 'patrol' else config.ENEMY_AGGRESSIVE_SPEED
    speeds = [level_rules.get_enemy_speed(level, kind) for level in LEVELS]
    assert speeds[0] == base
    assert speeds == sorted(speeds)
    assert all(base <= speed <= base * config.ENEMY_SPEED_CEILING for speed in speeds)
    assert all(level_rules.get_enemy_speed(level, 'static') == 0 for level in LEVELS)


def test_enemy_damage_grows_from_base_and_respects_its_ceiling():
    damage = [level_rules.get_enemy_damage(level) for level in LEVELS]
    assert damage[0] == config.ENEMY_DAMAGE
    assert damage == sorted(damage)
    assert all(type(value) is int and config.ENEMY_DAMAGE <= value
               <= int(config.ENEMY_DAMAGE * config.ENEMY_DAMAGE_CEILING) for value in damage)
