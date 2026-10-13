import pytest

import config
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture
import pygame


@pytest.fixture
def summoned(game, monkeypatch):
    calls = []
    monkeypatch.setattr(game, '_summon_hunter', lambda near: calls.append(near))
    game.state = config.STATE_PLAYING
    game.start_level()
    calls.clear()                 # start_level may summon a hunter of its own
    return calls


def test_the_h_key_does_nothing_unless_the_environment_variable_is_set(game, summoned, monkeypatch):
    monkeypatch.delenv('ASTROVOID_HUNTER_HOTKEY', raising=False)
    key(game, pygame.K_h)
    assert summoned == []


def test_with_the_variable_set_h_brings_the_hunter_in_beside_the_ship(game, summoned, monkeypatch):
    monkeypatch.setenv('ASTROVOID_HUNTER_HOTKEY', '1')
    key(game, pygame.K_h)
    assert summoned == [(game.ship.x, game.ship.y)]


@pytest.mark.parametrize('value', ['', '0', 'false', 'no'])
def test_a_falsy_value_leaves_the_key_off(game, summoned, monkeypatch, value):
    monkeypatch.setenv('ASTROVOID_HUNTER_HOTKEY', value)
    key(game, pygame.K_h)
    assert summoned == []


def test_h_only_works_while_playing_a_level(game, summoned, monkeypatch):
    monkeypatch.setenv('ASTROVOID_HUNTER_HOTKEY', '1')
    game.state = config.STATE_MENU
    key(game, pygame.K_h)
    assert summoned == []


def test_with_a_beacon_waiting_in_the_level_h_collects_it_instead_of_adding_a_second_hunter(game, summoned, monkeypatch):
    from entities.jev_beacon import JevBeacon
    monkeypatch.setenv('ASTROVOID_HUNTER_HOTKEY', '1')
    beacon = JevBeacon((300.0, 250.0))
    game.powerup_crystals = [beacon]
    key(game, pygame.K_h)
    assert summoned == [(300.0, 250.0)]              # one hunter, where the beacon lay
    assert not beacon.active                         # and the beacon is used up
    key(game, pygame.K_h)
    assert summoned[-1] == (game.ship.x, game.ship.y)    # none left: the next press summons beside the ship
