import json
import numpy as np
import pytest

pytest.importorskip('torch')
pytest.importorskip('sklearn')

from hunter.student.client import JevStudentClient
from hunter.student.encoder import FEATURE_NAMES
from hunter.student.network import HEADS, StudentModel
from tools import train_student as ts


def jev_rule(rng):
    """A synthetic Jev: brake first, then fight, then follow the player."""
    if rng.random() < .3:
        state = {'motion': {'brake': {'speed_state': 'too_fast'}}}
        return state, ('course', 'burn', 'hold')
    if rng.random() < .5:
        state = {'visible_contacts': [{'allegiance': 'enemy', 'distance_metres': 80,
                                       'degrees_off_nose_at_next_decision': 10.0,
                                       'aim': {'lead_degrees_off_nose': 10.0, 'on_target': False}}]}
        return state, ('track', 'coast', 'fire')
    offset = float(rng.uniform(-90, 90))
    state = {'follow_player': {'degrees_off_nose_at_next_decision': offset}}
    turn = 'left' if offset < -20 else 'right' if offset > 20 else 'none'
    return state, (turn, 'coast', 'hold')


def write_logs(directory, runs=8, per_run=60, with_probabilities=True):
    rng = np.random.default_rng(0)
    for run in range(runs):
        with open(directory / f'run{run}.jsonl', 'w') as handle:
            for _ in range(per_run):
                state, picks = jev_rule(rng)
                answers = {}
                for head, pick in zip(('turn', 'thrust', 'fire'), picks):
                    probabilities = None
                    if with_probabilities:
                        probabilities = {c: (.9 if c == pick else .1 / (len(HEADS[head]) - 1))
                                         for c in HEADS[head]}
                    answers[head] = {'choice': pick, 'confidence': .9,
                                     'probabilities': probabilities}
                handle.write(json.dumps({'run_id': f'run{run}', 'state': state,
                                         'answers': answers}) + '\n')


def test_load_records_skips_blank_and_malformed_lines(tmp_path):
    (tmp_path / 'a.jsonl').write_text('{"run_id": "a"}\n\nnot json\n{"run_id": "b"}\n')
    assert [r['run_id'] for r in ts.load_records(tmp_path)] == ['a', 'b']


def test_build_dataset_uses_probabilities_and_falls_back_to_one_hot(tmp_path):
    write_logs(tmp_path, runs=1, per_run=5)
    X, targets, run_ids = ts.build_dataset(ts.load_records(tmp_path))
    assert X.shape == (5, len(FEATURE_NAMES))
    assert set(run_ids) == {'run0'}
    for head, choices in HEADS.items():
        assert targets[head].shape == (5, len(choices))
        assert targets[head].sum(axis=1) == pytest.approx(np.ones(5))
        assert targets[head].max(axis=1) == pytest.approx(np.full(5, .9))
    other = tmp_path / 'bare'
    other.mkdir()
    write_logs(other, runs=1, per_run=5, with_probabilities=False)
    _, hard, _ = ts.build_dataset(ts.load_records(other))
    assert hard['turn'].max(axis=1) == pytest.approx(np.ones(5))


def test_build_dataset_skips_records_with_unknown_choices():
    record = {'run_id': 'r', 'state': {}, 'answers': {
        'turn': {'choice': 'warp', 'probabilities': None},
        'thrust': {'choice': 'coast', 'probabilities': None},
        'fire': {'choice': 'hold', 'probabilities': None}}}
    X, targets, run_ids = ts.build_dataset([record])
    assert len(X) == 0 and run_ids == []


def test_split_by_run_never_splits_a_run():
    run_ids = [f'r{i // 10}' for i in range(100)]
    train_idx, test_idx = ts.split_by_run(run_ids, held_out_fraction=.2, seed=1)
    assert not set(train_idx) & set(test_idx)
    assert len(train_idx) + len(test_idx) == 100
    assert {run_ids[i] for i in train_idx}.isdisjoint({run_ids[i] for i in test_idx})
    assert len(test_idx) >= 10


def test_split_needs_two_runs():
    with pytest.raises(ValueError):
        ts.split_by_run(['a'] * 5)


def test_training_beats_the_majority_baseline_on_held_out_runs(tmp_path):
    write_logs(tmp_path)
    X, targets, run_ids = ts.build_dataset(ts.load_records(tmp_path))
    train_idx, test_idx = ts.split_by_run(run_ids)
    model = ts.train(X, targets, train_idx, epochs=80)
    metrics = ts.evaluate(model, X, targets, test_idx, ts.majority_labels(targets, train_idx))
    assert metrics['joint'] > .85
    assert metrics['joint'] > metrics['majority_joint']
    tree = ts.tree_baseline(X, targets, train_idx, test_idx)
    assert set(tree) == set(HEADS)


def test_main_writes_a_model_the_client_can_load(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    write_logs(data)
    out = tmp_path / 'student.npz'
    ts.main(['--data', str(data), '--out', str(out)])
    model = StudentModel.load(out)
    assert isinstance(JevStudentClient(model), JevStudentClient)
    assert 'joint' in StudentModel.metrics(out)
