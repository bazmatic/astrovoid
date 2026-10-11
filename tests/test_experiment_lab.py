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
    assert len(full) == 72 and len(cheap) == 24
    assert seen == [('tune', (0, 1, 2, 3, 4, 5), 90.0, 3), ('tune', (0, 1), 45.0, 3)]
    assert evaluator(DEFAULT, 'full') == full


def test_unknown_fidelity_is_an_error():
    with pytest.raises(ValueError):
        lab.make_evaluator(workers=1)(DEFAULT, 'medium')


# --- compare ------------------------------------------------------------------

def test_parse_overrides_builds_params_with_numbers_and_switches():
    params = lab.parse_overrides('steer_band_degrees=25,pursue_unaimed=true,pulse_frames=8')
    assert params.steer_band_degrees == 25.0 and params.pulse_frames == 8.0
    assert params.pursue_unaimed is True and params.investigate_memory is False
    assert lab.parse_overrides('') == DEFAULT
    assert lab.parse_overrides('investigate_memory=false').investigate_memory is False


@pytest.mark.parametrize('bad', ['steer_band_degrees', 'nope=1', 'steer_band_degrees=wide',
                                 'pursue_unaimed=maybe', 'steer_band_degrees=1e9'])
def test_parse_overrides_rejects_bad_text(bad):
    with pytest.raises(ValueError):
        lab.parse_overrides(bad)


def fake_evaluate_factory(kills_for):
    def fake_evaluate(params, level_set, seeds, horizon, workers):
        return [EpisodeResult(l, s, 10, 60.0, kills_for(params, l, s), 1, 1, 0.0, 'horizon', 0)
                for l, s in run.episode_list(level_set, seeds)]
    return fake_evaluate


def test_compare_reports_a_clear_improvement_per_term(monkeypatch):
    monkeypatch.setattr(lab.run, 'evaluate', fake_evaluate_factory(
        lambda p, l, s: 6 + (3 if p.pursue_unaimed else 0) + (l + s) % 3))
    report = lab.compare(DEFAULT, RuleParams(pursue_unaimed=True), 'tune', workers=1)
    assert report['score']['diff'] > 0 and report['score']['low'] > 0
    assert report['improves'] is True
    assert report['wall_hits_per_min']['diff'] == 0
    assert set(report) >= {'kill_pct_per_min', 'kills_per_min', 'wall_hits_per_min',
                           'hits_taken_per_min', 'idle_fraction', 'score', 'improves'}


def test_compare_does_not_call_noise_an_improvement(monkeypatch):
    monkeypatch.setattr(lab.run, 'evaluate', fake_evaluate_factory(
        lambda p, l, s: 6 + ((l * 7 + s * 3 + (1 if p.pursue_unaimed else 0)) % 5 - 2)))
    report = lab.compare(DEFAULT, RuleParams(pursue_unaimed=True), 'tune', workers=1)
    assert report['improves'] is False


def test_format_report_lists_every_term_and_the_verdict():
    report = {key: {'base': 1.0, 'candidate': 2.0, 'diff': 1.0, 'low': 0.5, 'high': 1.5}
              for key in ('kill_pct_per_min', 'kills_per_min', 'wall_hits_per_min',
                          'hits_taken_per_min', 'idle_fraction', 'score')}
    report['improves'] = True
    text = lab.format_report(report, 'tune')
    for key in ('kill_pct_per_min', 'wall_hits_per_min', 'idle_fraction', 'score'):
        assert key in text
    assert 'tune' in text and 'improvement' in text.lower()


def test_compare_uses_the_requested_number_of_seeds(monkeypatch):
    seen = []

    def fake_evaluate(params, level_set, seeds, horizon, workers):
        seen.append(tuple(seeds))
        return [EpisodeResult(l, s, 10, 60.0, 6, 1, 1, 0.0, 'horizon', 0)
                for l, s in run.episode_list(level_set, seeds)]
    monkeypatch.setattr(lab.run, 'evaluate', fake_evaluate)
    lab.compare(DEFAULT, RuleParams(investigate_memory=True), 'tune', workers=1, seeds=tuple(range(12)))
    assert seen == [tuple(range(12)), tuple(range(12))]
    lab.compare(DEFAULT, DEFAULT, 'tune', workers=1)
    assert seen[-1] == run.SEEDS
