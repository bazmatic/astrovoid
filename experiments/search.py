"""Proposes numeric rule changes: random search, then one-parameter hill-climbing."""
from dataclasses import replace
import numpy as np

from experiments.score import improves, paired_bootstrap
from hunter.rule_params import BOUNDS, DEFAULT, RuleParams


def sample_params(rng, bounds=BOUNDS, base=DEFAULT):
    """Random numbers within bounds on top of `base`, so its switches carry over."""
    return replace(base, **{name: float(rng.uniform(low, high)) for name, (low, high) in bounds.items()})


class CachedEvaluator:
    """Memoises an evaluator, so the baseline and revisited candidates cost one run each."""

    def __init__(self, evaluate):
        self._evaluate = evaluate
        self._cache = {}
        self.calls = 0

    def __call__(self, params, fidelity):
        key = (params, fidelity)
        if key not in self._cache:
            self.calls += 1
            self._cache[key] = list(self._evaluate(params, fidelity))
        return self._cache[key]


def _mean(evaluate, params, fidelity):
    return float(np.mean(evaluate(params, fidelity)))


def random_search(evaluate, baseline=DEFAULT, n=40, keep=4, seed=0):
    """The best `keep` of `n` random candidates: screened cheaply, ranked at full fidelity."""
    rng = np.random.default_rng(seed)
    candidates = [sample_params(rng, base=baseline) for _ in range(n)]
    screened = sorted(candidates, key=lambda p: _mean(evaluate, p, 'cheap'), reverse=True)[:keep]
    return sorted(screened, key=lambda p: _mean(evaluate, p, 'full'), reverse=True)


def hill_climb(evaluate, start, step=0.15, max_sweeps=3, seed=0, bounds=BOUNDS, confidence=0.99):
    """Try each parameter up and down by `step`; keep a move only if it clearly improves.

    Dozens of moves are tried, so each must clear a stricter interval than a single comparison.
    """
    rng = np.random.default_rng(seed)
    current, log = start, []
    names = list(bounds)
    for _ in range(max_sweeps):
        moved = False
        for name in rng.permutation(names):
            name = str(name)
            low, high = bounds[name]
            value = getattr(current, name)
            for target in (value * (1 + step), value * (1 - step)):
                target = float(min(high, max(low, target)))
                if target == value:
                    continue
                candidate = replace(current, **{name: target})
                base_scores = evaluate(current, 'full')
                new_scores = evaluate(candidate, 'full')
                mean_diff, lo, hi = paired_bootstrap(base_scores, new_scores, level=confidence)
                accepted = lo > 0
                log.append({'param': name, 'from': value, 'to': target, 'accepted': accepted,
                            'mean_diff': mean_diff, 'low': lo, 'high': hi})
                if accepted:
                    current, moved = candidate, True
                    break
        if not moved:
            break
    return current, log


def optimise(evaluate, baseline=DEFAULT, n=40, keep=4, seed=0):
    """Random search for a start, hill-climb from it, then confirm the result on fresh seeds.

    Screening picks the best of many candidates and hill-climbing makes many comparisons, so the
    final answer is only returned if it also beats the baseline on seeds nothing was chosen on
    (evaluator fidelity 'confirm'); otherwise the baseline is returned.
    """
    base_scores = evaluate(baseline, 'full')
    start = baseline
    for candidate in random_search(evaluate, baseline, n, keep, seed):
        if improves(base_scores, evaluate(candidate, 'full')):
            start = candidate
            break
    final, log = hill_climb(evaluate, start, seed=seed)
    if final == baseline:
        return baseline, log
    mean_diff, lo, hi = paired_bootstrap(evaluate(baseline, 'confirm'), evaluate(final, 'confirm'))
    confirmed = lo > 0
    log.append({'param': 'CONFIRM', 'from': None, 'to': None, 'accepted': confirmed,
                'mean_diff': mean_diff, 'low': lo, 'high': hi})
    return (final if confirmed else baseline), log
