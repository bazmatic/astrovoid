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


def _crystal_game(monkeypatch, ship_at, hunter_at, observer=False):
    """A Game with one crystal at the origin and the ship and hunter placed; update the crystals once."""
    from unittest.mock import Mock
    import game as game_module
    from entities.powerup_crystal import PowerupCrystal
    g = game_module.Game.__new__(game_module.Game)
    g.ship = SimpleNamespace(x=ship_at[0], y=ship_at[1], radius=8, active=True, observer=observer)
    g.hunter_flight = SimpleNamespace(ship=SimpleNamespace(x=hunter_at[0], y=hunter_at[1], radius=8, active=True,
                                                           get_pos=lambda: hunter_at))
    g.ship.get_pos = lambda: ship_at
    g.powerup_crystals = [PowerupCrystal((0.0, 0.0))]
    g.collision_handler = Mock()
    g.sound_manager = Mock()
    g.scoring = Mock()
    return g


def test_a_crystal_near_the_hunter_is_drawn_towards_it(monkeypatch):
    g = _crystal_game(monkeypatch, ship_at=(900.0, 900.0), hunter_at=(40.0, 0.0))
    g._update_powerup_crystals(1.0)
    assert g.powerup_crystals[0].x > 0.0                       # moved towards the hunter


def test_a_crystal_is_drawn_to_the_nearer_of_player_and_hunter(monkeypatch):
    g = _crystal_game(monkeypatch, ship_at=(-20.0, 0.0), hunter_at=(40.0, 0.0))
    g._update_powerup_crystals(1.0)
    assert g.powerup_crystals[0].x < 0.0


def test_an_observer_does_not_draw_crystals(monkeypatch):
    g = _crystal_game(monkeypatch, ship_at=(-20.0, 0.0), hunter_at=(900.0, 900.0), observer=True)
    g._update_powerup_crystals(1.0)
    assert g.powerup_crystals[0].x == 0.0
