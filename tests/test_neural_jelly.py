"""The neural Jelly: a policy chooses heading and acceleration; without one it chases like the scripted Jelly."""
import math
from collections import Counter
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


def test_policy_observations_are_finite_and_normalised():
    crew, enc, team = team_scene(positions=(POS, (POS[0] + 60, POS[1]), (POS[0], POS[1] + 80)),
                                 ship=target((POS[0] + 200, POS[1])))
    for c in crew:
        x, _, _ = adapter.observe(team, c)
        assert np.isfinite(x).all() and np.abs(x).max() <= 1.0
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
    intent = adapter.intention((0., 0.), 1.)
    assert intent == Intent(heading=1., accel=0.)   # a zero turn keeps the current facing
    intent = adapter.intention((50., -50.), 1.)
    assert math.isclose(intent.heading, 1. + math.pi - 2*math.pi, abs_tol=1e-6) and math.isclose(intent.accel, -1.)


def test_teacher_heads_toward_target():
    (jelly,), enc, team = team_scene(ship=target((POS[0], POS[1] + 200)))
    heading, accel = adapter.teacher(jelly, enc)
    intent = adapter.intention((heading, accel), adapter.facing(jelly))
    assert math.isclose(math.remainder(intent.heading, 2*math.pi), math.pi / 2, abs_tol=1e-3) and intent.accel > 0.9


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
    return (adapter.relative_heading_label(c, desired), accel)


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


def test_training_and_evaluation_use_separate_arenas():
    from learning.adapters import jelly_scenario as scenario
    cases = scenario.training_cases(0, 4, 1)
    assert all(c['team_size'] == 1 and c['level'] in scenario.TRAIN_LEVELS for c in cases)
    assert all(c['level'] in scenario.HOLDOUT_LEVELS for c in scenario.evaluation_cases())
    assert not set(scenario.TRAIN_LEVELS) & set(scenario.HOLDOUT_LEVELS)


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
    assert short['episodes'] == len(scenario.evaluation_cases(1)) and short['seconds'] <= .5 * short['episodes'] + 1e-9
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


def test_stage2_team_sizes_are_not_tied_to_particular_levels():
    from collections import defaultdict
    from learning.adapters import jelly_scenario as scenario
    cases = [c for it in range(4) for c in scenario.training_cases(it, 16, 2)]
    levels = defaultdict(set)
    for c in cases:
        levels[(c['stage'], c['team_size'])].add(c['level'])
    assert set(levels) == {(1, 1), (2, 2), (2, 3), (2, 4)}
    assert all(len(found) > 2 for found in levels.values()), dict(levels)
    assert sum(c['stage'] == 1 for c in cases) * 4 == len(cases)   # the 1-in-4 retention share holds
    assert cases == [c for it in range(4) for c in scenario.training_cases(it, 16, 2)]


# ---- Stage 3: a training ship that hunts the Jellies back ----

def resolved(kind_key):
    """A piloted kind's traits as the game builds them for the neural pilot's settings."""
    import enemy_kinds
    from hunter.build import flight_kind
    from hunter.settings_for import hunter_settings_for
    return dict(flight_kind(enemy_kinds.kind(kind_key), hunter_settings_for('neural')).traits)


def test_training_ship_is_slower_and_weaker_than_normal():
    import enemy_kinds
    from creatures import registry
    registry.validate(enemy_kinds._CATALOGUE)
    kind = enemy_kinds.kind('training_ship')
    friend = enemy_kinds.kind('allied_hunter')
    assert kind.allegiance == friend.allegiance == 'friend' and kind.body == friend.body == 'hunterShip'
    assert 'training_ship' not in enemy_kinds.kinds()   # never placed as an enemy in a level
    ship, normal = resolved('training_ship'), resolved('allied_hunter')
    assert ship['thrusters']['maxSpeed'] == pytest.approx(.6 * normal['thrusters']['maxSpeed'])
    assert ship['thrusters']['thrust'] == pytest.approx(.6 * normal['thrusters']['thrust'])
    assert ship['burstFire']['interval'] == pytest.approx(2 * normal['burstFire']['interval'])
    assert ship['gun']['shotStrength'] == .5 and normal['gun'].get('shotStrength', 1.) == 1.
    assert ship['energy']['indestructible'] is False and ship['energy']['health'] == 3
    built = creatures.build('training_ship', (400., 300.), 11)
    assert built.allegiance == 'friend' and built.kind.pilot == 'neural'


