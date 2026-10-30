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
