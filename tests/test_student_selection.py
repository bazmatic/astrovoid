import sys
import pytest
from config import SETTINGS
from hunter import jev_pilot
from hunter.jev_pilot import PilotUnavailable, create_client
from hunter.student import client as student_client
from hunter.student.client import JevStudentClient
from hunter.student.recorder import RecordingJevClient
from tests.test_student_client import FAVOURITES, constant_model


@pytest.fixture
def model_file(tmp_path, monkeypatch):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    monkeypatch.setattr(student_client, 'MODEL_PATH', str(path))
    return path


@pytest.fixture
def settings(monkeypatch):
    def apply(pilot='jev', record=False):
        monkeypatch.setattr(SETTINGS.game, 'hunterPilot', pilot)
        monkeypatch.setattr(SETTINGS.game, 'recordPilotDecisions', record)
    return apply


class FakeJev:
    pass


@pytest.fixture
def fake_jev(monkeypatch):
    monkeypatch.setattr(jev_pilot, '_create_jev_client', lambda: FakeJev())


def test_defaults_keep_todays_behaviour():
    assert SETTINGS.game.hunterPilot == 'jev'
    assert SETTINGS.game.recordPilotDecisions is False


def test_jev_mode_without_key_is_unavailable(settings, monkeypatch):
    settings('jev')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    with pytest.raises(PilotUnavailable, match='missing_key'):
        create_client()


def test_student_mode_loads_the_student_even_with_a_key(settings, model_file, monkeypatch):
    settings('student')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'k')
    assert isinstance(create_client(), JevStudentClient)


def test_auto_uses_jev_when_it_is_available(settings, fake_jev):
    settings('auto')
    assert isinstance(create_client(), FakeJev)


def test_auto_falls_back_to_the_student_when_jev_is_unavailable(settings, model_file, monkeypatch):
    settings('auto')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    assert isinstance(create_client(), JevStudentClient)


def test_student_mode_without_a_model_is_unavailable(settings, tmp_path, monkeypatch):
    settings('student')
    monkeypatch.setattr(student_client, 'MODEL_PATH', str(tmp_path / 'absent.npz'))
    with pytest.raises(PilotUnavailable, match='missing_model'):
        create_client()


def test_unknown_mode_is_an_invalid_configuration(settings):
    settings('turbo')
    with pytest.raises(PilotUnavailable, match='invalid_configuration'):
        create_client()


def test_recording_wraps_jev_only(settings, fake_jev, model_file, monkeypatch, tmp_path):
    from hunter.student import recorder
    monkeypatch.setattr(recorder, 'DECISIONS_DIR', tmp_path)
    settings('jev', record=True)
    client = create_client()
    try:
        assert isinstance(client, RecordingJevClient)
        assert isinstance(client.inner, FakeJev)
    finally:
        client.sink.close()
    settings('student', record=True)
    assert isinstance(create_client(), JevStudentClient)


def test_recording_is_skipped_in_frozen_builds(settings, fake_jev, monkeypatch):
    settings('jev', record=True)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert isinstance(create_client(), FakeJev)


def test_rules_mode_needs_no_key_or_model_and_never_records(settings, monkeypatch, tmp_path):
    from hunter.rules_pilot import RulesClient
    from hunter.student import recorder
    monkeypatch.setattr(recorder, 'DECISIONS_DIR', tmp_path)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(student_client, 'MODEL_PATH', str(tmp_path / 'absent.npz'))
    settings('rules', record=True)
    assert isinstance(create_client(), RulesClient)
    assert not list(tmp_path.iterdir())