def test_flight_kind_keeps_the_catalogues_own_params():
    """Pilot settings fill in only what a kind leaves out, so existing kinds resolve as before."""
    ship, viber = resolved('training_ship'), resolved('neural_hunter')
    assert viber['thrusters']['maxSpeed'] == 8. and viber['burstFire']['interval'] == .25
    assert viber['energy']['health'] == 10 and ship['energy']['wallEnergy'] == 0


def stage3_env(team_size=1, **case):
    env, snap = jelly_env(team_size=team_size, stage=3, **case)
    env.ship.flight.controller.unavailable = True   # the pilot idles (neutral, gun off): tests place their own shots
    return env, snap


def shoot_at(env, i):
    """The training ship's shot (a friend's: source 'hunter', half strength) just behind Jelly `i`, flying into it."""
    from entities.projectile import Projectile
    c = next(c for c in env.team.members() if c.agent_id == i)
    shot = Projectile((c.x - 6., c.y), 0., source='hunter', strength=.5)
    env.world.projectiles.append(shot)
    return shot


def park_ship_far(env):
    env.ship.x, env.ship.y = env.free_cell(500.)
    env.ship.vx = env.ship.vy = 0.


def test_ship_hit_kills_one_hp_jelly():
    env, _ = stage3_env(team_size=2)
    try:
        park_ship_far(env)
        jelly = next(c for c in env.team.members() if c.agent_id == 0)
        assert jelly.hit_points == 1
        shoot_at(env, 0)
        env.step(still(env))
        assert not jelly.active and jelly.hit_points <= 0
    finally:
        env.close()


def test_training_ship_hunts_and_shoots_the_jellies():
    from learning.adapters.jelly_scenario import JellyEnvironment
    env = JellyEnvironment(horizon=30.)
    try:
        env.reset(7, level=11, team_size=2, stage=3)
        ship = env.ship
        start = min(math.dist(ship.get_pos(), c.get_pos()) for c in env.team.members())
        closest = start
        result = None
        while result is None or not (result.terminated or result.truncated):
            result = env.step(still(env))
            if env.team.members():
                closest = min(closest, min(math.dist(ship.get_pos(), c.get_pos()) for c in env.team.members()))
        assert ship.shots_fired > 0 and result.events['jelly_deaths'] > 0   # the frozen hunter pilot, greedy: seed 7
        assert closest < start
    finally:
        env.close()


def test_stage3_puts_the_hunting_ship_among_the_targets():
    env, snap = stage3_env(team_size=2)
    try:
        assert env.ship in env.world.roster.alive() and env.ship.active and env.ship.flight is not None
        assert all(env.enc.target_entity_for(c) is env.ship for c in env.team.members())
        assert all(math.dist(c.get_pos(), env.ship.get_pos()) >= 250. for c in env.team.members())
        result = env.step(still(env))
        assert result.events['stage'] == 3 and result.events['catches'] == 0
        assert {'ship_hits', 'ship_kills', 'jelly_deaths', 'survival_fraction', 'time_to_ship_kill'} <= set(result.events)
    finally:
        env.close()


def test_episode_ends_when_all_jellies_die():
    env, _ = stage3_env(team_size=2)
    try:
        park_ship_far(env)
        for i in env.agent_ids:
            shoot_at(env, i)
        result = env.step(still(env))
        assert result.terminated and not result.truncated
        assert result.events['jelly_deaths'] == 2 and result.events['alive'] == 0
        assert result.events['survival_fraction'] == 0. and result.events['ship_kills'] == 0
        with pytest.raises(RuntimeError):
            env.step({})
    finally:
        env.close()


