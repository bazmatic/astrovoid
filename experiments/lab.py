"""The experiment loop's driver: python -m experiments.lab baseline|round1."""
import argparse
import json
from pathlib import Path
import os
import numpy as np

from experiments import run
from experiments.score import Weights, components, improves, mean_components, paired_bootstrap, score
from experiments.search import CachedEvaluator, optimise
from hunter.rule_params import DEFAULT, RULES, SWITCHES, RuleParams


def make_evaluator(workers, horizon_full=90.0, horizon_cheap=45.0, weights=None):
    weights = weights or Weights()

    def evaluate(params, fidelity):
        if fidelity == 'full':
            results = run.evaluate(params, 'tune', run.SEEDS, horizon_full, workers)
        elif fidelity == 'confirm':
            # Fresh seeds, never used to choose anything: the check on screening and hill-climbing.
            fresh = tuple(range(len(run.SEEDS), 2 * len(run.SEEDS)))
            results = run.evaluate(params, 'tune', fresh, horizon_full, workers)
        elif fidelity == 'cheap':
            results = run.evaluate(params, 'tune', run.SEEDS[:2], horizon_cheap, workers)
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


def parse_overrides(text, base=DEFAULT):
    """`base` with 'name=value,name=value' applied: numbers, or true/false for the switches."""
    values = {}
    for item in filter(None, (part.strip() for part in text.split(','))):
        if '=' not in item:
            raise ValueError(f'expected name=value, got {item!r}')
        name, raw = (piece.strip() for piece in item.split('=', 1))
        if name in SWITCHES:
            if raw.lower() not in ('true', 'false'):
                raise ValueError(f'switch {name!r} must be true or false, got {raw!r}')
            values[name] = raw.lower() == 'true'
        else:
            try:
                values[name] = float(raw)
            except ValueError:
                raise ValueError(f'parameter {name!r} must be a number, got {raw!r}') from None
    return RuleParams.from_dict({**base.to_dict(), **values})


def compare(base, candidate, level_set, workers, horizon=90.0, weights=None, seeds=None):
    """Both parameter sets on the same episodes: per term, the means and the paired difference."""
    weights = weights or Weights()
    seeds = tuple(seeds) if seeds is not None else run.SEEDS
    base_results = run.evaluate(base, level_set, seeds, horizon, workers)
    candidate_results = run.evaluate(candidate, level_set, seeds, horizon, workers)
    report = {}
    keys = list(components(base_results[0])) + ['score']
    for key in keys:
        def value(result):
            return score(result, weights) if key == 'score' else components(result)[key]
        base_values = [value(r) for r in base_results]
        candidate_values = [value(r) for r in candidate_results]
        diff, low, high = paired_bootstrap(base_values, candidate_values)
        report[key] = {'base': float(np.mean(base_values)), 'candidate': float(np.mean(candidate_values)),
                       'diff': diff, 'low': low, 'high': high}
    report['improves'] = report['score']['low'] > 0
    return report


def format_report(report, level_set):
    lines = [f'{level_set} set, candidate minus base (paired 95% interval)']
    for key, row in report.items():
        if key == 'improves':
            continue
        lines.append(f'  {key:20s} {row["base"]:9.3f} -> {row["candidate"]:9.3f}   '
                     f'{row["diff"]:+8.3f}  ({row["low"]:+.3f} .. {row["high"]:+.3f})')
    lines.append('  verdict: ' + ('a real improvement (interval above zero)' if report['improves']
                                  else 'no reliable improvement'))
    return '\n'.join(lines)


def _report(title, results, weights):
    print(f'\n{title}')
    for key, value in mean_components(results, weights).items():
        print(f'  {key:20s} {value:8.3f}')


def baseline(workers, of='rules'):
    """Score the rules defaults (`rules`, the current champion) or the global ones (`default`)."""
    params = RULES if of == 'rules' else DEFAULT
    tune = run.evaluate(params, 'tune', run.SEEDS, 90.0, workers)
    heldout = run.evaluate(params, 'heldout', run.SEEDS, 90.0, workers)
    run.save_results(tune, run.RESULTS_DIR / f'baseline-{of}-tune.jsonl')
    run.save_results(heldout, run.RESULTS_DIR / f'baseline-{of}-heldout.jsonl')
    weights = baseline_weights(tune + heldout)
    print('proposed weights:', weights)
    _report(f'baseline ({of}), tune set', tune, weights)
    _report(f'baseline ({of}), held-out set', heldout, weights)
    rows = [components(r) for r in tune + heldout]
    print('\nspread across all baseline episodes (mean, std):')
    for key in rows[0]:
        values = [row[key] for row in rows]
        print(f'  {key:20s} {np.mean(values):8.3f} {np.std(values):8.3f}')


def finish_round1(best, base_held, best_held, out_dir):
    """Write the best parameters only if the held-out levels agree that they beat the baseline."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mean, low, high = paired_bootstrap(base_held, best_held)
    adopt = low > 0
    print(f'\nheld-out, best minus baseline: {mean:+.3f} (95% interval {low:+.3f} .. {high:+.3f})')
    path = out_dir / ('round1-best.json' if adopt else 'round1-rejected.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(best.to_dict(), indent=2))
    os.replace(temporary, path)
    print(('held-out improvement is real: wrote ' if adopt else
           'held-out shows no clear improvement: NOT adopted, wrote ') + str(path))
    return adopt


def round1(workers):
    weights = Weights()
    evaluator = make_evaluator(workers, weights=weights)
    best, log = optimise(evaluator, baseline=RULES)
    print('best parameters:', best.to_dict())
    for entry in log:
        print(('  KEPT ' if entry['accepted'] else '  tried'), entry)
    base_held = [score(r, weights) for r in run.evaluate(RULES, 'heldout', run.SEEDS, 90.0, workers)]
    best_held = [score(r, weights) for r in run.evaluate(best, 'heldout', run.SEEDS, 90.0, workers)]
    finish_round1(best, base_held, best_held, run.RESULTS_DIR)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('baseline', 'round1', 'compare'))
    parser.add_argument('--baseline-of', default='rules', choices=('rules', 'default'),
                        help='baseline: the rules defaults (current champion) or the global defaults')
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--candidate', default='', help='compare: name=value,... applied on the rules defaults')
    parser.add_argument('--base', default='', help='compare: overrides for the base (default: the rules defaults)')
    parser.add_argument('--seeds', type=int, default=len(run.SEEDS),
                        help='compare: seeds per level (more seeds detect smaller effects)')
    parser.add_argument('--set', default='tune', choices=('tune', 'heldout', 'both'),
                        help='compare: which level set (heldout is for the final check only)')
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    if args.command == 'compare':
        base, candidate = parse_overrides(args.base, RULES), parse_overrides(args.candidate, RULES)
        print('base:     ', base.to_dict())
        print('candidate:', candidate.to_dict())
        for level_set in (('tune', 'heldout') if args.set == 'both' else (args.set,)):
            print(format_report(compare(base, candidate, level_set, args.workers,
                                        seeds=range(args.seeds)), level_set))
        return
    if args.command == 'baseline':
        baseline(args.workers, args.baseline_of)
    else:
        round1(args.workers)


if __name__ == '__main__':
    main()
