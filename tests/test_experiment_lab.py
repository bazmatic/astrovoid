import numpy as np
import pytest
from experiments import lab, run
from experiments.harness import EpisodeResult
from experiments.score import Weights, components
from hunter.rule_params import DEFAULT, RuleParams


def fake_results(n=20, seed=0):
    rng = np.random.default_rng(seed)
    return [EpisodeResult(13, i, 10, 90.0, int(rng.integers(0, 12)), int(rng.integers(0, 6)),
                          int(rng.integers(0, 4)), float(rng.uniform(0, 40)), 'horizon') for i in range(n)]


def test_baseline_weights_scale_each_penalty_to_half_the_kill_spread():
    results = fake_results()
    weights = lab.baseline_weights(results)
    rows = [components(r) for r in results]
    kill_std = np.std([r['kill_pct_per_min'] for r in rows])
    assert weights.wall == pytest.approx(0.5 * kill_std / np.std([r['wall_hits_per_min'] for r in rows]))
    assert weights.hit == pytest.approx(0.5 * kill_std / np.std([r['hits_taken_per_min'] for r in rows]))
    assert weights.idle == pytest.approx(0.5 * kill_std / np.std([r['idle_fraction'] for r in rows]))


def test_a_term_that_never_varies_keeps_the_default_weight():
    flat = [EpisodeResult(13, i, 10, 90.0, i % 5, 0, 0, 0.0, 'horizon') for i in range(10)]
    weights = lab.baseline_weights(flat)
    assert weights.wall == Weights().wall and weights.hit == Weights().hit


def test_the_evaluator_scores_the_tune_episodes_in_order(monkeypatch):
    seen = []

    def fake_evaluate(params, level_set, seeds, horizon, workers):
        seen.append((level_set, seeds, horizon, workers))
        return [EpisodeResult(l, s, 5, 30.0, l % 4, 0, 0, 0.0, 'horizon')
                for l, s in run.episode_list(level_set, seeds)]
    monkeypatch.setattr(lab.run, 'evaluate', fake_evaluate)
    evaluator = lab.make_evaluator(workers=3)
    full = evaluator(DEFAULT, 'full')
    cheap = evaluator(DEFAULT, 'cheap')
    assert len(full) == 24 and len(cheap) == 12
    assert seen == [('tune', (0, 1), 90.0, 3), ('tune', (0,), 45.0, 3)]
    assert evaluator(DEFAULT, 'full') == full


def test_unknown_fidelity_is_an_error():
    with pytest.raises(ValueError):
        lab.make_evaluator(workers=1)(DEFAULT, 'medium')