def test_episode_ends_when_ship_dies():
    from learning.adapters.jelly_scenario import SHIP_HIT_REWARD, SHIP_KILL_REWARD
    env, _ = stage3_env(team_size=1)
    try:
        jelly = env.team.members()[0]
        env.ship.health = 1
        env.ship.x, env.ship.y = jelly.x + 6., jelly.y
        env.ship.vx = env.ship.vy = 0.
        result = env.step(still(env))
        assert result.terminated and not result.truncated
        assert result.events['ship_kills'] == 1 and result.events['ship_hits'] == 1
        assert not env.ship.active and result.events['survival_fraction'] == 1.
        assert 0. < result.events['time_to_ship_kill'] <= DECISION_FRAMES / 60
        assert result.agent_rewards[0] >= SHIP_HIT_REWARD + SHIP_KILL_REWARD - 1.
    finally:
        env.close()


def test_jelly_death_is_penalised():
    from learning.adapters.jelly_scenario import DEATH_PENALTY, TEAM_DEATH_SHARE
    env, _ = stage3_env(team_size=2)
    try:
        park_ship_far(env)
        home, angle = open_line(env, 120)
        place(env, 1, (home[0] + 80 * math.cos(angle), home[1] + 80 * math.sin(angle)))
        shoot_at(env, 0)
        result = env.step(still(env))
        assert not result.terminated and result.events['jelly_deaths'] == 1 and result.events['alive'] == 1
        assert result.agent_rewards[0] <= -DEATH_PENALTY + .1
        assert result.agent_rewards[1] == pytest.approx(-TEAM_DEATH_SHARE * DEATH_PENALTY, abs=.1)
        assert result.events['survival_fraction'] == .5
        after = env.step(still(env))   # the survivor plays on; the dead Jelly earns nothing more
        assert set(after.snapshot.observations) == {1} and after.agent_rewards[0] == 0.
    finally:
        env.close()


def test_stage3_reward_trade_off_makes_a_suicide_rush_unattractive():
    from learning.adapters import jelly_scenario as s
    assert s.SHIP_HIT_REWARD - s.DEATH_PENALTY < 0          # one hit traded for a life loses
    assert s.SHIP_KILL_REWARD > s.DEATH_PENALTY              # killing the ship is worth more than a death costs
    hull = resolved(s.SHIP_KIND)['energy']['health']
    assert hull * s.SHIP_HIT_REWARD + s.SHIP_KILL_REWARD > s.DEATH_PENALTY


def test_ship_dead_or_jellies_dead_before_first_step_does_not_crash():
    env, _ = stage3_env(team_size=1)
    try:
        env.enc.kill(env.ship)
        result = env.step({})
        assert result.terminated and result.events['seconds'] == 0.
    finally:
        env.close()


def test_stage3_cases_promote_and_metrics():
    from learning.adapters import jelly_scenario as scenario
    cases = [c for it in range(4) for c in scenario.training_cases(it, 16, 3)]
    by_stage = Counter(c['stage'] for c in cases)
    assert by_stage[3] * 4 == len(cases) * 3 and by_stage[2] == by_stage[1] == len(cases) // 8
    assert {c['team_size'] for c in cases if c['stage'] == 3} == set(scenario.STAGE3_TEAM_SIZES)
    assert all(c['team_size'] == 1 for c in cases if c['stage'] == 1)
    assert {c['team_size'] for c in cases if c['stage'] == 2} <= set(scenario.STAGE2_TEAM_SIZES)
    assert cases == [c for it in range(4) for c in scenario.training_cases(it, 16, 3)]
    assert scenario.training_cases(3, 16, 2) == scenario.training_cases(3, 16, 2)   # stage 2 unchanged
    held_out = scenario.evaluation_cases(3)
    assert all(c['stage'] == 3 and c['level'] in scenario.HOLDOUT_LEVELS for c in held_out)
    assert {c['team_size'] for c in held_out} == set(scenario.STAGE3_TEAM_SIZES)
    rows = [dict(catches=0, seconds=30., stuck_seconds=0., team_size=2, stage=3, ship_hits=3, ship_kills=1,
                 jelly_deaths=1, survival_fraction=.5, time_to_ship_kill=30., agent_returns={0: 1., 1: 1.}),
            dict(catches=0, seconds=60., stuck_seconds=0., team_size=4, stage=3, ship_hits=1, ship_kills=0,
                 jelly_deaths=0, survival_fraction=1., time_to_ship_kill=None, agent_returns={0: 1.}),
            dict(catches=2, seconds=60., stuck_seconds=0., team_size=1, agent_returns={0: 1.})]
    summary = scenario.metrics(rows)
    assert summary['ship_hits'] == 4 and summary['ship_kills'] == 1 and summary['jelly_deaths'] == 1
    assert summary['survival_fraction'] == pytest.approx(5 / 6)   # Jelly-weighted, over stage-3 rows only
    assert summary['time_to_ship_kill'] == 30.
    assert scenario.promote(3, summary, dict(catches_per_minute=0., stuck_fraction=1.)) == 3
    assert scenario.metrics(rows[2:])['survival_fraction'] == 1. and scenario.metrics(rows[2:])['ship_kills'] == 0


