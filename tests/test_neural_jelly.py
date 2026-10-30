"""The neural Jelly: a policy chooses heading and acceleration; without one it chases like the scripted Jelly."""
import math
import random
from types import SimpleNamespace

import numpy as np
import pytest

import creatures
from creatures.jelly_team import ACCEL_RATE, DECISION_FRAMES, MAX_SPEED, TURN_RATE, Intent, get_jelly_team
from learning.adapters import jelly as adapter
from learning.policy import PolicySpec, random_policy
from tests.creature_parts import encounter, open_maze, target, world

POS = (400.0, 300.0)


def team_scene(positions=(POS,), ship=None):
    crew = [creatures.build('neural_jelly', p, 5) for p in positions]
    enc = encounter(*crew, world_=world(ship=ship))
    enc.ready()
    team = get_jelly_team(enc)
    team.external = True
    team.members()
    return crew, enc, team


def speed(c):
    return math.hypot(c.vx, c.vy)


def test_commit_accelerates_and_clamps_speed():
    (jelly,), enc, team = team_scene()
    team.commit({jelly.agent_id: Intent(heading=0., accel=1.)})
    enc.step(1.0)
    assert math.isclose(speed(jelly), ACCEL_RATE)
    for _ in range(200):
        enc.step(1.0)
    assert math.isclose(speed(jelly), MAX_SPEED)
    assert jelly.vx > 0 and abs(jelly.vy) < 1e-9
    assert jelly.x > POS[0]


def test_negative_accel_brakes_to_a_stop_and_stays():
    (jelly,), enc, team = team_scene()
    team.commit({jelly.agent_id: Intent(heading=0., accel=1.)})
    for _ in range(200):
        enc.step(1.0)
    team.commit({jelly.agent_id: Intent(heading=math.pi, accel=-1.)})
    enc.step(1.0)
    assert math.isclose(speed(jelly), MAX_SPEED - ACCEL_RATE)
    assert jelly.vx > 0   # braking slows the current motion; it does not push backwards
    for _ in range(200):
        enc.step(1.0)
    assert speed(jelly) == 0.
    stopped = jelly.get_pos()
    for _ in range(20):
        enc.step(1.0)
    assert jelly.get_pos() == stopped


def test_heading_turns_at_a_bounded_rate():
    (jelly,), enc, team = team_scene()
    team.commit({jelly.agent_id: Intent(heading=0., accel=1.)})
    for _ in range(50):
        enc.step(1.0)
    assert math.isclose(jelly.jelly_facing, 0., abs_tol=1e-9)
    team.commit({jelly.agent_id: Intent(heading=math.pi / 2, accel=1.)})
    enc.step(1.0)
    assert math.isclose(jelly.jelly_facing, TURN_RATE)
    frames = math.ceil((math.pi / 2) / TURN_RATE)
    for frame in range(2, frames + 5):
        enc.step(1.0)
        assert jelly.jelly_facing <= math.pi / 2 + 1e-9   # never overshoots
        if frame < frames:
            assert jelly.jelly_facing < math.pi / 2 - 1e-9
    assert math.isclose(jelly.jelly_facing, math.pi / 2)


def test_without_policy_jelly_chases_like_scripted():
    ship = (POS[0] + 300.0, POS[1])
    scripted = creatures.build('aggressive', POS, 5)
    neural = creatures.build('neural_jelly', POS, 5)
    enc_s = encounter(scripted, world_=world(ship=target(ship)))
    enc_n = encounter(neural, world_=world(ship=target(ship)))
    random.seed(3)
    for _ in range(30):
        enc_s.step(1.0)
    random.seed(3)
    for _ in range(30):
        enc_n.step(1.0)
    assert neural.x > POS[0] + 10
    assert math.isclose(neural.x, scripted.x) and math.isclose(neural.y, scripted.y)
    assert get_jelly_team(enc_n).driver is None


def test_single_jelly_team_has_one_member():
    (jelly,), enc, team = team_scene()
    assert team.members() == [jelly]
    assert get_jelly_team(enc) is team


