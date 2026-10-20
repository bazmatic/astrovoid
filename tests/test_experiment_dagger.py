import numpy as np
import pytest
from experiments import dagger
from experiments.student import StudentSpec
from hunter.neural.policy import random_policy
from hunter.senses import SENSE_SIZE


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / 'p.npz'
    random_policy(0).save(path)
    return StudentSpec(weights=str(path), decision_frames=6, turn_rate=1.0)


def test_flying_and_labelling_gives_aligned_senses_and_teacher_labels(spec):
    senses, labels = dagger.fly_and_label(14, 200, spec, horizon=8.0)
    assert senses.shape[1] == SENSE_SIZE and labels.shape == (len(senses), 3)
    assert len(senses) >= 70                                       # 8 s at 10 decisions a second
    assert set(np.unique(labels[:, 0])) <= {0, 1, 2}


def test_the_run_is_deterministic(spec):
    a = dagger.fly_and_label(14, 201, spec, horizon=5.0)
    b = dagger.fly_and_label(14, 201, spec, horizon=5.0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_beta_one_executes_the_teacher_so_the_run_matches_a_teacher_flight_in_kind(spec):
    senses, labels = dagger.fly_and_label(14, 202, spec, horizon=10.0, beta=1.0)
    assert len(senses) > 50
    assert labels[:, 1].any()                                      # the teacher thrusts, so the ship moved


def test_labelling_does_not_change_the_flight(spec):
    # Same student, same episode: the score terms are identical whether or not the shadow is watching.
    from experiments.harness import run_episode
    plain = run_episode(14, 203, horizon=8.0, student=spec)
    labelled = {}

    def capture(result):
        labelled['r'] = result
    dagger.fly_and_label(14, 203, spec, horizon=8.0, on_result=capture)
    assert (plain.kills, plain.wall_hits, plain.hits_taken, round(plain.idle_seconds, 3)) == \
           (labelled['r'].kills, labelled['r'].wall_hits, labelled['r'].hits_taken,
            round(labelled['r'].idle_seconds, 3))


def test_the_cli_writes_dagger_files(tmp_path, spec):
    out = tmp_path / 'round1'
    dagger.main(['--weights', spec.weights, '--out', str(out), '--round', '1', '--seeds', '200-200',
                 '--levels', '14', '--horizon', '4', '--workers', '1'])
    files = list(out.glob('*.npz'))
    assert [f.name for f in files] == ['level14-seed200.npz']