def test_scripted_team_hunts_the_ship_at_stage3():
    from learning.adapters.jelly_scenario import JellyEnvironment
    env = JellyEnvironment(horizon=3., scripted=True)
    try:
        env.reset(5, level=11, team_size=3, stage=3)
        result = env.step({})
        while not (result.terminated or result.truncated):
            result = env.step({})
        assert result.events['stage'] == 3 and result.events['seconds'] <= 3.
    finally:
        env.close()


# ---- Game wiring: JELLY_POLICY ----

@pytest.fixture
def make_game(tmp_path, monkeypatch):
    """A real Game started with JELLY_POLICY pointing at the given file (as tests/test_replay_loop.py starts one)."""
    import pygame
    import config
    import level_config
    from unittest.mock import Mock
    from game import Game
    from profiles import ProfileManager
    from maze.config import MazeComplexity
    games = []

    def start(policy_path):
        pygame.init()
        screen = pygame.display.set_mode((1352, 878))
        monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
        monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
        monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
        monkeypatch.delenv('START_LEVEL', raising=False)
        monkeypatch.delenv('WALLCRAWLER_POLICY', raising=False)
        monkeypatch.setenv('JELLY_POLICY', str(policy_path))
        manager = ProfileManager(tmp_path / 'profiles.json')
        monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
        monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
        monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: False)
        monkeypatch.setattr(level_config, 'get_maze_complexity', lambda _: MazeComplexity.EMPTY)
        monkeypatch.setattr(level_config, 'get_maze_grid_size', lambda _: 5)
        game = Game(screen)
        games.append(game)
        return game
    yield start
    for game in games:
        game._close_hunter()


def jelly_policy_warnings(caplog):
    return [r for r in caplog.records if r.levelname == 'WARNING' and 'Jelly policy' in r.getMessage()]


def test_corrupt_weights_file_leaves_policy_none_and_game_starts(make_game, tmp_path, caplog):
    corrupt = tmp_path / 'corrupt.npz'
    corrupt.write_bytes(b'not a numpy archive')
    caplog.set_level('WARNING')
    game = make_game(corrupt)
    assert game.jelly_policy is None
    assert len(jelly_policy_warnings(caplog)) == 1
    missing = make_game(tmp_path / 'missing.npz')
    assert missing.jelly_policy is None and len(jelly_policy_warnings(caplog)) == 2
    truncated = tmp_path / 'truncated.npz'   # a damaged archive (zip header, no body), as a cut-off copy leaves it
    truncated.write_bytes(b'PK\x03\x04 cut off')
    assert make_game(truncated).jelly_policy is None and len(jelly_policy_warnings(caplog)) == 3