def test_driver_decides_every_decision_frames():
    (jelly,), enc, team = team_scene()
    team.external = False
    calls = []

    class Stub:
        def decide(self, t):
            calls.append(t.frames)
            t.commit({c.agent_id: Intent(heading=0., accel=1.) for c in t.members()})

    team.driver = Stub()
    for _ in range(DECISION_FRAMES * 2 + 1):
        enc.step(1.0)
    assert calls == [0, DECISION_FRAMES, 2 * DECISION_FRAMES]
    assert jelly.vx > 0


# --- the adapter: what a Jelly senses and how its policy's outputs become an Intent ---


def feature(x, name):
    return float(x[adapter.FEATURES.index(name)])


def test_observation_length_matches_spec():
    crew, enc, team = team_scene(positions=(POS, (POS[0] + 60, POS[1]), (POS[0], POS[1] + 80)),
                                 ship=target((POS[0] + 200, POS[1])))
    for c in crew:
        x, masks, sites = adapter.observe(team, c)
        assert sites == ()
        assert x.dtype == np.float32 and len(x) == len(adapter.SPEC.features)
        assert np.isfinite(x).all() and np.abs(x).max() <= 1.0
        assert set(masks) == {name for name, _ in adapter.HEADS}
    assert len(adapter.critic(team)) == adapter.CRITIC_SIZE
    assert np.isfinite(adapter.critic(team)).all()


def test_team_of_one_zero_fills_teammate_slots():
    (jelly,), enc, team = team_scene(ship=target((POS[0] + 200, POS[1])))
    x, _, _ = adapter.observe(team, jelly)
    slots = [i for i, n in enumerate(adapter.FEATURES) if n.startswith('teammate')]
    assert len(slots) == 4 * len(adapter.TEAM)
    assert not x[slots].any()


def test_teammate_slot_sees_nearest_other_jelly():
    (a, b, c), enc, team = team_scene(positions=(POS, (POS[0] + 300, POS[1]), (POS[0] + 50, POS[1])))
    a.jelly_facing = 0.
    x, _, _ = adapter.observe(team, a)
    assert feature(x, 'teammate0_present') == 1 and feature(x, 'teammate1_present') == 1
    assert feature(x, 'teammate2_present') == 0
    assert feature(x, 'teammate0_distance') < feature(x, 'teammate1_distance')
    assert math.isclose(feature(x, 'teammate0_bearing_cos'), 1., abs_tol=1e-6)


def test_dead_teammate_drops_out_of_slots():
    (a, b, c), enc, team = team_scene(positions=(POS, (POS[0] + 50, POS[1]), (POS[0] + 300, POS[1])))
    a.jelly_facing = 0.
    near = feature(adapter.observe(team, a)[0], 'teammate0_distance')
    enc.kill(b)
    x, _, _ = adapter.observe(team, a)
    assert feature(x, 'teammate0_present') == 1 and feature(x, 'teammate1_present') == 0
    assert feature(x, 'teammate0_distance') > near   # the far Jelly now fills slot 0


def test_closing_speed_is_nonzero_for_a_moving_target():
    ship = target((POS[0] + 200, POS[1]))
    (jelly,), enc, team = team_scene(ship=ship)
    ship.vx, ship.vy = -2., 0.   # toward the Jelly
    toward = feature(adapter.observe(team, jelly)[0], 'target_closing_speed')
    ship.vx = 2.                 # away from the Jelly
    away = feature(adapter.observe(team, jelly)[0], 'target_closing_speed')
    assert math.isclose(toward, 2 / adapter.CLOSING_SCALE, rel_tol=1e-5)
    assert math.isclose(away, -2 / adapter.CLOSING_SCALE, rel_tol=1e-5)


def test_no_target_sets_present_zero_and_does_not_raise():
    (jelly,), enc, team = team_scene()
    assert enc.target_for(jelly) is None
    x, _, _ = adapter.observe(team, jelly)
    assert feature(x, 'target_present') == 0
    assert not x[[adapter.FEATURES.index(f'target_{n}') for n in adapter.TARGET]].any()
    adapter.teacher(jelly, enc)


