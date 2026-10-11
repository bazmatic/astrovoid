import pytest
from game_handlers.autoplay import AutoplayDirector


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def director(clock=None, first=4, last=6, limit=90):
    return AutoplayDirector(first, last, limit, clock=clock or Clock())


def test_starts_at_the_first_level():
    assert director().level == 4


def test_a_level_in_progress_has_no_end_reason():
    d = director()
    d.start_level(enemy_count=5)
    assert d.end_reason(enemies_left=5, hunter_alive=True) is None


def test_time_limit_ends_the_level():
    clock = Clock()
    d = director(clock, limit=90)
    d.start_level(enemy_count=5)
    clock.now += 89.9
    assert d.end_reason(5, True) is None
    clock.now += 0.2
    assert d.end_reason(5, True) == 'time'


def test_clearing_every_enemy_ends_the_level():
    d = director()
    d.start_level(enemy_count=3)
    assert d.end_reason(enemies_left=0, hunter_alive=True) == 'cleared'


def test_a_level_that_began_with_no_enemies_is_not_cleared_at_once():
    d = director()
    d.start_level(enemy_count=0)
    assert d.end_reason(enemies_left=0, hunter_alive=True) is None


def test_hunter_death_ends_the_level():
    d = director()
    d.start_level(enemy_count=3)
    assert d.end_reason(enemies_left=3, hunter_alive=False) == 'hunter_dead'


def test_a_level_without_a_hunter_runs_to_the_time_limit():
    clock = Clock()
    d = director(clock)
    d.start_level(enemy_count=3, hunter_present=False)
    assert d.end_reason(3, hunter_alive=False) is None
    clock.now += 91
    assert d.end_reason(3, hunter_alive=False) == 'time'


def test_start_level_restarts_the_clock():
    clock = Clock()
    d = director(clock)
    d.start_level(enemy_count=1)
    clock.now += 200
    d.start_level(enemy_count=1)
    assert d.end_reason(1, True) is None


def test_advance_steps_through_the_range_and_wraps():
    d = director(first=4, last=6)
    assert [d.advance() for _ in range(5)] == [5, 6, 4, 5, 6]
    assert d.level == 6


def test_a_single_level_range_repeats_that_level():
    d = director(first=7, last=7)
    assert d.advance() == 7


def test_inverted_range_is_rejected():
    with pytest.raises(ValueError):
        director(first=9, last=4)



# --- stuck detection ---------------------------------------------------------

def stuck_director(clock, stuck=15, limit=300):
    d = AutoplayDirector(4, 6, limit, clock=clock, stuck_seconds=stuck)
    d.start_level(enemy_count=5)
    return d


def test_a_hunter_that_finds_no_new_ground_is_stuck():
    clock = Clock()
    d = stuck_director(clock)
    assert d.end_reason(5, True, hunter_cell=(1, 1)) is None
    clock.now += 14
    assert d.end_reason(5, True, hunter_cell=(1, 2)) is None
    clock.now += 14
    assert d.end_reason(5, True, hunter_cell=(1, 1)) is None  # revisiting is not progress
    clock.now += 2
    assert d.end_reason(5, True, hunter_cell=(1, 2)) == 'stuck'


def test_reaching_new_cells_keeps_resetting_the_clock():
    clock = Clock()
    d = stuck_director(clock)
    for step in range(10):
        clock.now += 10
        assert d.end_reason(5, True, hunter_cell=(step, 0)) is None


def test_an_enemy_nearby_counts_as_progress():
    clock = Clock()
    d = stuck_director(clock)
    d.end_reason(5, True, hunter_cell=(1, 1))
    for _ in range(5):
        clock.now += 10
        assert d.end_reason(5, True, hunter_cell=(1, 1), enemy_near=True) is None
    clock.now += 16
    assert d.end_reason(5, True, hunter_cell=(1, 1), enemy_near=False) == 'stuck'


def test_no_cell_means_stuck_is_not_judged():
    clock = Clock()
    d = stuck_director(clock)
    d.end_reason(5, True)
    clock.now += 100
    assert d.end_reason(5, True) is None


def test_zero_stuck_seconds_disables_the_rule():
    clock = Clock()
    d = stuck_director(clock, stuck=0)
    d.end_reason(5, True, hunter_cell=(1, 1))
    clock.now += 200
    assert d.end_reason(5, True, hunter_cell=(1, 1)) is None


def test_start_level_forgets_the_ground_already_covered():
    clock = Clock()
    d = stuck_director(clock)
    d.end_reason(5, True, hunter_cell=(1, 1))
    clock.now += 14
    d.start_level(enemy_count=5)
    clock.now += 14
    assert d.end_reason(5, True, hunter_cell=(1, 1)) is None

# --- Game integration -------------------------------------------------------

import pygame
from unittest.mock import Mock
import config
import level_config
from config import SETTINGS