def test_wrong_spec_weights_fall_back_to_scripted(make_game, tmp_path, caplog):
    wrong = PolicySpec('jelly_team', adapter.FEATURES, adapter.HEADS, version=adapter.SPEC.version + 1,
                       continuous=('heading', 'accel'))
    path = tmp_path / 'wrong.npz'
    random_policy(wrong).save(path)
    caplog.set_level('WARNING')
    game = make_game(path)
    assert game.jelly_policy is None and len(jelly_policy_warnings(caplog)) == 1
    # The game is the encounter's world; a neural_jelly there chases exactly like the scripted aggressive Jelly.
    assert game.encounter.world is game
    ship = (POS[0] + 300.0, POS[1])
    scripted = creatures.build('aggressive', POS, 5)
    neural = creatures.build('neural_jelly', POS, 5)
    enc_s = encounter(scripted, world_=world(ship=target(ship)))
    enc_n = encounter(neural, world_=world(ship=target(ship), jelly_policy=game.jelly_policy))
    random.seed(3)
    for _ in range(30):
        enc_s.step(1.0)
    random.seed(3)
    for _ in range(30):
        enc_n.step(1.0)
    assert math.isclose(neural.x, scripted.x) and math.isclose(neural.y, scripted.y)
    assert get_jelly_team(enc_n).driver is None and not get_jelly_team(enc_n).neural


def test_valid_jelly_weights_reach_the_team_through_the_game_world(make_game, tmp_path, caplog):
    path = tmp_path / 'policy.npz'
    random_policy(adapter.SPEC, 1).save(path)
    caplog.set_level('WARNING')
    game = make_game(path)
    assert game.jelly_policy is not None and game.jelly_policy.spec == adapter.SPEC
    assert not jelly_policy_warnings(caplog)
    jelly = creatures.build('neural_jelly', POS, 5)
    enc = encounter(jelly, world_=world(ship=target((POS[0] + 300.0, POS[1])), jelly_policy=game.jelly_policy))
    enc.step(1.0)
    assert get_jelly_team(enc).driver is not None and get_jelly_team(enc).neural


# ---- Evaluation gate ----

def gate_rows(catches, stuck, ship_hits=0, deaths=0):
    """One validation-shaped set: a stage-1 solo, a stage-2 pair and a stage-3 pair, each a minute long."""
    return [dict(catches=catches, seconds=60., stuck_seconds=stuck, team_size=1, stage=1, time_to_contact=10.),
            dict(catches=catches, seconds=60., stuck_seconds=stuck, team_size=2, stage=2, time_to_contact=None),
            dict(catches=0, seconds=60., stuck_seconds=stuck, team_size=2, stage=3, ship_hits=ship_hits,
                 ship_kills=0, jelly_deaths=deaths, survival_fraction=1-deaths/2, time_to_contact=None)]


def test_selection_score_rejects_policy_that_loses_on_cave_arenas():
    from learning.adapters import jelly_scenario as scenario
    baseline = scenario.metrics(gate_rows(catches=4, stuck=6.))
    lowest = scenario.selection_score(scenario.metrics(gate_rows(catches=0, stuck=0.)), baseline)
    assert lowest == -math.inf                                                    # sits still: never caught
    assert scenario.selection_score(scenario.metrics(gate_rows(catches=4, stuck=0.)), baseline) == -math.inf   # tie
    assert scenario.selection_score(scenario.metrics(gate_rows(catches=9, stuck=7.)), baseline) == -math.inf   # stuck
    passing = scenario.selection_score(scenario.metrics(gate_rows(catches=5, stuck=1.)), baseline)
    better = scenario.selection_score(scenario.metrics(gate_rows(catches=8, stuck=1.)), baseline)
    hunter = scenario.selection_score(scenario.metrics(gate_rows(catches=5, stuck=1., ship_hits=3)), baseline)
    reckless = scenario.selection_score(scenario.metrics(gate_rows(catches=5, stuck=1., ship_hits=3, deaths=2)), baseline)
    assert -math.inf < passing < better and passing < hunter and reckless < hunter
    # Stuck at zero on both sides is not worse than the baseline: the catch rate decides.
    still = scenario.metrics(gate_rows(catches=4, stuck=0.))
    assert scenario.selection_score(scenario.metrics(gate_rows(catches=5, stuck=0.)), still) > -math.inf