def test_target_bearing_is_relative_to_facing():
    (jelly,), enc, team = team_scene(ship=target((POS[0], POS[1] + 200)))
    jelly.jelly_facing = 0.
    x, _, _ = adapter.observe(team, jelly)
    assert feature(x, 'target_present') == 1
    assert math.isclose(feature(x, 'target_bearing_sin'), 1., abs_tol=1e-6)
    assert math.isclose(feature(x, 'target_bearing_cos'), 0., abs_tol=1e-6)


def test_wall_rays_see_adjacent_wall():
    wall = SimpleNamespace(start=(POS[0] + 20, POS[1] - 100), end=(POS[0] + 20, POS[1] + 100), active=True)
    crew = [creatures.build('neural_jelly', POS, 5)]
    enc = encounter(*crew, world_=world(maze=open_maze([wall])))
    enc.ready()
    team = get_jelly_team(enc)
    team.external = True
    crew[0].jelly_facing = 0.
    x, _, _ = adapter.observe(team, crew[0])
    assert math.isclose(feature(x, 'ray_0'), 20 / adapter.RAY_REACH, rel_tol=1e-4)
    assert feature(x, 'ray_8') == 1.0   # nothing behind


def test_intention_maps_activations_to_heading_and_accel():
    intent = adapter.intention((0., 0.))
    assert intent == Intent(heading=0., accel=0.)
    intent = adapter.intention((50., -50.))
    assert math.isclose(intent.heading, math.pi) and math.isclose(intent.accel, -1.)


def test_teacher_heads_toward_target():
    (jelly,), enc, team = team_scene(ship=target((POS[0], POS[1] + 200)))
    heading, accel = adapter.teacher(jelly, enc)
    intent = adapter.intention((heading, accel))
    assert math.isclose(intent.heading, math.pi / 2, abs_tol=1e-3) and intent.accel > 0.9


def test_driver_commits_one_intent_per_member():
    crew, enc, team = team_scene(positions=(POS, (POS[0] + 60, POS[1])), ship=target((POS[0] + 200, POS[1])))
    for c in crew:
        c.jelly_intent = None
    driver = adapter.JellyDriver(random_policy(adapter.SPEC), greedy=False, seed=1)
    driver.decide(team)
    assert set(driver.states) == {c.agent_id for c in crew}
    for c in crew:
        assert isinstance(c.jelly_intent, Intent)
        assert -math.pi <= c.jelly_intent.heading <= math.pi and -1 <= c.jelly_intent.accel <= 1
    assert adapter.enabled(None, None, None) == [True, True]


def test_load_policy_rejects_wrong_spec(tmp_path):
    good = tmp_path / 'good.npz'
    random_policy(adapter.SPEC).save(good)
    assert adapter.load_policy(good).spec == adapter.SPEC
    wrong = PolicySpec('jelly_team', adapter.FEATURES, adapter.HEADS, version=adapter.SPEC.version + 1,
                       continuous=('heading', 'accel'))
    bad = tmp_path / 'bad.npz'
    random_policy(wrong).save(bad)
    with pytest.raises(ValueError):
        adapter.load_policy(bad)


# ---- Stage 1 scenario: navigation to a moving target ----

def still(env):
    """Zero-accel actions for every living Jelly: heading 0, no push."""
    return {i: (0., 0.) for i in env.snapshot().observations}


def toward(env, i, pos, accel=3.):
    c = next(c for c in env.team.members() if c.agent_id == i)
    desired = math.atan2(pos[1] - c.y, pos[0] - c.x)
    return (math.atanh(max(-.999, min(.999, desired / math.pi))), accel)


def jelly_env(horizon=60.0, **case):
    from learning.adapters.jelly_scenario import JellyEnvironment
    env = JellyEnvironment(horizon=horizon)
    snap = env.reset(case.pop('seed', 5), **case)
    return env, snap


def test_reset_and_step_are_deterministic_for_a_seed():
    def trial():
        env, first = jelly_env(team_size=2, seed=7)
        try:
            results = []
            for _ in range(20):
                actions = {i: toward(env, i, env.world.additional_targets[0].get_pos()) for i in env.agent_ids}
                results.append(env.step(actions))
            return first, results
        finally:
            env.close()
    (a, ra), (b, rb) = trial(), trial()
    assert set(a.observations) == {0, 1}
    for i in a.observations:
        np.testing.assert_array_equal(a.observations[i], b.observations[i])
    for x, y in zip(ra, rb):
        assert x.events == y.events and x.agent_rewards == y.agent_rewards
        for i in x.snapshot.observations:
            np.testing.assert_array_equal(x.snapshot.observations[i], y.snapshot.observations[i])


