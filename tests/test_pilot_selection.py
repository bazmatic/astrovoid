import pytest
from config import SETTINGS
from hunter import jev_pilot
from hunter.jev_pilot import PilotUnavailable, create_client
from hunter.rules_pilot import RulesClient


@pytest.fixture
def pilot(monkeypatch):
    def apply(mode):
        monkeypatch.setattr(SETTINGS.game, 'hunterPilot', mode)
    return apply


def test_the_default_pilot_is_jev():
    assert SETTINGS.game.hunterPilot == 'jev'


def test_jev_mode_without_a_key_is_unavailable(pilot, monkeypatch):
    pilot('jev')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    with pytest.raises(PilotUnavailable, match='missing_key'):
        create_client()


def test_jev_mode_builds_the_jev_client(pilot, monkeypatch):
    pilot('jev')
    sentinel = object()
    monkeypatch.setattr(jev_pilot, '_create_jev_client', lambda: sentinel)
    assert create_client() is sentinel


def test_rules_mode_needs_no_key_or_model(pilot, monkeypatch):
    pilot('rules')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    assert isinstance(create_client(), RulesClient)


@pytest.mark.parametrize('mode', ['student', 'auto', 'turbo', 'neural'])
def test_anything_else_is_not_a_client_mode(pilot, mode):
    pilot(mode)
    with pytest.raises(PilotUnavailable, match='invalid_configuration'):
        create_client()