def test_selection_score_baseline_is_the_scripted_jelly_on_the_validation_cases(monkeypatch):
    from learning.adapters import jelly_scenario as scenario
    monkeypatch.setattr(scenario, '_baselines', {})
    monkeypatch.setattr(scenario, 'run_horizon', .2)
    baseline = scenario.validation_baseline()
    assert baseline['episodes'] == len(scenario.validation_cases())
    assert baseline is scenario.validation_baseline() and ('validation', .2) in scenario._baselines
    # The scripted Jelly cannot beat itself.
    assert scenario.selection_score(baseline) == -math.inf


def test_compare_returns_interval_keys():
    from learning.adapters import jelly_scenario as scenario
    a = dict(episodes=gate_rows(catches=5, stuck=0.) * 3)
    b = dict(episodes=gate_rows(catches=3, stuck=1.) * 3)
    result = scenario.compare(a, b)
    assert {'mean_extra_catches', 'lower_95', 'upper_95', 'mean_extra_ship_hits', 'mean_extra_jelly_deaths'} <= set(result)
    assert result['lower_95'] <= result['mean_extra_catches'] <= result['upper_95']
    assert result['mean_extra_catches'] == pytest.approx(4 / 3)
    assert scenario.compare(dict(episodes=[]), dict(episodes=[]))['lower_95'] == 0.


def test_validation_and_evaluation_cases_cover_all_three_stages():
    from learning.adapters import jelly_scenario as scenario
    validation, evaluation = scenario.validation_cases(), scenario.evaluation_cases()
    for cases in (validation, evaluation):
        assert {c['stage'] for c in cases} == {1, 2, 3}
        assert {c['level'] for c in cases} == set(scenario.HOLDOUT_LEVELS)
        assert all(c['team_size'] == 1 for c in cases if c['stage'] == 1)
        assert {c['team_size'] for c in cases if c['stage'] == 2} == set(scenario.STAGE2_TEAM_SIZES)
        assert {c['team_size'] for c in cases if c['stage'] == 3} == set(scenario.STAGE3_TEAM_SIZES)
    assert not {c['seed'] for c in validation} & {c['seed'] for c in evaluation}   # selection never sees these
    assert evaluation == [c for stage in scenario.STAGES for c in scenario.evaluation_cases(stage)]
    assert all(c['stage'] == 1 for c in scenario.evaluation_cases(1))


def test_metrics_report_every_evaluation_measure_per_stage():
    from learning.adapters import jelly_scenario as scenario
    summary = scenario.metrics(gate_rows(catches=3, stuck=6., ship_hits=2, deaths=1))
    for key in ('catches_per_minute', 'time_to_contact', 'stuck_fraction', 'angular_spread', 'survival_fraction'):
        assert key in summary, key
    # Time to contact counts an episode without contact as its whole length: (10 + 60 + 60) / 3.
    assert summary['time_to_contact'] == pytest.approx(130 / 3)
    assert summary['stage1_catches_per_minute'] == 3. and summary['stage2_catches_per_minute'] == 3.
    assert summary['stage1_time_to_contact'] == 10. and summary['stage3_survival_fraction'] == .5
    assert summary['stage3_ship_hits'] == 2 and summary['stage2_episodes'] == 1
    assert all(isinstance(v, (int, float)) for v in summary.values())   # train.log lines hold numbers only


def test_time_to_contact_is_the_first_catch_or_ship_hit():
    env, _ = jelly_env(team_size=1)
    try:
        result = env.step(still(env))
        assert result.events['time_to_contact'] is None
        (jelly,) = env.team.members()
        target_ = env.world.additional_targets[0]
        target_.x, target_.y = jelly.x + 3, jelly.y
        target_.vx = target_.vy = 0.
        result = env.step(still(env))
        assert result.events['time_to_contact'] == pytest.approx((DECISION_FRAMES + 1) / 60)
        for _ in range(3):
            result = env.step(still(env))
        assert result.events['time_to_contact'] == pytest.approx((DECISION_FRAMES + 1) / 60)
    finally:
        env.close()


def test_jelly_runs_do_not_bootstrap_from_the_weak_teacher_by_default(tmp_path):
    from learning.tasks import task
    from tools.trainer.control import start
    from tools import ppo_neural
    assert task('jelly_team').fresh_defaults['bootstrap_episodes'] == 0
    calls = []
    start(from_='new', changes={'task': 'jelly_team', 'budget_seconds': 10}, root=tmp_path, processes=[],
          launch=lambda command, log: calls.append(command))
    assert ppo_neural.build_parser().parse_args(calls[0][3:]).bootstrap_episodes == 0


