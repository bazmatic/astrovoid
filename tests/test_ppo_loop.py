import numpy as np
import pytest

pytest.importorskip('torch')

from experiments.harness import EpisodeResult
from experiments.run import TUNE_LEVELS
from hunter.neural.policy import InvalidPolicy, NeuralPolicy, random_policy
from hunter.senses import SENSE_SIZE
from tools import ppo_neural as ppo


def fake_rollout_factory():
    def rollout(jobs, workers):
        episodes = []
        for level, seed, spec in jobs:
            rng = np.random.default_rng(spec.sample_seed)
            n = 30
            episodes.append({
                'senses': rng.normal(0, 1, (n, SENSE_SIZE)).astype(np.float32),
                'controls': np.stack([rng.integers(0, 3, n), rng.integers(0, 2, n), rng.integers(0, 2, n)],
                                     axis=1).astype(np.int8),
                'rewards': rng.normal(0, 1, n).astype(np.float32),
                'result': EpisodeResult(level, seed, 5, 30.0, 1, 0, 0, 0.0, 'horizon', 0)})
        return episodes
    return rollout


def test_jobs_depend_only_on_the_iteration_and_count_not_on_the_workers():
    a = ppo.make_jobs(3, 24, 'w.npz', 6, 1.0)
    b = ppo.make_jobs(3, 24, 'w.npz', 6, 1.0)
    assert a == b and len(a) == 24
    assert all(not spec.greedy and 300 <= seed < 400 and level in TUNE_LEVELS for level, seed, spec in a)
    assert len({spec.sample_seed for _, _, spec in a}) == 24
    assert {spec.sample_seed for _, _, spec in a}.isdisjoint(
        {spec.sample_seed for _, _, spec in ppo.make_jobs(4, 24, 'w.npz', 6, 1.0)})


def test_the_kl_coefficient_fades_then_holds():
    assert ppo.kl_coefficient(0, 100) == pytest.approx(0.1)
    assert ppo.kl_coefficient(25, 100) == pytest.approx(0.06)
    assert ppo.kl_coefficient(50, 100) == pytest.approx(0.02)
    assert ppo.kl_coefficient(99, 100) == pytest.approx(0.02)


def test_a_missing_or_invalid_start_policy_stops_training(tmp_path):
    with pytest.raises(InvalidPolicy):
        ppo.train_rl(tmp_path / 'absent.npz', tmp_path / 'out', 1, rollout=fake_rollout_factory(), log=lambda *_: None)
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'junk')
    with pytest.raises(InvalidPolicy):
        ppo.train_rl(bad, tmp_path / 'out', 1, rollout=fake_rollout_factory(), log=lambda *_: None)
    assert not (tmp_path / 'out').exists() or not list((tmp_path / 'out').glob('*.npz'))


def test_the_loop_writes_loadable_checkpoints_and_keeps_the_best(tmp_path):
    start = tmp_path / 'start.npz'
    random_policy(0, hidden=16, embed=8).save(start)
    scores = iter([1.0, 3.0, 2.0])

    def gate(path):
        NeuralPolicy.load(path)
        return {'student': {'score': next(scores)}, 'passed': False}
    result = ppo.train_rl(start, tmp_path / 'out', iterations=3, episodes=6, workers=1, check_every=1,
                          rollout=fake_rollout_factory(), gate=gate, log=lambda *_: None)
    assert [p.name for p in sorted((tmp_path / 'out').glob('iter*.npz'))] == [
        'iter0000.npz', 'iter0001.npz', 'iter0002.npz']
    assert len(result['history']) == 3 and not result['passed']
    best = NeuralPolicy.load(result['best'])
    second = NeuralPolicy.load(tmp_path / 'out' / 'iter0001.npz')
    assert np.allclose(best.params['gru_w_ih'], second.params['gru_w_ih'])      # the second check scored highest


def test_it_stops_as_soon_as_the_gate_passes(tmp_path):
    start = tmp_path / 'start.npz'
    random_policy(1, hidden=16, embed=8).save(start)
    calls = []

    def gate(path):
        calls.append(path)
        return {'student': {'score': 5.0}, 'passed': len(calls) == 2}
    result = ppo.train_rl(start, tmp_path / 'out', iterations=10, episodes=6, workers=1, check_every=1,
                          rollout=fake_rollout_factory(), gate=gate, log=lambda *_: None)
    assert result['passed'] and len(result['history']) == 2


def test_the_checkpoints_are_flown_greedily_by_the_default_gate(tmp_path, monkeypatch):
    from experiments import neural_lab, run
    seen = []

    def fake_evaluate(params, level_set, seeds, horizon, workers, hide_player=True, student=None):
        seen.append(student)
        from tests.test_neural_lab import results
        return results(1.0, 2, 2, n=3)
    monkeypatch.setattr(run, 'evaluate', fake_evaluate)
    gate = ppo.make_gate(workers=1, seeds=3, decision_frames=6, turn_rate=1.0)
    report = gate(str(tmp_path / 'ckpt.npz'))
    assert seen[0] is None and seen[1].greedy and seen[1].weights == str(tmp_path / 'ckpt.npz')
    assert 'passed' in report and 'student' in report
    gate(str(tmp_path / 'again.npz'))
    assert sum(1 for s in seen if s is None) == 1              # the rules reference is flown once
