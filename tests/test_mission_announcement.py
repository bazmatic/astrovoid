"""A level with a mission announces it in the centre of the screen until the player starts flying."""
import pytest

import config
import level_config
from policies.exit import AlwaysOpen, TypeCleared
from tests.test_replay_loop import game  # noqa: F401 - pytest fixture

EGGS = ('MISSION', 'Destroy every Egg to open the exit')


@pytest.fixture
def egg_level(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_exit_policy', lambda level: TypeCleared(('egg',)))
    game.start_level()
    game.state = config.STATE_PLAYING
    return game


def test_a_level_with_a_mission_announces_it(egg_level):
    assert egg_level.announcer.showing == EGGS


def test_the_mission_stays_while_the_player_waits(egg_level):
    for _ in range(300):
        egg_level.update(1.0)
    assert egg_level.announcer.showing == EGGS


def test_the_mission_fades_once_the_player_flies(egg_level):
    egg_level.player_has_moved = True
    for _ in range(90):
        egg_level.update(1.0)
    assert egg_level.announcer.showing is None


def test_restarting_announces_it_again(egg_level):
    egg_level.player_has_moved = True
    for _ in range(90):
        egg_level.update(1.0)
    egg_level.start_level()
    assert egg_level.announcer.showing == EGGS


def test_a_level_without_a_mission_announces_nothing(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_exit_policy', lambda level: AlwaysOpen())
    game.start_level()
    assert game.announcer.showing is None


def test_the_mission_is_drawn_without_trouble(egg_level):
    egg_level.draw()