def test_level_27_is_not_a_jelly_training_level_and_every_case_type_visits_every_other_level():
    from learning.adapters import jelly_scenario as scenario
    assert 27 not in scenario.TRAIN_LEVELS
    levels = len(scenario.TRAIN_LEVELS)
    for stage in (1, 2, 3):
        cases = [c for iteration in range(levels*scenario.RETENTION_SHARE)
                 for c in scenario.training_cases(iteration, scenario.RETENTION_SHARE, stage)]
        assert all(c['level'] != 27 for c in cases)
    cases = [c for iteration in range(levels) for c in scenario.training_cases(iteration, 16, 2)]
    # 16 * levels cases span 4 passes of 28; each (stage, team size) must meet every training level
    visited = {}
    for c in cases:
        visited.setdefault((c['stage'], c['team_size']), set()).add(c['level'])
    assert set(visited) == {(1, 1), (2, 2), (2, 3), (2, 4)}
    assert all(seen == set(scenario.TRAIN_LEVELS) for seen in visited.values())


@pytest.mark.parametrize('barrier', ['wall', 'gate'])
def test_teacher_routes_around_a_wall_and_reaches_the_target_without_clipping_it(barrier):
    from maze.wall_segment import WallSegment
    from creatures.jelly_team import advance
    from creatures.wallcrawler_team import capsule_hits
    wall = WallSegment((200, 0), (200, 200), 3)
    goal = (250., 150.)
    (jelly,), enc, team = team_scene(positions=((150., 150.),), ship=target(goal))
    enc.world.maze = SimpleNamespace(walls=[wall], spatial_grid=None, cell_size_x=100, cell_size_y=100,
                                   offset_x=0, offset_y=0, grid_width=4, grid_height=4)
    if barrier == 'gate':
        enc.maze.walls = []
        enc.maze.gate_segments = [wall]
    for _ in range(150):
        intent = adapter.intention(adapter.teacher(jelly, enc), adapter.facing(jelly))
        for _ in range(DECISION_FRAMES):
            before = jelly.get_pos()
            advance(jelly, intent)
            assert not capsule_hits(before, jelly.get_pos(), jelly.radius, wall.start, wall.end)
            if math.dist(jelly.get_pos(), goal) < 15:
                return
    pytest.fail('teacher failed to take the open route around the wall')


def test_teacher_follows_a_wall_when_route_is_unavailable_and_uses_a_new_opening():
    from maze.wall_segment import WallSegment
    wall = WallSegment((200, 0), (200, 400), 3)
    (jelly,), enc, team = team_scene(positions=((150., 150.),), ship=target((250., 150.)))
    enc.world.maze = SimpleNamespace(walls=[wall], spatial_grid=None, cell_size_x=100, cell_size_y=100,
                                   offset_x=0, offset_y=0, grid_width=4, grid_height=4)
    exploring = adapter.intention(adapter.teacher(jelly, enc), adapter.facing(jelly))
    assert exploring.accel > .9 and abs(exploring.heading) > .3
    wall.active = False
    intent = adapter.intention(adapter.teacher(jelly, enc), adapter.facing(jelly))
    assert abs(intent.heading) < .01 and intent.accel > .9


