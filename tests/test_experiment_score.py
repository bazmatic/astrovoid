import math
import numpy as np
import pytest
from experiments.harness import EpisodeResult
from experiments.score import (RATE_FLOOR_SECONDS, Weights, components, improves, mean_components,
                               paired_bootstrap, score)


def result(**kw):
    base = dict(level=13, seed=0, enemies_at_start=10, elapsed=60.0, kills=6, wall_hits=3,
                hits_taken=2, idle_seconds=6.0, end='horizon')
    base.update(kw)
    return EpisodeResult(**base)


def test_components_are_per_minute_rates_and_a_fraction():
    c = components(result())
    assert c['kills_per_min'] == pytest.approx(6.0)
    assert c['wall_hits_per_min'] == pytest.approx(3.0)
    assert c['hits_taken_per_min'] == pytest.approx(2.0)
    assert c['idle_fraction'] == pytest.approx(0.1)
    assert 'died' not in c


def test_score_combines_the_components_with_the_weights():
    w = Weights(wall=1.0, hit=2.0, idle=10.0)
    assert score(result(), w) == pytest.approx(6.0 - 3.0 - 4.0 - 1.0)


def test_rates_use_a_floor_so_a_very_short_episode_is_finite():
    c = components(result(elapsed=0.5, kills=1, idle_seconds=0.0))
    assert c['kills_per_min'] == pytest.approx(1 / (RATE_FLOOR_SECONDS / 60))
    assert math.isfinite(score(result(elapsed=0.0, kills=0, wall_hits=0, hits_taken=0,
                                      idle_seconds=0.0)))


def test_a_level_with_no_enemies_scores_finitely():
    r = result(enemies_at_start=0, kills=0, elapsed=90.0, idle_seconds=70.0)
    assert math.isfinite(score(r))


def test_a_hunter_that_never_moves_scores_worse_than_a_working_one():
    idle = result(kills=0, wall_hits=0, hits_taken=0, idle_seconds=70.0, elapsed=90.0)
    working = result(kills=8, elapsed=90.0, idle_seconds=10.0)
    assert score(working) > score(idle)


def test_mean_components_averages_every_term_and_the_score():
    mean = mean_components([result(kills=6), result(kills=12)])
    assert mean['kills_per_min'] == pytest.approx(9.0)
    assert 'score' in mean


def test_bootstrap_accepts_a_planted_improvement():
    rng = np.random.default_rng(1)
    base = rng.normal(5, 2, 24)
    better = base + 0.8 + rng.normal(0, 0.2, 24)
    mean, low, high = paired_bootstrap(base, better)
    assert 0.5 < mean < 1.1 and low > 0
    assert improves(base, better)


def test_bootstrap_rejects_noise():
    rng = np.random.default_rng(2)
    base = rng.normal(5, 2, 24)
    noise = base + rng.normal(0, 0.5, 24)
    assert not improves(base, noise)
    assert not improves(base, base - 1.0)


def test_bootstrap_is_deterministic_and_checks_lengths():
    a, b = np.arange(10.0), np.arange(10.0) + 1
    assert paired_bootstrap(a, b) == paired_bootstrap(a, b)
    with pytest.raises(ValueError):
        paired_bootstrap([1, 2], [1, 2, 3])
