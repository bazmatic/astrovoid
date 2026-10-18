import pytest

import config
from scoring.par import par_seconds, route_cells


def walled_grid(*walls):
    grid = [[1] * 5 for _ in range(5)]
    for row in range(1, 4):
        for col in range(1, 4):
            grid[row][col] = 0
    for col, row in walls:
        grid[row][col] = 1
    return grid


def test_the_route_goes_round_the_walls():
    assert route_cells(walled_grid((2, 1), (2, 2)), (1, 1), (3, 1)) == 6


def test_no_route_is_none():
    assert route_cells(walled_grid((2, 1), (2, 2), (2, 3)), (1, 1), (3, 1)) is None


def test_par_adds_route_enemies_bosses_and_crystals():
    counts = {'static': 10, 'replay': 2, 'mother_boss': 1, 'egg': 1}
    assert par_seconds(2400, counts, 3) == pytest.approx(2400 / 240 + 13 * 1.2 + 6 + 3 * 0.6)


def test_a_timer_exit_sets_a_floor():
    assert par_seconds(240, {}, 0, timer_seconds=60) == 62
    assert par_seconds(4800, {}, 0, timer_seconds=5) == 20


def test_the_settings_have_the_defaults():
    game = config.SETTINGS.game
    assert (game.parSpeedShare, game.parSecondsPerEnemy, game.parSecondsPerSpawningBoss,
            game.parSecondsPerCrystal, game.parTimerMargin) == (0.5, 1.2, 6, 0.6, 2)
