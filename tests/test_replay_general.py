"""learning.replay is task-agnostic: each task's replay hooks module rebuilds its environment, and recorded joint
actions fly again with exactly the recorded events."""
import json
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_importing_replay_imports_no_task_module():
    code = ('import sys, learning.replay, learning.tasks\n'
            'print(sorted(m for m in sys.modules if m.startswith("learning.adapters")))')
    out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == '[]'


def record_jelly_run(path, cases, horizon=2.0, iteration=0):
    """Write a run directory the way learning.run does: config.json plus one iteration's episodes file."""
    from learning.adapters import jelly_scenario as scenario
    from learning.policy import random_policy
    from learning.training import collect
    path.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(json.dumps(scenario.metadata(SimpleNamespace(opponent=path/'opponent.npz', horizon=horizon))))
    manifest['training'] = {'seed': 0}
    (path/'config.json').write_text(json.dumps(dict(task='jelly_team', manifest=manifest, shaping=manifest['rewards'],
                                                    episode={'horizon_seconds': horizon})))
    env = scenario.environment(horizon=horizon, arenas=manifest['arenas'])
    policy = random_policy(scenario.SPEC, 3, hidden=8, embed=4)
    episodes, actions = [], []
    try:
        for case in cases:
            job = dict(case); seed = job.pop('seed')
            _, events, trace = collect(env, policy, seed, job)
            episodes.append(dict(events, **case)); actions.append(list(trace))
    finally:
        env.close()
    (path/'episodes').mkdir(exist_ok=True)
    (path/'episodes'/f'iter{iteration:04d}.json').write_text(json.dumps(dict(
        iteration=iteration, policy='initial.npz', task='jelly_team', jobs=cases, episodes=episodes, actions=actions)))
    return episodes


def test_jelly_stage_1_and_stage_3_episodes_replay_exactly(tmp_path):
    from learning import replay
    cases = [dict(level=11, seed=301, team_size=1, stage=1), dict(level=11, seed=302, team_size=2, stage=3)]
    recorded = record_jelly_run(tmp_path, cases, horizon=6.0)   # long enough for the ship to kill a Jelly
    assert replay.episodes(tmp_path, 0) == [dict(episode=i, **case) for i, case in enumerate(cases)]
    rows = replay.fly(tmp_path, 0)
    assert len(rows) == 2
    for row, expected, case in zip(rows, json.loads(json.dumps(recorded)), cases):
        events = {k: v for k, v in expected.items() if k not in case}
        assert json.loads(json.dumps({k: row[k] for k in events})) == events
        assert (row['level'], row['seed']) == (case['level'], case['seed'])
        assert row['return'] == pytest.approx(sum(expected['agent_returns'].values()))
        assert row['end'] in ('horizon', 'ship_killed', 'team_dead')
    assert rows[1]['stage'] == 3 and rows[1]['jelly_deaths'] >= 1


def test_jelly_replay_detects_a_changed_action(tmp_path):
    from learning import replay
    record_jelly_run(tmp_path, [dict(level=11, seed=301, team_size=1, stage=1)])
    episodes = tmp_path/'episodes'/'iter0000.json'
    data = json.loads(episodes.read_text())
    for step in data['actions'][0]:
        step['0'] = [-v for v in step['0']]
    episodes.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='replay diverged in episode 0'):
        replay.fly(tmp_path, 0)


def test_jelly_replay_rejects_another_scenario_version(tmp_path):
    from learning import replay
    record_jelly_run(tmp_path, [dict(level=11, seed=301, team_size=1, stage=1)], horizon=.2)
    settings = json.loads((tmp_path/'config.json').read_text())
    settings['manifest']['scenario_version'] -= 1
    (tmp_path/'config.json').write_text(json.dumps(settings))
    with pytest.raises(ValueError, match='replay rules.*scenario_version'):
        replay.open_environment(tmp_path)


def test_a_task_without_replay_hooks_is_named_in_the_error(tmp_path):
    from learning import replay
    (tmp_path/'config.json').write_text(json.dumps(dict(task='hunter', manifest={})))
    with pytest.raises(ValueError, match="hunter.*open_environment"):
        replay.open_environment(tmp_path)


def test_a_hooks_module_missing_open_environment_is_named_in_the_error(tmp_path, monkeypatch):
    from learning import replay, tasks
    monkeypatch.setitem(sys.modules, 'tests._empty_replay_hooks', types.ModuleType('tests._empty_replay_hooks'))
    monkeypatch.setitem(tasks.TASKS, 'empty', tasks.Task('empty', 'tests', 'Empty', replay_module='learning.replay',
                                                         replay_hooks='tests._empty_replay_hooks'))
    (tmp_path/'config.json').write_text(json.dumps(dict(task='empty', manifest={})))
    with pytest.raises(ValueError, match="empty.*tests._empty_replay_hooks.*open_environment"):
        replay.open_environment(tmp_path)


def test_both_team_tasks_register_replay_hooks():
    from learning.tasks import task
    assert task('wallcrawler_team').replay_hooks == 'learning.adapters.crawler_replay'
    assert task('jelly_team').replay_hooks == 'learning.adapters.jelly_replay'
    assert task('jelly_team').replay().__name__ == 'learning.replay'
    assert task('hunter').replay() is None
