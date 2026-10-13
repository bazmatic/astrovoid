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


def no_gate(path):
    return {'student': {'score': 0.0}, 'passed': False}


def test_the_default_rollout_carries_the_penalty_scales(monkeypatch, tmp_path):
    seen = []

    class FakePool:
        def __init__(self, workers, shaping=None):
            seen.append(shaping)

        def __call__(self, jobs):
            return fake_rollout_factory()(jobs, 1)

        def close(self):
            seen.append('closed')
    monkeypatch.setattr(ppo, 'PoolRollout', FakePool)
    start = tmp_path / 'start.npz'
    random_policy(0, hidden=16, embed=8).save(start)
    ppo.train_rl(start, tmp_path / 'out', iterations=1, episodes=4, workers=1, check_every=99,
                 shaping={'wall_scale': 5.0, 'still_penalty': 2.0}, gate=no_gate, log=lambda *_: None)
    assert seen == [{'wall_scale': 5.0, 'still_penalty': 2.0}, 'closed']


def test_each_iteration_logs_where_its_time_went(tmp_path):
    start = tmp_path / 'start.npz'
    random_policy(0, hidden=16, embed=8).save(start)
    result = ppo.train_rl(start, tmp_path / 'out', iterations=1, episodes=4, workers=1, check_every=99,
                          rollout=fake_rollout_factory(), gate=no_gate, log=lambda *_: None)
    assert result['history'][0]['rollout_s'] >= 0 and result['history'][0]['update_s'] > 0


def _timed_job(job):
    import os
    import time
    level, seed, spec = job
    time.sleep(0.02 * (level % 3))
    return {'pid': os.getpid(), 'level': level, 'seed': seed, 'wall': 0.02 * (level % 3)}


def test_longest_first_orders_by_the_level_estimates_and_keeps_unknown_levels_first():
    jobs = [(13, 0, None), (14, 1, None), (15, 2, None), (16, 3, None)]
    order = ppo.longest_first(jobs, {13: 5.0, 14: 9.0, 15: 1.0})
    assert order == [3, 1, 0, 2]                       # level 16 is unknown: it goes first; then 9, 5, 1
    assert ppo.longest_first(jobs, {}) == [0, 1, 2, 3]  # nothing known: submission order


def test_the_pool_returns_results_in_job_order_and_reuses_its_workers():
    jobs = [(level, level * 10, None) for level in (14, 13, 15, 14, 13, 15)]
    pooled = ppo.PoolRollout(2, job=_timed_job)
    try:
        first = pooled(jobs)
        second = pooled(jobs)
    finally:
        pooled.close()
    assert [(e['level'], e['seed']) for e in first] == [(l, s) for l, s, _ in jobs]
    assert [(e['level'], e['seed']) for e in second] == [(l, s) for l, s, _ in jobs]
    assert {e['pid'] for e in first + second} <= {e['pid'] for e in first} | {e['pid'] for e in second}
    assert len({e['pid'] for e in first + second}) <= 2          # two workers, the same two both times


def test_progress_lines_are_flushed_so_a_redirected_log_shows_them(monkeypatch):
    import io
    import sys

    class Spy(io.StringIO):
        flushes = 0

        def flush(self):
            Spy.flushes += 1
    monkeypatch.setattr(sys, 'stdout', Spy())
    ppo.log_line('iteration=0')
    assert Spy.flushes >= 1


def collision_rollout(wall_hits, hits_taken):
    """Rollouts as in fake_rollout_factory, but every 30 s episode has these collision counts."""
    base = fake_rollout_factory()

    def rollout(jobs, workers):
        episodes = base(jobs, workers)
        for e in episodes:
            r = e['result']
            e['result'] = EpisodeResult(r.level, r.seed, 5, 30.0, 1, wall_hits, hits_taken, 0.0, 'horizon', 0)
        return episodes
    return rollout


def run_with(tmp_path, rollout, **kwargs):
    start = tmp_path / 'start.npz'
    if not start.exists():
        random_policy(0, hidden=16, embed=8).save(start)
    calls = []

    def gate(path):
        calls.append(path.name)
        return {'student': {'score': 5.0}, 'passed': False}
    result = ppo.train_rl(start, tmp_path / 'out', iterations=6, episodes=4, workers=1, check_every=2,
                          rollout=rollout, gate=gate, log=lambda *_: None, **kwargs)
    return result, calls


def test_the_gate_is_skipped_while_training_collisions_are_far_above_the_limits(tmp_path):
    # 4 wall hits and 4 enemy hits in 30 s is 8 a minute each: nowhere near passing
    result, calls = run_with(tmp_path, collision_rollout(4, 4))
    assert calls == ['iter0005.npz']                    # only the one final check, so a best policy exists
    assert [bool(h.get('gate_skipped')) for h in result['history']] == [False, True, False, True, False, True]
    assert result['best'] is not None


def test_the_gate_runs_on_schedule_when_collisions_are_low(tmp_path):
    result, calls = run_with(tmp_path, collision_rollout(0, 0))
    assert calls == ['iter0001.npz', 'iter0003.npz', 'iter0005.npz']


def test_without_limits_the_gate_runs_on_schedule_whatever_the_collisions(tmp_path):
    result, calls = run_with(tmp_path, collision_rollout(4, 4), gate_limits=None)
    assert calls == ['iter0001.npz', 'iter0003.npz', 'iter0005.npz']


def test_one_limit_exceeded_is_enough_to_skip(tmp_path):
    _, calls = run_with(tmp_path, collision_rollout(0, 4))               # walls fine, enemy hits 8 a minute
    assert calls == ['iter0005.npz']