def test_contact_with_target_rewards_only_contacting_jelly_more():
    from learning.adapters.jelly_scenario import CATCH_REWARD, TEAM_CATCH_SHARE
    env, _ = jelly_env(team_size=2)
    try:
        catcher = next(c for c in env.team.members() if c.agent_id == 0)
        target = env.world.additional_targets[0]
        target.x, target.y = catcher.x + 3, catcher.y
        target.vx = target.vy = 0.
        result = env.step(still(env))
        assert result.events['catches'] == 1 and result.events['agent_catches'] == {0: 1}
        r = result.agent_rewards
        assert math.isclose(r[0], CATCH_REWARD, abs_tol=1e-6)
        assert math.isclose(r[1], TEAM_CATCH_SHARE * CATCH_REWARD, abs_tol=1e-6)
        assert r[0] > r[1] > 0
        assert math.isclose(result.reward, r[0] + r[1])
    finally:
        env.close()


def test_target_respawns_after_catch_and_episode_continues():
    from learning.adapters.jelly_scenario import RESPAWN_DISTANCE
    env, _ = jelly_env(team_size=1)
    try:
        (jelly,) = env.team.members()
        target = env.world.additional_targets[0]
        target.x, target.y = jelly.x, jelly.y + 4
        result = env.step(still(env))
        assert result.events['catches'] == 1
        assert not result.terminated and not result.truncated
        assert target.active and env.world.maze.is_open(target.get_pos(), target.radius)
        assert math.dist(target.get_pos(), jelly.get_pos()) >= RESPAWN_DISTANCE
        for _ in range(5):
            result = env.step(still(env))
        assert result.events['catches'] == 1 and result.events['seconds'] > 0
    finally:
        env.close()


def test_step_after_end_raises():
    env, _ = jelly_env(horizon=.2)
    try:
        result = env.step(still(env))
        while not (result.terminated or result.truncated):
            result = env.step(still(env))
        assert result.truncated and math.isclose(result.events['seconds'], .2)
        with pytest.raises(RuntimeError):
            env.step(still(env))
    finally:
        env.close()


def test_progress_toward_target_is_rewarded_and_standing_still_is_not_stuck():
    env, _ = jelly_env(team_size=1)
    try:
        (jelly,) = env.team.members()
        target = env.world.additional_targets[0]
        target.vx = target.vy = 0.
        for _ in range(12):
            result = env.step(still(env))
            assert result.agent_rewards[0] == 0.
        assert result.events['stuck_seconds'] == 0.
        # Put the target on the clearest ray, then accelerate straight at it.
        distances = adapter.rays(jelly, env.world.maze, 0.)
        k = int(np.argmax(distances))
        assert distances[k] > 200
        angle = k * 2 * math.pi / len(distances)
        target.x, target.y = jelly.x + 150 * math.cos(angle), jelly.y + 150 * math.sin(angle)
        rewards = [env.step({0: toward(env, 0, target.get_pos())}).agent_rewards[0] for _ in range(5)]
        assert all(r > 0 for r in rewards[1:])
    finally:
        env.close()


