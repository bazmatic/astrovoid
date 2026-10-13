import numpy as np
import pytest
from experiments import rollout
from experiments.score import score
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
    return StudentSpec(weights=str(path), decision_frames=6, turn_rate=1.0, greedy=False, sample_seed=1)


def test_a_rollout_has_aligned_senses_controls_and_rewards(spec):
    r = rollout.fly_rollout(14, 300, spec, horizon=10.0)
    assert r['senses'].shape[1] == SENSE_SIZE and r['senses'].dtype == np.float32
    assert len(r['senses']) == len(r['controls']) == len(r['rewards']) >= 90     # 10 s at 10 decisions a second
    assert r['controls'].shape[1] == 3 and set(np.unique(r['controls'][:, 0])) <= {0, 1, 2}


def test_the_rewards_add_up_to_the_lab_score_times_minutes(spec):
    r = rollout.fly_rollout(14, 300, spec, horizon=50.0)
    result = r['result']
    assert result.elapsed >= 45.0          # the lab's floor on short episodes does not apply
    assert float(r['rewards'].sum()) == pytest.approx(score(result) * result.elapsed / 60.0, rel=1e-4, abs=1e-3)


def test_collisions_and_idling_cost_and_kills_pay(spec):
    r = rollout.fly_rollout(14, 300, spec, horizon=50.0)
    result = r['result']
    if result.kills == 0:
        assert not (r['rewards'] > 0).any()              # nothing pays without a kill
    if result.wall_impulse == 0 and result.hits_taken == 0 and result.idle_seconds == 0 and result.kills == 0:
        assert not r['rewards'].any()                    # nothing happened, nothing earned
    assert (r['rewards'] < 0).any() or result.kills > 0 or not (
        result.wall_hits or result.hits_taken or result.idle_seconds)


def test_a_rollout_is_reproducible_and_the_sample_seed_changes_it(spec):
    a = rollout.fly_rollout(14, 301, spec, horizon=8.0)
    b = rollout.fly_rollout(14, 301, spec, horizon=8.0)
    assert np.array_equal(a['controls'], b['controls']) and np.array_equal(a['rewards'], b['rewards'])
    other = StudentSpec(weights=spec.weights, greedy=False, sample_seed=2)
    c = rollout.fly_rollout(14, 301, other, horizon=8.0)
    assert not np.array_equal(a['controls'], c['controls'])


def test_a_greedy_spec_is_unchanged_by_the_sample_seed(tmp_path):
    path = tmp_path / 'g.npz'
    random_policy(3).save(path)
    one = rollout.fly_rollout(14, 301, StudentSpec(weights=str(path), sample_seed=1), horizon=6.0)
    two = rollout.fly_rollout(14, 301, StudentSpec(weights=str(path), sample_seed=2), horizon=6.0)
    assert np.array_equal(one['controls'], two['controls'])


def test_the_weights_file_is_not_modified_by_flying(spec):
    before = open(spec.weights, 'rb').read()
    rollout.fly_rollout(14, 301, spec, horizon=4.0)
    assert open(spec.weights, 'rb').read() == before


def test_a_wall_scale_multiplies_only_the_wall_penalty(spec):
    plain = rollout.fly_rollout(14, 300, spec, horizon=50.0)
    heavy = rollout.fly_rollout(14, 300, spec, horizon=50.0, wall_scale=5.0)
    assert heavy['result'] == plain['result']                          # flying is unchanged
    from experiments.score import Weights
    extra = 4.0 * Weights().quotient * plain['result'].wall_impulse
    assert float(plain['rewards'].sum() - heavy['rewards'].sum()) == pytest.approx(extra, rel=1e-4, abs=1e-3)


def test_a_hit_scale_multiplies_only_the_enemy_hit_penalty(spec):
    plain = rollout.fly_rollout(14, 300, spec, horizon=50.0)
    heavy = rollout.fly_rollout(14, 300, spec, horizon=50.0, hit_scale=5.0)
    assert heavy['result'] == plain['result']
    from experiments.score import Weights
    extra = 4.0 * Weights().hit * plain['result'].hits_taken
    assert float(plain['rewards'].sum() - heavy['rewards'].sum()) == pytest.approx(extra, rel=1e-4, abs=1e-3)


class _Counter:
    kills = wall_impulse = hits_taken = spawned = 0
    idle_seconds = 0.0


def _fly_frames(recorder, speeds, max_speed=10.0):
    """Feed the recorder one decision step of frames at the given speeds (no events happen)."""
    from types import SimpleNamespace
    recorder._start_enemies = 1
    for frame, speed in enumerate(speeds):
        controller = SimpleNamespace(frames=frame, last_controls=(1, 0, 0))
        game = SimpleNamespace(hunter_controller=controller)
        hunter = SimpleNamespace(vx=speed, vy=0.0, max_speed=max_speed)
        recorder.before_frame(game, hunter)
        recorder.counted(_Counter(), frame / 60.0)
        if frame == 0:
            recorder.senses.append(np.zeros(SENSE_SIZE, np.float32))
        recorder.after_frame()
    return recorder.arrays()[2]


def test_near_motionless_frames_cost_the_still_penalty_per_second():
    recorder = rollout.RolloutRecorder(6, still_penalty=3.0, still_speed=0.15)
    rewards = _fly_frames(recorder, [0.0, 0.5, 1.4, 1.6, 5.0, 9.0])       # 3 frames under 15% of 10
    assert rewards[0] == pytest.approx(-3.0 * 3 / 60.0)


def test_moving_hunters_and_the_default_pay_no_still_penalty():
    assert _fly_frames(rollout.RolloutRecorder(6, still_penalty=3.0), [5.0] * 6)[0] == 0.0
    assert _fly_frames(rollout.RolloutRecorder(6), [0.0] * 6)[0] == 0.0
