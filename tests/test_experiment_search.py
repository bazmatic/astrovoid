import numpy as np
import pytest
from experiments import search
from experiments.search import CachedEvaluator, hill_climb, optimise, random_search, sample_params
from hunter.rule_params import BOUNDS, DEFAULT, RuleParams

TARGET = RuleParams(steer_band_degrees=35.0, engage_standoff_cells=2.5)


def synthetic(params, fidelity):
    """A noisy bowl with its peak at TARGET; the noise is fixed per episode index."""
    count = 6 if fidelity == 'cheap' else 24
    noise = np.random.default_rng(123).normal(0, 0.3, count)
    penalty = (((params.steer_band_degrees - TARGET.steer_band_degrees) / 30) ** 2
               + ((params.engage_standoff_cells - TARGET.engage_standoff_cells) / 2) ** 2)
    return list(10.0 - 8.0 * penalty + noise)


def test_sample_params_stays_in_bounds_and_is_reproducible():
    rng = np.random.default_rng(0)
    for _ in range(50):
        params = sample_params(rng)
        for name, (low, high) in BOUNDS.items():
            assert low <= getattr(params, name) <= high
    assert sample_params(np.random.default_rng(5)) == sample_params(np.random.default_rng(5))


def test_cached_evaluator_calls_the_scorer_once_per_key():
    calls = []

    def scorer(params, fidelity):
        calls.append((params, fidelity))
        return [1.0, 2.0]
    cached = CachedEvaluator(scorer)
    assert cached(DEFAULT, 'full') == cached(DEFAULT, 'full')
    cached(DEFAULT, 'cheap')
    assert cached.calls == 2 and len(calls) == 2


def test_random_search_returns_the_best_candidates_first():
    best = random_search(CachedEvaluator(synthetic), n=60, keep=3, seed=1)
    assert len(best) == 3
    means = [np.mean(synthetic(p, 'full')) for p in best]
    assert means == sorted(means, reverse=True)
    assert means[0] > np.mean(synthetic(DEFAULT, 'full')) - 1.0


def test_hill_climb_moves_towards_the_peak_and_logs_every_try():
    evaluate = CachedEvaluator(synthetic)
    final, log = hill_climb(evaluate, DEFAULT, step=0.2, max_sweeps=4, seed=0)
    assert abs(final.steer_band_degrees - 35) < abs(DEFAULT.steer_band_degrees - 35)
    assert any(entry['accepted'] for entry in log)
    assert all({'param', 'from', 'to', 'accepted', 'mean_diff', 'low', 'high'} <= set(entry)
               for entry in log)


def test_hill_climb_rejects_changes_that_are_only_noise():
    def flat(params, fidelity):
        rng = np.random.default_rng(abs(hash(params)) % (2 ** 32))
        return list(5.0 + rng.normal(0, 0.5, 24))
    final, log = hill_climb(CachedEvaluator(flat), DEFAULT, step=0.2, max_sweeps=2, seed=0)
    # Each try has a 2.5% chance of passing on noise alone; allow for a couple.
    assert sum(entry['accepted'] for entry in log) <= 2


def test_hill_climb_respects_bounds():
    def always_better_higher(params, fidelity):
        return [params.steer_band_degrees] * 24
    final, _ = hill_climb(CachedEvaluator(always_better_higher), DEFAULT, step=0.5, max_sweeps=10)
    assert final.steer_band_degrees == BOUNDS['steer_band_degrees'][1]


def test_optimise_improves_on_the_baseline_and_keeps_a_log():
    final, log = optimise(CachedEvaluator(synthetic), n=40, keep=3, seed=2)
    assert np.mean(synthetic(final, 'full')) > np.mean(synthetic(DEFAULT, 'full'))
    assert log


def test_optimise_keeps_the_baseline_when_nothing_beats_it():
    final, log = optimise(CachedEvaluator(lambda p, f: [1.0] * 24), n=10, keep=2, seed=0)
    assert final == DEFAULT


# --- review fixes ---------------------------------------------------------------

def test_sampled_candidates_keep_the_baselines_switches():
    from hunter.rule_params import RULES
    rng = np.random.default_rng(0)
    for _ in range(20):
        assert sample_params(rng, base=RULES).investigate_memory is True
        assert sample_params(rng).investigate_memory is False


def test_random_search_candidates_carry_the_baselines_switches():
    from hunter.rule_params import RULES
    seen = []

    def evaluate(params, fidelity):
        seen.append(params.investigate_memory)
        return [1.0] * 6
    random_search(CachedEvaluator(evaluate), baseline=RULES, n=8, keep=2, seed=0)
    assert seen and all(seen)


def test_hill_climb_uses_a_stricter_interval_than_a_single_comparison():
    base = np.array([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
    nudge = base + np.array([0.9, 1.0, 0.1, 0.9, 1.0, 0.1, 0.9, 1.0])
    from experiments.score import paired_bootstrap
    assert paired_bootstrap(base, nudge, level=0.95)[1] > 0
    assert paired_bootstrap(base, nudge, level=0.999)[1] < paired_bootstrap(base, nudge, level=0.95)[1]


def test_confirmation_on_fresh_seeds_rejects_a_screening_fluke():
    calls = []

    def evaluate(params, fidelity):
        calls.append(fidelity)
        if fidelity == 'confirm':
            return [5.0] * 24            # on fresh seeds nothing beats the baseline
        return [5.0 + (3.0 if params != DEFAULT else 0.0)] * 24   # but screening loved everything
    final, _ = optimise(CachedEvaluator(evaluate), n=6, keep=2, seed=0)
    assert 'confirm' in calls
    assert final == DEFAULT


def test_confirmation_accepts_a_candidate_that_also_wins_on_fresh_seeds():
    def evaluate(params, fidelity):
        gain = (params.steer_band_degrees - DEFAULT.steer_band_degrees) / 10.0
        rng = np.random.default_rng(4)
        return list(5.0 + gain + rng.normal(0, 0.05, 24))
    final, _ = optimise(CachedEvaluator(evaluate), n=40, keep=3, seed=1)
    assert final.steer_band_degrees > DEFAULT.steer_band_degrees
