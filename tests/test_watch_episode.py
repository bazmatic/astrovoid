import json

from tools import ppo_neural as ppo
from tools.watch_episode import episode_jobs


def run_dir(tmp_path):
    config = {'episode': {'episodes_per_iteration': 24, 'levels': [1, 2, 3], 'rules_share': 0.05},
              'start': 'start.npz', 'shaping': {'horizon': 60.0, 'panic_score': -50.0},
              'decision_frames': 6, 'turn_rate': 1.0}
    (tmp_path / 'config.json').write_text(json.dumps(config))
    return tmp_path


def test_an_iterations_episodes_are_the_ones_training_flew(tmp_path):
    run = run_dir(tmp_path)
    jobs, shaping = episode_jobs(run, 7)
    expected = ppo.make_jobs(7, 24, run / 'iter0006.npz', 6, 1.0, 0.05, (1, 2, 3))
    assert [(l, s, spec) for l, s, spec in jobs] == expected
    assert shaping == {'horizon': 60.0, 'panic_score': -50.0}


def test_the_first_iteration_flies_the_runs_starting_model(tmp_path):
    jobs, _ = episode_jobs(run_dir(tmp_path), 0)
    assert all(spec.weights == 'start.npz' for _, _, spec in jobs)
