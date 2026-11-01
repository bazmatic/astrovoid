"""learning.replay is task-agnostic: each task's replay hooks module rebuilds its environment, and recorded joint
actions fly again with exactly the recorded events."""
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


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


class _OverAtOnce:
    """An environment whose episodes end before the first decision: the recording holds no actions at all."""
    def __init__(self):
        self.steps = []
    def reset(self, seed, **case):
        self.case = case
    def step(self, actions):
        self.steps.append(actions)
        return SimpleNamespace(reward=0., truncated=False, terminated=True, events={'seconds': 0., 'level': None})
    def close(self):
        pass


def test_an_episode_recorded_without_actions_replays_with_one_empty_step(tmp_path, monkeypatch):
    from learning import replay, tasks
    env = _OverAtOnce()
    hooks = types.ModuleType('tests._over_at_once_hooks')
    hooks.open_environment = lambda path, manifest: env
    monkeypatch.setitem(sys.modules, hooks.__name__, hooks)
    monkeypatch.setitem(tasks.TASKS, 'over', tasks.Task('over', 'tests', 'Over', replay_module='learning.replay',
                                                        replay_hooks=hooks.__name__))
    (tmp_path/'config.json').write_text(json.dumps(dict(task='over', manifest={})))
    (tmp_path/'episodes').mkdir()
    (tmp_path/'episodes'/'iter0000.json').write_text(json.dumps(dict(
        jobs=[dict(level=3, seed=9)], episodes=[dict(seconds=0., level=None)], actions=[[]])))
    rows = replay.fly(tmp_path, 0)
    assert env.steps == [{}] and env.case == dict(level=3)
    assert rows == [dict(episode=0, level=None, seed=9, **{'return': 0.}, end='terminated', seconds=0.)]


def test_jelly_replay_accepts_a_run_with_its_copied_opponent_file(tmp_path):
    """learning.run copies the trainer's opponent into every run and records its checksum, Jelly runs included."""
    from learning import replay
    from learning.policy import random_policy
    from learning.adapters.jelly import SPEC
    random_policy(SPEC, 0).save(tmp_path/'opponent.npz')
    record_jelly_run(tmp_path, [dict(level=11, seed=301, team_size=1, stage=1)], horizon=.2)
    settings = json.loads((tmp_path/'config.json').read_text())
    assert settings['manifest']['opponent_sha256'] is not None
    replay.open_environment(tmp_path).close()
    assert replay.fly(tmp_path, 0)[0]['seconds'] == pytest.approx(.2)


def test_the_jelly_replay_scene_draws_each_jellys_route_and_waypoint():
    import pygame
    from learning.adapters import jelly_replay, jelly_scenario
    env = jelly_scenario.JellyEnvironment(horizon=5.)
    pygame.init()
    screen = pygame.Surface((1352, 878))
    try:
        env.reset(5, level=14, lesson='cave')
        screen.fill((0, 0, 0))
        jelly_replay.draw(env, screen)
        colours = {tuple(screen.get_at((x, y)))[:3] for x in range(0, 1352, 2) for y in range(0, 878, 2)}
        assert jelly_replay.WAYPOINT_COLOUR in colours       # the waypoint marker is on screen
    finally:
        env.close()
