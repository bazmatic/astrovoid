"""The designed arc, levels 1 to 24: every level has a file and the files keep the pacing rules."""
import pytest

import level_config
from level_rules import anemones_that_fit

ARC = range(1, 25)
BOSS_LEVELS = [6, 12, 18, 24]
ORDINARY = [level for level in ARC if level not in BOSS_LEVELS]
BOSSES = ('split_boss', 'mother_boss')
TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone') + BOSSES


def enemies(level):
    return level_config.load_level_config(level)['enemies']


def enemy_count(level):
    return sum(n for name, n in enemies(level).items() if name not in BOSSES)


@pytest.mark.parametrize('level', ARC)
def test_every_arc_level_has_a_complete_file(level):
    data = level_config.load_level_config(level)
    assert data is not None, f'levels/{level}.json is missing or does not parse'
    assert data['seed'] == 100 + level
    assert set(data['enemies']) == set(TYPES)
    assert all(type(n) is int and n >= 0 for n in data['enemies'].values())
    assert data['maze']['complexity'] in ('empty', 'simple', 'normal', 'complex', 'extreme')
    assert type(data['maze']['grid_size']) is int


def test_bosses_appear_only_on_the_boss_levels():
    assert [level for level in ARC if level_config.is_boss_level(level)] == BOSS_LEVELS


@pytest.mark.parametrize('level, split, mother', [(6, 1, 0), (12, 2, 0), (18, 0, 1), (24, 1, 1)])
def test_each_boss_level_has_its_bosses_in_an_open_arena(level, split, mother):
    assert (enemies(level)['split_boss'], enemies(level)['mother_boss']) == (split, mother)
    maze = level_config.load_level_config(level)['maze']
    assert maze['complexity'] == 'empty' and maze['grid_size'] <= 16


def test_at_most_one_enemy_type_is_new_on_any_level():
    seen = set()
    for level in ARC:
        new = {name for name, n in enemies(level).items() if n} - seen
        assert len(new) <= 1, f'level {level} introduces {sorted(new)}'
        seen |= new
    assert seen == set(TYPES)


def test_the_enemy_count_rises_gently_between_ordinary_levels():
    for earlier, later in zip(ORDINARY, ORDINARY[1:]):
        step = enemy_count(later) - enemy_count(earlier)
        assert -1 <= step <= 2, f'level {earlier} to {later} changes the count by {step}'


def test_the_arc_starts_small_and_ends_at_24():
    assert enemy_count(1) == 4
    assert enemy_count(23) == 24


def test_ordinary_mazes_never_shrink_and_stop_at_32():
    sizes = [level_config.get_maze_grid_size(level) for level in ORDINARY]
    assert sizes == sorted(sizes)
    assert sizes[0] == 10 and sizes[-1] == 32


@pytest.mark.parametrize('level', ARC)
def test_anemones_fit_the_maze(level):
    assert enemies(level)['anemone'] <= anemones_that_fit(level_config.get_maze_grid_size(level))


def test_the_hunter_flies_from_level_four_except_on_boss_levels():
    without = [level for level in ARC if not level_config.level_has_hunter(level)]
    assert without == [1, 2, 3] + BOSS_LEVELS