def test_training_pulls_the_policy_toward_what_the_teacher_would_do_in_the_states_it_visits():
    """DAgger: the Jelly flies its own episode, the teacher labels every state it reaches, and updates reduce the
    gap between the policy's heading and the teacher's."""
    import numpy as np
    import torch
    from learning.adapters import jelly_scenario as scenario
    from learning.ppo import update_team
    from learning.training import build_network, collect
    policy = random_policy(adapter.SPEC, 0)
    label = lambda env, i: env.adapter.teacher_action(env, i, None)
    env = scenario.environment(horizon=4.)
    try:
        episodes = collect(env, policy, 7, dict(level=14, team_size=1, stage=1), labeller=label)[0]
    finally:
        env.close()
    assert any(t is not None for t in episodes[0]['teacher'])
    x = torch.as_tensor(np.asarray(episodes[0]['x']), dtype=torch.float32)[None]
    critic = torch.as_tensor(np.asarray(episodes[0]['critic']), dtype=torch.float32)[None]
    taught = torch.as_tensor([t is not None for t in episodes[0]['teacher']])
    target = torch.as_tensor([t[0] if t else 0. for t in episodes[0]['teacher']]).tanh()

    def gap_after_training(teacher_weight):
        torch.manual_seed(0)
        net = build_network(policy, adapter.CRITIC_SIZE)
        optimiser = torch.optim.Adam(net.parameters(), lr=3e-3)
        rng = np.random.default_rng(0)
        for _ in range(30):
            update_team(net, optimiser, episodes, rng, teacher_weight=teacher_weight, teacher_heads=('heading', 'accel'))
        with torch.no_grad():
            return float((net(x, critic)[0]['heading'][0, :, 0].tanh()-target)[taught].square().mean())
    assert gap_after_training(10.) < gap_after_training(0.) * .7


def test_neural_jellies_switch_replaces_every_campaign_jelly_and_leaves_other_enemies(monkeypatch):
    from game_handlers.spawn_manager import make_enemy
    assert make_enemy('aggressive', POS, 5, None).kind.key == 'aggressive'
    monkeypatch.setenv('NEURAL_JELLIES', '1')
    assert make_enemy('aggressive', POS, 5, None).kind.key == 'neural_jelly'
    assert make_enemy('static', POS, 5, None).kind.key == 'static'


def test_a_jelly_senses_the_way_round_a_wall_not_just_the_direction_of_its_target():
    from maze.wall_segment import WallSegment
    wall = WallSegment((200, 0), (200, 200), 3)
    (jelly,), enc, team = team_scene(positions=((150., 150.),), ship=target((250., 150.)))
    jelly.jelly_facing = 0.
    enc.world.maze = SimpleNamespace(walls=[wall], spatial_grid=None, cell_size_x=100, cell_size_y=100,
                                     offset_x=0, offset_y=0, grid_width=4, grid_height=4)
    x, _, _ = adapter.observe(team, jelly)
    assert abs(feature(x, 'target_bearing_sin')) < .01        # the target is dead ahead, behind the wall
    assert feature(x, 'target_route_present') == 1.
    assert feature(x, 'target_route_bearing_sin') > .3        # but the way round starts off to the side
    assert feature(x, 'target_route_distance') * adapter.DISTANCE_SCALE > 100 + 1   # longer than the straight line
    wall.active = False
    x, _, _ = adapter.observe(team, jelly)
    assert abs(feature(x, 'target_route_bearing_sin')) < .01   # nothing in the way: straight at it
    assert math.isclose(feature(x, 'target_route_distance'), 100 / adapter.DISTANCE_SCALE, rel_tol=1e-3)



def test_an_older_jelly_checkpoint_migrates_and_behaves_as_before_until_it_learns_to_use_the_new_inputs(tmp_path):
    old_features = tuple(f for f in adapter.FEATURES if 'route' not in f)
    old_spec = PolicySpec(adapter.SPEC.task, old_features, adapter.SPEC.heads, 2, adapter.SPEC.continuous)
    old = random_policy(old_spec, 4)
    old.mean[:] = np.linspace(-1, 1, len(old_features))
    old.save(tmp_path/'old.npz')
    migrated = adapter.load_transfer_policy(str(tmp_path/'old.npz'))
    assert migrated.spec == adapter.SPEC
    senses = np.random.default_rng(0).uniform(-1, 1, len(adapter.FEATURES)).astype(np.float32)
    kept = np.array([f in old_features for f in adapter.FEATURES])
    old_out, _ = old.step(senses[kept], old.initial_state())
    new_out, _ = migrated.step(senses, migrated.initial_state())   # the route inputs are non-zero and change nothing
    for head in old_out:
        assert np.allclose(old_out[head], new_out[head], atol=1e-5)
