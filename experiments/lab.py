"""The experiment loop's driver: python -m experiments.lab baseline|round1."""
import argparse
import json
import os
import numpy as np

from experiments import run
from experiments.score import Weights, components, improves, mean_components, paired_bootstrap, score
from experiments.search import CachedEvaluator, optimise
from hunter.rule_params import DEFAULT, RuleParams


def make_evaluator(workers, horizon_full=90.0, horizon_cheap=45.0, weights=None):
    weights = weights or Weights()

    def evaluate(params, fidelity):
        if fidelity == 'full':
            results = run.evaluate(params, 'tune', run.SEEDS, horizon_full, workers)
        elif fidelity == 'cheap':
            results = run.evaluate(params, 'tune', (0,), horizon_cheap, workers)
        else:
            raise ValueError(f'unknown fidelity {fidelity!r}')
        return [score(r, weights) for r in results]
    return CachedEvaluator(evaluate)


def baseline_weights(results):
    """Each penalty is weighted so its spread can swing the score by half the kill rate's spread."""
    rows = [components(r) for r in results]
    kill_std = float(np.std([row['kill_pct_per_min'] for row in rows]))
    defaults = Weights()
    chosen = {}
    for field, term in (('wall', 'wall_hits_per_min'), ('hit', 'hits_taken_per_min'),
                        ('idle', 'idle_fraction')):
        term_std = float(np.std([row[term] for row in rows]))
        chosen[field] = 0.5 * kill_std / term_std if term_std > 0 and kill_std > 0 else getattr(defaults, field)
    return Weights(**chosen)


def _report(title, results, weights):
    print(f'\n{title}')
    for key, value in mean_components(results, weights).items():
        print(f'  {key:20s} {value:8.3f}')


def baseline(workers):
    tune = run.evaluate(DEFAULT, 'tune', run.SEEDS, 90.0, workers)
    heldout = run.evaluate(DEFAULT, 'heldout', run.SEEDS, 90.0, workers)
    run.save_results(tune, run.RESULTS_DIR / 'baseline-tune.jsonl')
    run.save_results(heldout, run.RESULTS_DIR / 'baseline-heldout.jsonl')
    weights = baseline_weights(tune + heldout)
    print('proposed weights:', weights)
    _report('baseline, tune set', tune, weights)
    _report('baseline, held-out set', heldout, weights)
    rows = [components(r) for r in tune + heldout]
    print('\nspread across all baseline episodes (mean, std):')
    for key in rows[0]:
        values = [row[key] for row in rows]
        print(f'  {key:20s} {np.mean(values):8.3f} {np.std(values):8.3f}')


def round1(workers):
    weights = Weights()
    evaluator = make_evaluator(workers, weights=weights)
    best, log = optimise(evaluator)
    out = run.RESULTS_DIR / 'round1-best.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(best.to_dict(), indent=2))
    print('best parameters:', best.to_dict())
    for entry in log:
        print(('  KEPT ' if entry['accepted'] else '  tried'), entry)
    base_held = [score(r, weights) for r in run.evaluate(DEFAULT, 'heldout', run.SEEDS, 90.0, workers)]
    best_held = [score(r, weights) for r in run.evaluate(best, 'heldout', run.SEEDS, 90.0, workers)]
    mean, low, high = paired_bootstrap(base_held, best_held)
    print(f'\nheld-out, best minus baseline: {mean:+.3f} (95% interval {low:+.3f} .. {high:+.3f})')
    print('held-out improvement is real' if improves(base_held, best_held) else
          'held-out shows no clear improvement')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('baseline', 'round1'))
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    {'baseline': baseline, 'round1': round1}[args.command](args.workers)


if __name__ == '__main__':
    main()
