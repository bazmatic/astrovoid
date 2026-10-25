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
    expected = ppo.make_jobs(7, 24, run / 'iter0006.npz', 6, 1.0, (1, 2, 3))
    assert [(seed, spec) for _, seed, spec in jobs] == [(seed, spec) for _, seed, spec in expected]
    # Historical 5% Rules scheduling put the twentieth global episode on 25.
    start = 7 * 24
    assert [level for level, _, _ in jobs] == [25 if (n + 1) // 20 > n // 20 else (1, 2, 3)[n % 3]
                                               for n in range(start, start + 24)]
    assert shaping == {'horizon': 60.0, 'panic_score': -50.0}


def test_the_first_iteration_flies_the_runs_starting_model(tmp_path):
    jobs, _ = episode_jobs(run_dir(tmp_path), 0)
    assert all(spec.weights == 'start.npz' for _, _, spec in jobs)


def test_new_runs_replay_level_25_as_an_ordinary_selected_level(tmp_path):
    run = run_dir(tmp_path)
    config = json.loads((run / 'config.json').read_text())
    del config['episode']['rules_share']
    config['episode']['levels'] = [25, 26]
    (run / 'config.json').write_text(json.dumps(config))
    jobs, _ = episode_jobs(run, 7)
    assert [level for level, _, _ in jobs] == [25, 26] * 12


def test_resumed_historical_runs_replay_each_iterations_original_schedule(tmp_path):
    run = run_dir(tmp_path)
    config = json.loads((run / 'config.json').read_text())
    config['episode']['level_cycle_from_iteration'] = 8
    (run / 'config.json').write_text(json.dumps(config))
    old, _ = episode_jobs(run, 7)
    new, _ = episode_jobs(run, 8)
    assert 25 in [level for level, _, _ in old]
    assert [level for level, _, _ in new] == [1, 2, 3] * 8


def test_old_and_new_maze_seeding_replay_correctly_across_resume(tmp_path):
    run = run_dir(tmp_path)
    config = json.loads((run / 'config.json').read_text())
    config['shaping']['random_maze'] = True
    config['episode']['random_maze_from_iteration'] = 8
    (run / 'config.json').write_text(json.dumps(config))
    assert episode_jobs(run, 7)[1]['random_maze'] is False
    assert episode_jobs(run, 8)[1]['random_maze'] is True
