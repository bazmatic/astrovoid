from unittest.mock import Mock

import pytest

from entities.ship import Ship
from policies.ammo import AMMO_POLICIES, UnlimitedAmmo
from policies.registry import PolicyError


def make_ship():
    ship = Ship((100.0, 100.0))
    ship.sound_manager = Mock()
    return ship


def test_limited_ammo_runs_out():
    ship = make_ship()
    ship.ammo = 1
    assert ship.fire()
    assert ship.fire() is None


def test_unlimited_ammo_never_runs_out():
    ship = make_ship()
    ship.ammo_policy = UnlimitedAmmo()
    ship.ammo = 0
    for _ in range(5):
        assert ship.fire()
    assert ship.ammo == 0


@pytest.mark.parametrize('data', [{'type': 'limited'}, {'type': 'unlimited'}])
def test_ammo_policies_round_trip(data):
    assert AMMO_POLICIES.parse(data).to_json() == data


def test_a_bad_ammo_policy_is_refused():
    with pytest.raises(PolicyError):
        AMMO_POLICIES.parse({'type': 'lots'})


def test_the_names():
    assert AMMO_POLICIES.names() == ('limited', 'unlimited')
