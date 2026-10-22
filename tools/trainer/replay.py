"""Replaying training episodes: an iteration's episodes, how each went, and watching one in the game window."""
import sys
from pathlib import Path

from tools.trainer.control import TrainerError, launch_process
from tools.trainer.runs import RL_ROOT

SPEEDS = (1.0, 0.5, 0.25)          # normal speed and slower


def _run_dir(root, run, iteration):
    """The run's folder, if `iteration` is one it has finished (only those have their checkpoint to fly from)."""
    path = Path(root) / str(run)
    if not str(run).startswith('run') or not path.is_dir():
        raise TrainerError(f'there is no run {run}')
    if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration < 0 \
            or not (path / f'iter{iteration:04d}.npz').exists():
        raise TrainerError(f'{run} has not finished iteration {iteration}')
    return path


def replayable(path):
    """Whether the run recorded enough to fly its episodes again (runs from before replays did not)."""
    from tools.trainer.settings import config_of
    config = config_of(Path(path)) or {}
    return 'shaping' in config and 'episode' in config


def _jobs(path, iteration):
    from tools.watch_episode import episode_jobs
    try:
        return episode_jobs(path, iteration)[0]
    except (SystemExit, KeyError, ValueError) as e:
        raise TrainerError(f'{path.name} cannot be replayed: {e}') from None


def episodes(run, iteration, root=RL_ROOT):
    """The iteration's episodes as training flew them, each with its level: quick, nothing is flown."""
    path = _run_dir(root, run, iteration)
    return [{'episode': i, 'level': level, 'seed': seed} for i, (level, seed, _) in enumerate(_jobs(path, iteration))]


def fly(run, iteration, root=RL_ROOT, workers=8):
    """The iteration's episodes flown again, with how each went. Takes a while, and slows any training."""
    from tools.watch_episode import fly_all
    path = _run_dir(root, run, iteration)
    _jobs(path, iteration)
    return [{'episode': i, 'level': level, 'panic': panic, 'return': ret, 'kills': kills, 'end': end,
             'seconds': seconds}
            for i, (level, panic, ret, kills, end, seconds) in enumerate(fly_all(path, iteration, workers))]


def watch(run, iteration, episode, speed=1.0, root=RL_ROOT, launch=None):
    """Open the episode in the game window, at `speed` (one of SPEEDS)."""
    path = _run_dir(root, run, iteration)
    count = len(_jobs(path, iteration))
    if not isinstance(episode, int) or isinstance(episode, bool) or not 0 <= episode < count:
        raise TrainerError(f'iteration {iteration} has episodes 0 to {count - 1}')
    if speed not in SPEEDS:
        raise TrainerError(f'the speed must be one of {", ".join(f"{s:g}" for s in SPEEDS)}')
    command = [sys.executable, '-m', 'tools.watch_episode', str(path), str(iteration), str(episode),
               '--speed', f'{speed:g}']
    (launch or launch_process)(command, Path(root) / 'replay.log')
    return command
