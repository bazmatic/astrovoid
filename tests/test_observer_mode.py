from types import SimpleNamespace
import pytest
import config
from entities.ship import Ship
from game_handlers.combat_targets import nearest_friendly
from scoring.system import ScoringSystem


@pytest.mark.parametrize('value,expected', [('', False), ('0', False), ('no', False), ('1', True), ('true', True)])
def test_the_observer_flag_reads_the_environment(monkeypatch, value, expected):
    monkeypatch.setenv('ASTROVOID_OBSERVER', value)
    assert config.observer_mode_enabled() is expected


def test_the_flag_is_off_when_unset(monkeypatch):
    monkeypatch.delenv('ASTROVOID_OBSERVER', raising=False)
    assert not config.observer_mode_enabled()


def test_an_observer_counts_as_shielded_without_the_shield_up():
    ship = Ship((100, 100))
    assert not ship.is_shield_active()
    ship.observer = True
    assert ship.is_shield_active() and not ship.shield_active


def test_an_observer_is_not_damaged_by_a_wall():
    ship = Ship((100, 100))
    ship.observer = True
    ship.on_wall_collision()
    assert not ship.damaged


def test_enemies_ignore_an_observer_but_still_see_the_hunter():
    enemy = SimpleNamespace(x=0, y=0)
    player = SimpleNamespace(x=1, y=0, active=True, observer=True)
    hunter = SimpleNamespace(x=50, y=0, active=True)
    assert nearest_friendly(enemy, player, hunter) is hunter
    assert nearest_friendly(enemy, player) is None


def test_an_observer_never_loses_power(monkeypatch):
    monkeypatch.delenv('NO_POWER_DRAIN', raising=False)
    monkeypatch.setenv('ASTROVOID_OBSERVER', '1')
    assert not ScoringSystem().power_drain_enabled
