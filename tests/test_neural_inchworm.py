"""Inchworm inference, motor semantics, curriculum and replay. No optimizer runs."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from learning.adapters import inchworm as adapter
from learning.adapters import inchworm_scenario as scenario
from learning.policy import random_policy
from physics.inchworm import InchwormCommand


def test_observation_is_finite_body_relative_and_has_versioned_shape():
    env = scenario.environment(horizon=.2)
    try:
        a = env.reset(12,level=0,stage=3).observations[0]
        b = env.reset(12,level=1,stage=3).observations[0]
        assert a.shape == (len(adapter.FEATURES),) == (83,)
        assert np.isfinite(a).all()
        assert b == pytest.approx(a,abs=1e-5)
        target = env.prey
        wall = type(env.world.maze.walls[0])((env.worm.x-50,(env.worm.y+target.y)/2),
                                            (env.worm.x+50,(env.worm.y+target.y)/2),1)
        # Explicit occlusion uses a wall perpendicular to the current line of sight.
        mid = ((env.worm.worm_front[0]+target.x)/2,(env.worm.worm_front[1]+target.y)/2)
        dx,dy = target.x-env.worm.worm_front[0],target.y-env.worm.worm_front[1]
        wall.start,wall.end = (mid[0]-dy,mid[1]+dx),(mid[0]+dy,mid[1]-dx)
        env.world.maze.walls.append(wall)
        x,masks,_ = adapter.observe(env.worm,env.enc)
        assert x[adapter.FEATURES.index('target_present')] == 0
        assert not masks['bite'][1]
    finally:
        env.close()


def test_motor_conversion_clips_through_tanh_and_has_no_twist_output():
    command = adapter.intention((100.,-100.,0.,.2,-.2,1,0,1))
    assert command.muscles[:3] == (1.,-1.,0.)
    assert command.rear_grip and not command.front_grip and command.bite
    assert len(adapter.HEADS) == 8 and all('twist' not in n for n,_ in adapter.HEADS)
    for bad in ((0.,)*7,(float('nan'),)*8,(0.,)*5+(2,0,0)):
        with pytest.raises(ValueError):
            adapter.intention(bad)


def test_policy_round_trip_rejects_wrong_task_and_bad_normalization(tmp_path):
    policy = random_policy(adapter.SPEC,2,hidden=8,embed=4)
    path = tmp_path/'weights.npz'
    policy.save(path)
    loaded = adapter.load_policy(path)
    x = np.zeros(len(adapter.FEATURES),np.float32)
    assert loaded.choose(x,loaded.initial_state())[0] == policy.choose(x,policy.initial_state())[0]
    policy.mean[0] = np.nan
    policy.save(path)
    with pytest.raises(ValueError,match='normalization'):
        adapter.load_policy(path)
    from learning.adapters.flocker import SPEC as FLOCKER_SPEC
    random_policy(FLOCKER_SPEC).save(path)
    with pytest.raises(ValueError,match='schema'):
        adapter.load_policy(path)


def test_game_loads_once_with_independent_memory_and_external_override(tmp_path,monkeypatch):
    import creatures
    from tests.creature_parts import encounter,world,open_maze
    path = tmp_path/'policy.npz'
    random_policy(adapter.SPEC,1,hidden=8,embed=4).save(path)
    monkeypatch.setenv('INCHWORM_POLICY',str(path))
    a,b = creatures.build('inchworm',(400.,200.)),creatures.build('inchworm',(500.,200.))
    enc = encounter(a,b,world_=world(maze=open_maze()))
    enc.ready()
    assert a.worm_driver.policy is b.worm_driver.policy
    assert a.worm_driver.state is not b.worm_driver.state
    a.worm_command = InchwormCommand()
    enc.step(1.)
    assert not a.worm_driver.state.any()  # an external controller retains priority
    assert b.worm_driver.state.any()
    enc.close()
    assert a.worm_driver is None and b.worm_driver is None


def test_missing_selected_policy_logs_and_falls_back(monkeypatch,caplog):
    from tests.test_inchworm_creature import setting
    monkeypatch.setenv('INCHWORM_POLICY','/no/such/inchworm.npz')
    c,enc = setting()
    assert c.worm_driver is None
    enc.step(1.)
    assert c.worm_front_grip
    assert 'using reflex controller' in caplog.text
    enc.close()


@pytest.mark.parametrize('stage',range(1,6))
def test_each_lesson_collects_finite_trajectories_without_learning(stage):
    from learning.training import collect
    env = scenario.environment(horizon=.2)
    policy = random_policy(adapter.SPEC,2,hidden=8,embed=4)
    try:
        trajectories,events,trace = collect(env,policy,12,dict(level=0,stage=stage))
        assert len(trajectories)==1 and len(trace)==2
        assert len(trajectories[0]['actions'][0])==8
        assert np.isfinite(trajectories[0]['x']).all()
        assert np.isfinite(trajectories[0]['rewards']).all()
        assert not trajectories[0]['terminated']
        with pytest.raises(RuntimeError):
            env.step({0:(0.,)*8})
    finally:
        env.close()


def test_curriculum_requires_two_held_out_passes_and_keeps_prior_lessons():
    state = scenario.initial_curriculum(None)
    assert scenario.advance_curriculum(state,dict(success=1.)) == state
    evidence = scenario.validation_evidence(dict(success=1.,survived=1.),state,None)
    state = scenario.advance_curriculum(state,evidence)
    assert state == dict(stage=1,passing_blocks=1)
    state = scenario.advance_curriculum(state,evidence)
    assert state['stage']==2
    cases = scenario.training_cases(0,24,5,curriculum=dict(stage=5))
    assert {c['stage'] for c in cases} == set(range(1,6))
    assert {c['level'] for c in cases}.isdisjoint(c['level'] for c in scenario.validation_cases())
    assert {c['seed'] for c in scenario.evaluation_cases()}.isdisjoint(c['seed'] for c in scenario.validation_cases())
    assert {c['stage'] for c in scenario.training_cases(0,40,1,bootstrap=True)} == set(range(1,6))


def test_recorded_actions_replay_exactly_and_rule_changes_are_rejected(tmp_path):
    from learning import replay
    from learning.training import collect
    env = scenario.environment(horizon=.3)
    case = dict(seed=18,level=4,stage=5)
    try:
        _,events,trace = collect(env,random_policy(adapter.SPEC,1,hidden=8,embed=4),
                               case['seed'],dict(level=case['level'],stage=case['stage']))
    finally:
        env.close()
    manifest = scenario.metadata(SimpleNamespace(horizon=.3))
    manifest['training'] = {}
    config = dict(task='inchworm',manifest=manifest)
    (tmp_path/'config.json').write_text(json.dumps(config))
    (tmp_path/'episodes').mkdir()
    (tmp_path/'episodes/iter0000.json').write_text(json.dumps(dict(jobs=[case],episodes=[dict(events,**case)],actions=[trace])))
    result, = replay.fly(tmp_path,0)
    assert result['return'] == pytest.approx(events['return_total'])
    config['manifest']['scenario_version'] += 1
    (tmp_path/'config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError,match='rules'):
        replay.open_environment(tmp_path)


def test_preset_and_task_defaults_are_consistent_and_do_not_launch(monkeypatch):
    from tools.ppo_neural import build_parser
    from learning.tasks import task
    preset = json.loads((Path(__file__).resolve().parents[1]/'config/training/inchworm.json').read_text())
    args = build_parser().parse_args(['--task','inchworm'])
    for key,value in task('inchworm').fresh_defaults.items():
        assert getattr(args,key) == value == preset[key]
    overridden = build_parser().parse_args(['--task','inchworm','--episodes','2','--bootstrap-episodes=0'])
    assert overridden.episodes==2 and overridden.bootstrap_episodes==0
    assert task('inchworm').adapter().USES_OPPONENT is False
    assert 'inchworm' in task('inchworm').label.lower()
    from tools.trainer.settings import applies_to
    assert applies_to('inchworm_bite_reward') == ('inchworm',)


def test_deployment_requires_all_lessons_and_matched_cases():
    assert not scenario.deployment_report({'trained':{'episodes':[]},'scripted':{'episodes':[]}},None)['passed']
    a = dict(stage=1,level=1,seed=1,success=1.)
    with pytest.raises(ValueError,match='match'):
        scenario.compare({'episodes':[a]},{'episodes':[dict(a,seed=2)]})


def test_cli_dispatch_keeps_planned_horizon_without_running_training(monkeypatch):
    import learning.run
    from tools.ppo_neural import main
    seen = []
    def record_only(args):
        seen.append(args)
        return dict(paused=False,last='not-started')
    monkeypatch.setattr(learning.run,'train',record_only)
    main(['--task','inchworm'])
    assert seen[-1].horizon == 45.
    main(['--task','inchworm','--horizon=2'])
    assert seen[-1].horizon == 2.


def test_game_inference_and_external_training_actions_share_cadence_through_stun():
    a,b = scenario.environment(horizon=2.),scenario.environment(horizon=2.)
    policy = random_policy(adapter.SPEC,3,hidden=8,embed=4)
    try:
        a.reset(12); b.reset(12)
        a.worm.worm_driver = adapter.InchwormDriver(policy)
        state = policy.initial_state()
        for decision in range(12):
            if decision == 2:
                a.worm.worm_stun = b.worm.worm_stun = 10.
            x,masks,_ = adapter.observe(b.worm,b.enc)
            action,state = policy.choose(x,state,masks)
            b.step({0:action})
            for _ in range(adapter.DECISION_FRAMES):
                a.enc.step(1.)
            assert a.worm.get_pos() == pytest.approx(b.worm.get_pos(),abs=1e-7)
            assert a.worm.worm_driver.state == pytest.approx(state,abs=1e-7)
    finally:
        a.close(); b.close()
