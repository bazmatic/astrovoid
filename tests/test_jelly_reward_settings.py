"""Run reward settings affect paid rewards, survive workers/replay, and cannot change on resume."""
import json

import pytest

from tools import ppo_neural


@pytest.mark.parametrize('custom,catch,share', [({}, 10., .25), ({'catch_reward': 12., 'team_catch_share': .5}, 12., .5)])
def test_catch_pays_the_configured_reward_and_teammate_share(custom, catch, share):
    from learning.adapters.jelly_scenario import JellyEnvironment
    from tests.test_neural_jelly import still
    env = JellyEnvironment(rewards=custom)
    try:
        env.reset(5, team_size=2)
        catcher = next(c for c in env.team.members() if c.agent_id == 0)
        target = env.world.additional_targets[0]
        target.x, target.y = catcher.x + 3, catcher.y
        target.vx = target.vy = 0.
        result = env.step(still(env))
        assert result.events['catches'] == 1
        assert result.agent_rewards == pytest.approx({0: catch, 1: catch * share})
    finally:
        env.close()


def test_recorded_reward_settings_govern_worker_rollouts_and_replay(tmp_path):
    from learning import replay
    from learning.adapters import jelly_scenario as scenario
    from learning.policy import random_policy
    from learning.run import rollout_job
    args = ppo_neural.build_parser().parse_args(['--task', 'jelly_team', '--horizon', '.4',
                                               '--jelly-progress-reward', '.2', '--jelly-stuck-penalty', '0'])
    # An immutable copy as a real run records it; checksum validation also uses this copy.
    import shutil
    shutil.copyfile(args.opponent, tmp_path / 'opponent.npz')
    args.opponent = str(tmp_path / 'opponent.npz')
    manifest = scenario.metadata(args)
    manifest['training'] = {}
    (tmp_path / 'config.json').write_text(json.dumps(dict(task=args.task, args=vars(args), manifest=manifest)))
    policy = random_policy(scenario.SPEC, 3, hidden=8, embed=4)
    policy.save(tmp_path / 'initial.npz')
    case = dict(level=11, seed=301, team_size=1, stage=1)
    trajectories, events, actions = rollout_job(dict(task=args.task, weights=str(tmp_path / 'initial.npz'),
        opponent=args.opponent, horizon=args.horizon, muted=False, mode='greedy', case=case))
    assert abs(sum(events['agent_returns'].values())) > 0
    (tmp_path / 'episodes').mkdir()
    (tmp_path / 'episodes' / 'iter0000.json').write_text(json.dumps(dict(jobs=[case],
        episodes=[dict(events, **case)], actions=[actions])))
    replayed = replay.fly(tmp_path, 0)[0]
    assert replayed['return'] == pytest.approx(sum(events['agent_returns'].values()))
    default = scenario.JellyEnvironment(horizon=args.horizon, arenas=manifest['arenas'])
    from learning.training import collect
    try:
        _, default_events, _ = collect(default, policy, case['seed'], {k:v for k,v in case.items() if k != 'seed'}, greedy=True)
    finally:
        default.close()
    assert sum(events['agent_returns'].values()) == pytest.approx(100 * sum(default_events['agent_returns'].values()))


def test_resume_rejects_changed_reward_values_before_loading_optimizer_state(tmp_path):
    from learning.adapters import jelly_scenario as scenario
    from learning.run import train
    args = ppo_neural.build_parser().parse_args(['--task', 'jelly_team', '--out', str(tmp_path), '--resume'])
    args.opponent = str(tmp_path / 'opponent.npz')
    manifest = scenario.metadata(args)
    manifest['training'] = {k:getattr(args,k) for k in ('seed','lr','gamma','gae_lambda','episodes','bootstrap_episodes')}
    (tmp_path / 'config.json').write_text(json.dumps(dict(task=args.task, manifest=manifest)))
    args.jelly_catch_reward = 20.
    with pytest.raises(ValueError, match='rules.*changed'):
        train(args)


def test_custom_shaping_geometry_changes_payout_without_changing_benchmark_metrics():
    import math
    from learning.adapters.jelly_scenario import JellyEnvironment
    from tests.test_neural_jelly import open_line, place, still
    env = JellyEnvironment(rewards={'flank_range': 50., 'bunch_distance': 250., 'bunch_penalty': .3})
    try:
        env.reset(5, team_size=2, stage=2)
        home, angle = open_line(env, 230)
        target = env.world.additional_targets[0]
        target.x, target.y = home[0] + 100 * math.cos(angle), home[1] + 100 * math.sin(angle)
        target.vx = target.vy = 0.
        place(env, 1, (home[0] + 200 * math.cos(angle), home[1] + 200 * math.sin(angle)))
        result = env.step(still(env))
        # A perfect 200px-wide pincer scores spread 1 and no bunching in the fixed benchmark.
        assert result.events['angular_spread'] == pytest.approx(1.)
        assert result.events['bunched_seconds'] == 0.
        # Both Jellies are outside the configured flank range, and inside its bunch distance.
        assert result.agent_rewards == pytest.approx({0: -.3, 1: -.3})
    finally:
        env.close()
