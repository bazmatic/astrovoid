import asyncio
import json
import numpy as np
import pytest
from hunter.jev_pilot import JevPilot, PilotUnavailable, PILOT_QUESTIONS
from hunter.model import PilotObservation
from hunter.student.client import JevStudentClient, load_student_client
from hunter.student.encoder import FEATURE_NAMES
from hunter.student.network import HEADS, InvalidModel, StudentModel


def constant_model(favourites):
    """A model whose heads ignore the input and always favour one choice each."""
    n = len(FEATURE_NAMES)
    heads = {}
    for name, choices in HEADS.items():
        bias = np.zeros(len(choices), dtype=np.float32)
        bias[choices.index(favourites[name])] = 5.0
        heads[name] = (np.zeros((4, len(choices)), dtype=np.float32), bias)
    layers = ((np.zeros((n, 4), dtype=np.float32), np.zeros(4, dtype=np.float32)),)
    return StudentModel(np.zeros(n, dtype=np.float32), np.ones(n, dtype=np.float32), layers, heads)


FAVOURITES = {'turn': 'right', 'thrust': 'coast', 'fire': 'hold'}


def test_heads_follow_the_pilot_questions():
    assert set(HEADS) == {'turn', 'thrust', 'fire'}
    for name, choices in HEADS.items():
        assert choices == tuple(PILOT_QUESTIONS[name]['criteria'])


def test_predict_returns_normalised_probabilities_per_head():
    probs = constant_model(FAVOURITES).predict(np.zeros(len(FEATURE_NAMES)))
    for name, dist in probs.items():
        assert set(dist) == set(HEADS[name])
        assert sum(dist.values()) == pytest.approx(1.0)
        assert max(dist, key=dist.get) == FAVOURITES[name]


def test_student_client_answers_in_the_shape_jev_pilot_reads():
    client = JevStudentClient(constant_model(FAVOURITES))
    result = asyncio.run(client.system_one(state={}, questions=PILOT_QUESTIONS))
    assert result.choices['turn'].choice == 'right'
    assert 0.9 < result.choices['turn'].confidence <= 1.0
    assert result.choices['turn'].probabilities['right'] == result.choices['turn'].confidence


def test_jev_pilot_decides_with_the_student_client():
    client = JevStudentClient(constant_model(FAVOURITES))
    decision = asyncio.run(JevPilot(client).decide(PilotObservation(1, 0, json.dumps({}))))
    assert decision.action.turn == 1
    assert not decision.action.thrust and not decision.action.fire
    assert 0 < decision.confidence <= 1


def test_save_and_load_round_trip(tmp_path):
    model = constant_model(FAVOURITES)
    path = tmp_path / 'm.npz'
    model.save(path, metrics={'joint': 0.9})
    loaded = StudentModel.load(path)
    features = np.arange(len(FEATURE_NAMES), dtype=np.float32)
    assert loaded.predict(features) == model.predict(features)


def test_load_rejects_a_changed_feature_list(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    data = dict(np.load(path))
    data['feature_names'] = np.array(list(FEATURE_NAMES[:-1]) + ['renamed'])
    np.savez(path, **data)
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_rejects_changed_heads(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    data = dict(np.load(path))
    data['heads_json'] = np.array("{'turn': ['left']}")
    np.savez(path, **data)
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_rejects_a_truncated_file(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    path.write_bytes(path.read_bytes()[:200])
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_student_client_reports_missing_and_invalid_models(tmp_path):
    with pytest.raises(PilotUnavailable, match='missing_model'):
        load_student_client(tmp_path / 'absent.npz')
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'not a model')
    with pytest.raises(PilotUnavailable, match='invalid_model'):
        load_student_client(bad)


def test_load_student_client_loads_a_good_model(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    assert isinstance(load_student_client(path), JevStudentClient)
