"""Runs seeded hunter episodes in parallel: python -m experiments.run."""
import argparse
import json
import multiprocessing
import os
import time
from dataclasses import asdict
from pathlib import Path

from experiments.harness import EpisodeResult
from experiments.score import mean_components
from hunter.rule_params import DEFAULT, RULES, RuleParams

TUNE_LEVELS = (13, 14, 15, 17, 19, 20, 22, 25, 26, 27, 18, 30)
HELDOUT_LEVELS = (16, 21, 23, 28, 29, 24)
SEEDS = (0, 1, 2, 3, 4, 5)
LEVEL_SETS = {'tune': TUNE_LEVELS, 'heldout': HELDOUT_LEVELS}
RESULTS_DIR = Path(__file__).resolve().parents[1] / '.astrovoid-local' / 'experiments'


class EpisodeError(RuntimeError):
    """An episode crashed; the message names it."""


def episode_list(level_set, seeds=SEEDS):
    return [(level, seed) for level in LEVEL_SETS[level_set] for seed in seeds]


def _use_dummy_drivers():
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'


def _episode(level, seed, params, horizon):
    from experiments.harness import run_episode
    return run_episode(level, seed, params, horizon)


def _run_one(args):
    level, seed, params_dict, horizon = args
    params = RuleParams(**params_dict)
    try:
        return _episode(level, seed, params, horizon)
    except Exception as exc:
        raise EpisodeError(
            f'level {level} seed {seed} params {params_dict}: {type(exc).__name__}: {exc}') from None


def evaluate(params=DEFAULT, level_set='tune', seeds=SEEDS, horizon=90.0, workers=1):
    jobs = [(level, seed, params.to_dict(), horizon) for level, seed in episode_list(level_set, seeds)]
    if workers <= 1:
        return [_run_one(job) for job in jobs]
    context = multiprocessing.get_context('spawn')
    with context.Pool(workers, initializer=_use_dummy_drivers) as pool:
        return pool.map(_run_one, jobs, chunksize=1)


def save_results(results, path):
    """Write JSONL via a temporary file, so an interrupted run never leaves a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(temporary, 'w', encoding='utf-8') as handle:
            for result in results:
                handle.write(json.dumps(asdict(result)) + '\n')
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_results(path):
    with open(path, encoding='utf-8') as handle:
        return [EpisodeResult(**json.loads(line)) for line in handle if line.strip()]


def load_params(path):
    if path is None:
        return RULES
    return RuleParams.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params')
    parser.add_argument('--set', default='tune', choices=sorted(LEVEL_SETS))
    parser.add_argument('--seeds', type=int, default=len(SEEDS))
    parser.add_argument('--horizon', type=float, default=90.0)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    _use_dummy_drivers()
    params = load_params(args.params)
    started = time.perf_counter()
    results = evaluate(params, args.set, tuple(range(args.seeds)), args.horizon, args.workers)
    out = Path(args.out) if args.out else RESULTS_DIR / f'{time.strftime("%Y%m%d-%H%M%S")}-{args.set}.jsonl'
    save_results(results, out)
    print(f'{len(results)} episodes in {time.perf_counter() - started:.0f}s -> {out}')
    for key, value in mean_components(results).items():
        print(f'  {key:20s} {value:8.3f}')


if __name__ == '__main__':
    main()