def test_accelerating_without_getting_anywhere_counts_as_stuck_and_is_penalised():
    from learning.adapters.jelly_scenario import STUCK_PENALTY, STUCK_WINDOW
    env, _ = jelly_env(team_size=1)
    try:
        (jelly,) = env.team.members()
        target = env.world.additional_targets[0]
        target.vx = target.vy = 0.
        home = jelly.get_pos()
        rewards = []
        for _ in range(STUCK_WINDOW // DECISION_FRAMES + 3):
            result = env.step({0: toward(env, 0, target.get_pos())})
            rewards.append(result.agent_rewards[0])
            jelly.x, jelly.y = home   # jammed: full accel, no displacement
            jelly.vx = jelly.vy = 0.
        # Stuck from the first decision whose whole window was spent accelerating: the last four.
        assert math.isclose(result.events['stuck_seconds'], 4 * DECISION_FRAMES / 60)
        assert rewards[-1] < -STUCK_PENALTY + .03 and rewards[0] > -STUCK_PENALTY / 2
    finally:
        env.close()


def test_scripted_mode_chases_and_teacher_collect_runs():
    from learning.adapters.jelly_scenario import JellyEnvironment, teacher_action
    from learning.training import collect
    env = JellyEnvironment(horizon=1., scripted=True)
    try:
        env.reset(3, level=11, team_size=1)
        (jelly,) = env.team.members()
        start = jelly.get_pos()
        while True:
            result = env.step({})
            if result.truncated or result.terminated:
                break
        assert jelly.get_pos() != start   # the scripted Chase/Drift brain moved it
    finally:
        env.close()
    env = JellyEnvironment(horizon=.5)
    try:
        episodes, events, trace = collect(env, random_policy(adapter.SPEC, hidden=8, embed=4), 4,
                                          dict(level=11, team_size=1), teacher=teacher_action)
        assert trace and all(len(e['x']) == len(e['rewards']) for e in episodes)
        assert {'catches', 'seconds', 'stuck_seconds'} <= set(events)
    finally:
        env.close()


def test_promote_needs_more_catches_and_less_stuck_than_scripted():
    from learning.adapters import jelly_scenario as scenario
    baseline = dict(catches_per_minute=2., stuck_fraction=.2)
    assert scenario.promote(1, dict(catches_per_minute=3., stuck_fraction=.1, episodes=4), baseline) == 2
    assert scenario.promote(1, dict(catches_per_minute=3., stuck_fraction=.3, episodes=4), baseline) == 1
    assert scenario.promote(1, dict(catches_per_minute=1., stuck_fraction=.1, episodes=4), baseline) == 1
    rows = [dict(catches=2, seconds=60., stuck_seconds=6., team_size=1, agent_returns={0: 1.})]
    summary = scenario.metrics(rows)
    assert summary['catches_per_minute'] == 2. and math.isclose(summary['stuck_fraction'], .1)
    # learning.run spreads the summary into its log line beside these keys.
    assert not set(summary) & {'iteration', 'update_s', 'mean_return', 'rollout_s', 'team_size', 'elapsed_s'}


def test_hooks_cover_the_trainer_contract():
    from learning.adapters import jelly_scenario as scenario
    for name in ('SPEC', 'CRITIC_SIZE', 'INITIAL_STAGE', 'IMITATION_HEADS', 'environment', 'metadata',
                 'training_cases', 'validation_cases', 'evaluation_cases', 'metrics', 'selection_score',
                 'promote', 'compare'):
        assert hasattr(scenario, name), name
    assert scenario.INITIAL_STAGE == 1 and scenario.IMITATION_HEADS == ('heading', 'accel')
    cases = scenario.training_cases(0, 4, 1)
    assert all(c['team_size'] == 1 and c['level'] in scenario.TRAIN_LEVELS for c in cases)
    assert all(c['level'] in scenario.HOLDOUT_LEVELS for c in scenario.evaluation_cases())
    assert not set(scenario.TRAIN_LEVELS) & set(scenario.HOLDOUT_LEVELS)
    env = scenario.environment(opponent='ignored', horizon=1., muted=True, arenas=None, scripted=False)
    assert env.adapter.teacher_action is scenario.teacher_action and env.adapter.enabled is adapter.enabled


def test_task_registry_has_jelly_team():
    from learning.tasks import task
    t = task('jelly_team')
    assert t.module == 'learning.adapters.jelly_scenario' and t.label == 'Jelly team'
    assert t.fresh_defaults == dict(horizon=60.0, workers=4, iterations=10000)
    assert t.adapter().SPEC.task == 'jelly_team'


def test_manager_can_start_fresh_jelly_team(tmp_path):
    from tools.trainer.control import start
    from tools import ppo_neural
    calls = []
    result = start(from_='new', changes={'task': 'jelly_team', 'budget_seconds': 10}, root=tmp_path,
                   processes=[], launch=lambda command, log: calls.append(command))
    assert result.started_from == 'random'
    args = ppo_neural.build_parser().parse_args(calls[0][3:])
    assert args.task == 'jelly_team' and args.workers == 4 and args.horizon == 60 and args.start == ''


def test_scripted_baseline_runs_at_the_configured_run_horizon(monkeypatch):
    from learning.adapters import jelly_scenario as scenario
    monkeypatch.setattr(scenario, '_baselines', {})
    monkeypatch.setattr(scenario, 'run_horizon', scenario.run_horizon)
    scenario.metadata(SimpleNamespace(horizon=.5, opponent=''))
    short = scenario.scripted_baseline()
    assert (1, .5) in scenario._baselines
    assert short['episodes'] == len(scenario.evaluation_cases()) and short['seconds'] <= .5 * short['episodes'] + 1e-9
    scenario.metadata(SimpleNamespace(horizon=.2, opponent=''))
    shorter = scenario.scripted_baseline()
    assert set(scenario._baselines) == {(1, .5), (1, .2)} and shorter is not short
    assert math.isclose(shorter['seconds'], .2 * shorter['episodes'])
    # promote baselines at the run's horizon: it reuses that cache entry rather than a 60 s one.
    scenario.promote(1, dict(catches_per_minute=0., stuck_fraction=1., episodes=1))
    assert set(scenario._baselines) == {(1, .5), (1, .2)}


def test_flank_spread_is_zero_for_collinear_bearing_and_one_for_even_ring():
    from learning.adapters.jelly_scenario import flank_spread
    target = (100., 100.)
    same_side = [(150., 100.), (200., 100.), (300., 100.)]
    assert math.isclose(flank_spread(same_side, target), 0., abs_tol=1e-9)
    for n in (2, 3, 4):
        ring = [(100 + 80 * math.cos(2 * math.pi * k / n), 100 + 80 * math.sin(2 * math.pi * k / n)) for k in range(n)]
        assert math.isclose(flank_spread(ring, target), 1., abs_tol=1e-9)
    quarter = [(180., 100.), (100., 180.)]   # a right angle apart: partly spread
    assert 0. < flank_spread(quarter, target) < 1.


def test_single_jelly_has_spread_zero_without_error():
    from learning.adapters.jelly_scenario import flank_spread
    assert flank_spread([(150., 100.)], (100., 100.)) == 0.
    assert flank_spread([], (100., 100.)) == 0.
    assert flank_spread([(100., 100.), (150., 100.)], (100., 100.)) == 0.   # a Jelly on the target has no bearing


def open_line(env, length):
    """Jelly 0's position and the bearing of its clearest wall ray, which is open for at least `length` px."""
    jelly = next(c for c in env.team.members() if c.agent_id == 0)
    distances = adapter.rays(jelly, env.world.maze, 0.)
    k = int(np.argmax(distances))
    assert distances[k] > length
    return jelly.get_pos(), k * 2 * math.pi / len(distances)


def place(env, i, pos):
    c = next(c for c in env.team.members() if c.agent_id == i)
    c.x, c.y = pos
    c.vx = c.vy = 0.


def park_target_far(env):
    target = env.world.additional_targets[0]
    target.x, target.y = env.free_cell(500.)
    target.vx = target.vy = 0.
    return target


def test_bunching_penalty_applies_only_below_bunch_distance():
    from learning.adapters.jelly_scenario import BUNCH_DISTANCE, BUNCH_PENALTY, FLANK_RANGE
    def rewards(gap, stage):
        env, _ = jelly_env(team_size=2, stage=stage)
        try:
            home, angle = open_line(env, BUNCH_DISTANCE + 40)
            place(env, 1, (home[0] + gap * math.cos(angle), home[1] + gap * math.sin(angle)))
            target = park_target_far(env)
            assert all(math.dist(c.get_pos(), target.get_pos()) > FLANK_RANGE for c in env.team.members())
            result = env.step(still(env))
            return result.agent_rewards, result.events
        finally:
            env.close()
    close, events = rewards(BUNCH_DISTANCE - 10, 2)
    assert all(math.isclose(r, -BUNCH_PENALTY, abs_tol=1e-9) for r in close.values())
    assert events['bunched_seconds'] > 0
    apart, events = rewards(BUNCH_DISTANCE + 10, 2)
    assert all(r == 0. for r in apart.values()) and events['bunched_seconds'] == 0.
    stage1, events = rewards(BUNCH_DISTANCE - 10, 1)   # stage 1 rewards are unchanged; bunching is only reported
    assert all(r == 0. for r in stage1.values()) and events['bunched_seconds'] > 0


def test_flanking_pair_is_rewarded_at_stage2_only():
    from learning.adapters.jelly_scenario import FLANK_RANGE, FLANK_REWARD
    def rewards(stage):
        env, _ = jelly_env(team_size=2, stage=stage)
        try:
            home, angle = open_line(env, 230)
            target = env.world.additional_targets[0]
            target.x, target.y = home[0] + 100 * math.cos(angle), home[1] + 100 * math.sin(angle)
            target.vx = target.vy = 0.
            place(env, 1, (home[0] + 200 * math.cos(angle), home[1] + 200 * math.sin(angle)))   # the far side
            assert all(math.dist(c.get_pos(), target.get_pos()) <= FLANK_RANGE for c in env.team.members())
            result = env.step(still(env))
            return result.agent_rewards, result.events
        finally:
            env.close()
    pincer, events = rewards(2)
    assert all(math.isclose(r, FLANK_REWARD, rel_tol=1e-6) for r in pincer.values())
    assert math.isclose(events['angular_spread'], 1., abs_tol=1e-6) and events['flank_seconds'] > 0
    stage1, events = rewards(1)
    assert all(r == 0. for r in stage1.values()) and math.isclose(events['angular_spread'], 1., abs_tol=1e-6)


def test_stage2_cases_have_team_size_2_to_4():
    from learning.adapters import jelly_scenario as scenario
    cases = scenario.training_cases(3, 16, 2)
    team = [c for c in cases if c['stage'] == 2]
    retention = [c for c in cases if c['stage'] == 1]
    assert {c['team_size'] for c in team} == {2, 3, 4}
    assert retention and all(c['team_size'] == 1 for c in retention) and len(retention) < len(team)
    assert all(c['level'] in scenario.TRAIN_LEVELS for c in cases)
    assert all(c['team_size'] == 1 and c['stage'] == 1 for c in scenario.training_cases(3, 16, 1))
    held_out = scenario.evaluation_cases(2)
    assert {c['team_size'] for c in held_out} == {2, 3, 4} and all(c['stage'] == 2 for c in held_out)
    assert all(c['level'] in scenario.HOLDOUT_LEVELS for c in held_out)


def test_flank_metrics_and_promote_from_stage2_need_more_spread_and_team_catches():
    from learning.adapters import jelly_scenario as scenario
    rows = [dict(catches=1, seconds=60., stuck_seconds=0., team_size=1, angular_spread=0., flank_seconds=0.,
                 bunched_seconds=0., agent_returns={0: 1.}),
            dict(catches=3, seconds=60., stuck_seconds=0., team_size=2, angular_spread=.8, flank_seconds=10.,
                 bunched_seconds=12., agent_returns={0: 1., 1: 1.}),
            dict(catches=1, seconds=60., stuck_seconds=0., team_size=2, angular_spread=.2, flank_seconds=30.,
                 bunched_seconds=0., agent_returns={0: 1., 1: 1.})]
    summary = scenario.metrics(rows)
    assert math.isclose(summary['angular_spread'], (.8 * 10 + .2 * 30) / 40)
    assert math.isclose(summary['team_catches_per_minute'], 2.)   # the solo retention row is left out
    assert math.isclose(summary['bunched_fraction'], 12 / 300)
    baseline = dict(angular_spread=.3, team_catches_per_minute=1.5)
    assert scenario.promote(2, summary, baseline) == 3
    assert scenario.promote(2, dict(summary, angular_spread=.2), baseline) == 2
    assert scenario.promote(2, dict(summary, team_catches_per_minute=1.), baseline) == 2
    assert scenario.promote(2, dict(summary, episodes=0), baseline) == 2
