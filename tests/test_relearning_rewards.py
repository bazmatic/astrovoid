"""Completion credit, stage-specific landing rewards and controlled actor damping."""
import math
import numpy as np
import pytest
from learning.adapters.crawler_scenario import CrawlerEnvironment
from learning.adapters.wallcrawler import SPEC
from learning.policy import random_policy
from learning.initialization import dampen_actor


@pytest.mark.parametrize('stage,reward',[('precision',0.),('tracking',0.),('pursuit',0.)])
def test_current_drills_do_not_reward_landings(stage,reward):
    env=CrawlerEnvironment()
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage=stage)
        owner=env.agent_ids[0]
        before=env.agent_returns()[owner]
        env.agent_landings[owner]+=1
        assert env.agent_returns()[owner]-before==reward
        assert env.landing_reward==reward
    finally:env.close()


def test_clear_bonus_is_large_shared_once_and_part_of_real_transition():
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='precision')
        targets=env.world.additional_targets
        for target in targets[1:]:target.active=False
        owner=env.agent_ids[0]
        shot=Projectile(targets[0].get_pos(),0,is_enemy=True);shot.actor_id=owner
        env.world.projectiles.append(shot)
        result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
        assert result.terminated and not result.truncated
        assert result.events['trial_completion_reward']==10
        assert result.events['agent_completion_rewards']=={0:5.,1:5.}
        assert result.agent_rewards[1-owner]==5.
        assert result.agent_rewards[owner]==pytest.approx(6.+.02*env.agent_quality[owner])
        assert result.reward==pytest.approx(sum(result.agent_rewards.values()))
        before=dict(env.agent_completion_rewards)
        env.record_completion()
        assert dict(env.agent_completion_rewards)==before
        with pytest.raises(RuntimeError,match='ended'):env.step({})
    finally:env.close()


@pytest.mark.parametrize('ending',['timeout','death','combat_clear'])
def test_unsuccessful_or_non_drill_trial_never_receives_completion_bonus(ending):
    env=CrawlerEnvironment(horizon=.1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='shooting' if ending=='combat_clear' else 'precision')
        if ending=='timeout':
            result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
            assert result.truncated and result.events['trial_completion_reward']==0
        else:
            for target in env.world.additional_targets:target.active=False
            if ending=='death':
                for crawler in env.team.members():crawler.active=False
            env.record_completion()
            assert env.completion_reward==0
        assert not env.agent_completion_rewards
    finally:env.close()


def test_damping_preserves_backbone_and_softens_only_outputs_without_mutating_source():
    policy=random_policy(SPEC,5,hidden=8,embed=4)
    original={k:v.copy() for k,v in policy.params.items()}
    new=dampen_actor(policy,.5)
    outputs={name+suffix for name,_ in SPEC.heads for suffix in ('_w','_b')}
    for key,value in original.items():
        np.testing.assert_array_equal(policy.params[key],value)
        if key not in outputs:np.testing.assert_array_equal(new.params[key],value)
    for name,_ in SPEC.heads:
        if name in SPEC.continuous:
            np.testing.assert_allclose(new.params[name+'_w'][0],original[name+'_w'][0]*.5)
            assert np.all(new.params[name+'_w'][1]==0)
            assert new.params[name+'_b'][1]==pytest.approx(math.log(.35))
        else:
            np.testing.assert_allclose(new.params[name+'_w'],original[name+'_w']*.5)
            np.testing.assert_allclose(new.params[name+'_b'],original[name+'_b']*.5)
    np.testing.assert_array_equal(new.mean,policy.mean)
    np.testing.assert_array_equal(new.scale,policy.scale)


@pytest.mark.parametrize('factor',[0.,-1.,1.1,float('nan')])
def test_invalid_damping_is_rejected(factor):
    with pytest.raises(ValueError,match='actor scale'):dampen_actor(random_policy(SPEC,0),factor)


@pytest.mark.parametrize('phase',['flight','launch','landing'])
def test_airborne_phases_can_aim_and_fire_with_physical_recoil(phase):
    from tests.test_creature_learning import team_scene
    from creatures.wallcrawler_team import Intent,Landing
    from learning.adapters.wallcrawler import observe,enabled
    crew,enc,team=team_scene()
    crawler=crew[0]
    if phase=='launch':
        crawler.wall_attach_cooldown=0
        site=Landing(enc.maze.walls[1],(400,600),(0,-1),(400,588))
        team.commit({crawler.agent_id:Intent(move=0,aim=.08,fire=True,detach=True)},
                    {crawler.agent_id:[site]+[None]*7})
    else:
        crawler.wall_state='returning';crawler.wall_phase=phase;crawler.wall_in_flight=True
        crawler.x,crawler.y=(400,580) if phase=='landing' else (800,450)
        crawler.vx,crawler.vy=0.,1.
        crawler.wall_destination=(Landing(enc.maze.walls[1],(400,600),(0,-1),(400,588)) if phase=='landing' else None)
        crawler.wall_intent=Intent(move=0,aim=.08,fire=True)
    crawler.gun_cooldown=0
    angle=crawler.angle
    enc.step(1)
    assert crawler.wall_state=='returning' and crawler.just_fired
    assert enc.world.projectiles
    x,masks,_=observe(team,crawler)
    assert masks['aim'].all() and masks['fire'].all()
    assert enabled(x,(1,0.,1,0,0,0),masks)[1:3]==[True,True]
    if phase=='flight':
        shot=enc.world.projectiles[-1]
        ratio=shot.radius**2/crawler.radius**2
        assert crawler.vx==pytest.approx(-ratio*shot.vx)
        assert crawler.vy==pytest.approx(1.-ratio*(shot.vy-1.))
        assert (crawler.angle-angle+180)%360-180==pytest.approx(.24)


def test_battle_horizon_pays_survivors_once_and_death_cost_is_personal():
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        victim=env.team.members()[0]
        env.frames=30
        env.record_battle_outcomes()
        env.enc.kill(victim)
        env.frames=60
        env.record_battle_outcomes()
        returns=env.agent_returns()
        assert returns[victim.agent_id]==pytest.approx(.05-40)
        assert returns[1-victim.agent_id]==pytest.approx(.1+20)
        before=returns.copy()
        env.record_battle_outcomes()
        assert env.agent_returns()==before
        assert env.battle_events()['battle_death_penalty']==-40
        assert env.battle_events()['battle_survival_bonus']==20
    finally:env.close()


def test_battle_jelly_kill_bonus_is_only_for_final_shooter_once():
    from entities.projectile import Projectile
    env=CrawlerEnvironment()
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        target=env.world.additional_targets[0]
        for owner in (0,1):
            shot=Projectile(target.get_pos(),0,is_enemy=True)
            shot.actor_id=owner
            assert env.opponent_hit(shot)
            assert not env.opponent_hit(shot)
        assert env.agent_jelly_kills=={1:1}
        assert env.agent_returns()[0]==1
        assert env.agent_returns()[1]==6
        assert env.battle_events()['battle_kill_reward']==5
    finally:env.close()