@pytest.fixture
def make_game(tmp_path, monkeypatch):
    from game import Game
    from profiles import ProfileManager
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
    monkeypatch.delenv('START_LEVEL', raising=False)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'jev')
    monkeypatch.setattr(SETTINGS.autoplay, 'firstLevel', 4)
    monkeypatch.setattr(SETTINGS.autoplay, 'lastLevel', 6)
    monkeypatch.setattr(SETTINGS.autoplay, 'timeLimitSeconds', 90)
    monkeypatch.setattr(SETTINGS.autoplay, 'stuckSeconds', 0)
    manager = ProfileManager(tmp_path / 'profiles.json')
    monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
    monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
    monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: False)
    games = []

    def make(autoplay=True):
        if autoplay:
            monkeypatch.setenv('AUTOPLAY', '1')
        else:
            monkeypatch.delenv('AUTOPLAY', raising=False)
        game = Game(screen)
        games.append(game)
        return game
    make.profiles = tmp_path / 'profiles.json'
    yield make
    for game in games:
        game._close_hunter()
        if game.hunter_worker is not None:
            game.hunter_worker.close()
            game.hunter_worker.join(2)
    pygame.quit()


def test_autoplay_is_off_by_default(make_game):
    game = make_game(autoplay=False)
    assert game.autoplay is None
    assert game.state != config.STATE_PLAYING


def test_autoplay_starts_playing_at_once_with_a_hunter(make_game):
    game = make_game()
    assert game.state == config.STATE_PLAYING
    assert game.level == 4
    assert game.hunter is not None and game.hunter.active
    assert game.player_has_moved


def test_the_parked_player_never_moves(make_game):
    game = make_game()
    start = (game.ship.x, game.ship.y)
    for _ in range(30):
        game.update(1.0)
    assert (game.ship.x, game.ship.y) == pytest.approx(start, abs=1.0)


def test_time_limit_advances_to_the_next_level_without_touching_the_profile(make_game):
    game = make_game()
    before = make_game.profiles.read_bytes() if make_game.profiles.exists() else None
    clock = Mock(return_value=game.autoplay._started_at + 91)
    game.autoplay.clock = clock
    game.update(1.0)
    assert game.level == 5
    assert game.state == config.STATE_PLAYING
    assert game.hunter is not None
    after = make_game.profiles.read_bytes() if make_game.profiles.exists() else None
    assert before == after


def test_hunter_death_advances_the_level(make_game):
    game = make_game()
    game.hunter.active = False
    game.update(1.0)
    assert game.level == 5
    assert game.hunter is not None and game.hunter.active


def test_the_player_cannot_fail_the_level(make_game):
    game = make_game()
    game.scoring.calculate_current_potential_score = lambda *a, **k: {
        'potential_score': 0, 'score_percentage': 0.0}
    game.update(1.0)
    assert not game.game_frozen and not game.game_over_active
    assert game.state == config.STATE_PLAYING


def test_reaching_the_exit_does_not_end_the_level(make_game):
    game = make_game()
    game.maze.check_exit_reached = lambda *a, **k: True
    game.update(1.0)
    assert not game.exit_explosion_active
    assert game.state == config.STATE_PLAYING


def watch_player_argument(game):
    seen = []
    original = game.hunter_perception.observe

    def spy(hunter, maze, player, *args, **kwargs):
        seen.append(player)
        return original(hunter, maze, player, *args, **kwargs)
    game.hunter_perception.observe = spy
    return seen


def test_the_player_is_hidden_from_the_hunter_by_default(make_game):
    assert SETTINGS.autoplay.hidePlayer is True
    game = make_game()
    seen = watch_player_argument(game)
    game.update(1.0)
    assert seen and all(player is None for player in seen)


def test_the_player_is_visible_when_hiding_is_off(make_game, monkeypatch):
    monkeypatch.setattr(SETTINGS.autoplay, 'hidePlayer', False)
    game = make_game()
    seen = watch_player_argument(game)
    game.update(1.0)
    assert seen and all(player is game.ship for player in seen)


def test_the_player_is_always_visible_outside_autoplay(make_game):
    game = make_game(autoplay=False)
    assert game._hunter_sees_player() is True


def test_a_stuck_hunter_ends_the_level_when_the_player_is_hidden(make_game, monkeypatch):
    monkeypatch.setattr(SETTINGS.autoplay, 'stuckSeconds', 15)
    game = make_game()
    game._enemy_near_hunter = lambda: False
    now = [game.autoplay._started_at]
    game.autoplay.clock = lambda: now[0]
    game.update(1.0)
    assert game.level == 4
    now[0] += 16
    game.update(1.0)
    assert game.level == 5


def test_stuck_is_not_judged_when_the_player_is_visible(make_game, monkeypatch):
    monkeypatch.setattr(SETTINGS.autoplay, 'stuckSeconds', 15)
    monkeypatch.setattr(SETTINGS.autoplay, 'hidePlayer', False)
    game = make_game()
    now = [game.autoplay._started_at]
    game.autoplay.clock = lambda: now[0]
    game.update(1.0)
    now[0] += 60
    game.update(1.0)
    assert game.level == 4
