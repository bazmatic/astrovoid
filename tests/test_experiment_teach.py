import numpy as np
import pytest
from experiments import teach
from hunter.senses import SENSE_SIZE


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def test_an_episode_records_aligned_senses_and_labels():
    senses, labels = teach.record_episode(13, 100, decision_frames=6, horizon=6.0)
    assert senses.shape == (60, SENSE_SIZE) and senses.dtype == np.float32     # 6 s at 10 decisions a second
    assert labels.shape == (60, 3) and labels.dtype == np.int8
    assert set(np.unique(labels[:, 0])) <= {0, 1, 2} and set(np.unique(labels[:, 1:])) <= {0, 1}
    assert np.isfinite(senses).all()


def test_the_rules_pilot_actually_does_things_so_the_labels_are_not_constant():
    _, labels = teach.record_episode(14, 100, decision_frames=6, horizon=20.0)
    assert len(set(map(tuple, labels))) > 2
    assert labels[:, 1].any() and labels[:, 0].any()


def test_the_last_controls_in_each_senses_row_are_the_previous_rows_labels():
    senses, labels = teach.record_episode(13, 101, decision_frames=6, horizon=4.0)
    from hunter.senses import FEATURE_NAMES
    cols = [FEATURE_NAMES.index(n) for n in ('last_turn_left', 'last_turn_none', 'last_turn_right')]
    for t in range(1, len(labels)):
        assert int(np.argmax(senses[t, cols])) == labels[t - 1, 0]
        assert senses[t, FEATURE_NAMES.index('last_thrust')] == labels[t - 1, 1]
        assert senses[t, FEATURE_NAMES.index('last_fire')] == labels[t - 1, 2]


def test_recording_is_deterministic():
    a = teach.record_episode(13, 102, decision_frames=6, horizon=5.0)
    b = teach.record_episode(13, 102, decision_frames=6, horizon=5.0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_the_decision_rate_changes_the_number_of_steps():
    s3, _ = teach.record_episode(13, 100, decision_frames=3, horizon=4.0)
    s6, _ = teach.record_episode(13, 100, decision_frames=6, horizon=4.0)
    assert len(s3) == 2 * len(s6)


def test_labels_translate_special_commands_into_the_basic_equivalents():
    # A course turn is recorded as the left or right the ship actually performed; a burn as thrust.
    from hunter.neural.controls import TURN_LEFT, TURN_RIGHT
    recorder = teach.StepRecorder(decision_frames=2, rate=5.0)
    recorder.add_frame(rotation=-5.0, engine=False, trigger=False)
    recorder.add_frame(rotation=-5.0, engine=True, trigger=False)
    assert recorder.pending_label() == (TURN_LEFT, True, False)


def test_the_cli_writes_one_file_per_episode_and_skips_existing_ones(tmp_path):
    out = tmp_path / 'teach'
    args = ['--out', str(out), '--seeds', '100-100', '--levels', '13', '--horizon', '3', '--workers', '1']
    teach.main(args)
    files = sorted(out.glob('*.npz'))
    assert [f.name for f in files] == ['level13-seed100.npz']
    stamp = files[0].stat().st_mtime_ns
    teach.main(args)
    assert files[0].stat().st_mtime_ns == stamp
    data = np.load(files[0])
    assert data['senses'].shape[1] == SENSE_SIZE and data['labels'].shape[1] == 3
