"""Training seams, legal actions, local communication and actual damage events."""
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from learning.policy import PolicySpec, RecurrentPolicy, random_policy
from learning.models import load_into, network_class
from creatures.wallcrawler_team import get_team, Intent, Landing, candidates
from learning.adapters.wallcrawler import observe, SPEC, intention, enabled
from tests.creature_parts import encounter, world, open_maze, target
from maze.wall_segment import WallSegment
import creatures


def team_scene(positions=((400,312),(500,312))):
    walls = [WallSegment((200,300),(1000,300),4), WallSegment((200,600),(1000,600),4)]
    crew = [creatures.build('wallcrawler',p) for p in positions]
    enc = encounter(*crew,world_=world(maze=open_maze(walls),ship=target((600,500))))
    enc.world.ship.vx = enc.world.ship.vy = 0
    enc.ready()
    team = get_team(enc); team.external=True;team.members()
    return crew, enc, team


def test_arbitrary_heads_have_matching_numpy_and_torch_inference(tmp_path):
    import torch
    spec=PolicySpec('other',('a','b'),(('walk',5),('signal',4)))
    p=random_policy(spec,3,hidden=7,embed=5)
    net=network_class(2,dict(spec.heads))(7,5);load_into(net,p,dict(spec.heads))
    senses=np.random.default_rng(4).normal(size=(9,2)).astype(np.float32)
    with torch.no_grad(): z,state=net(torch.from_numpy(senses)[None])
    hidden=p.initial_state()
    for t,x in enumerate(senses):
        logits,hidden=p.step(x,hidden)
        for k in logits: np.testing.assert_allclose(logits[k],z[k][0,t].numpy(),atol=1e-6)
    path=tmp_path/'p.npz';p.save(path)
    q=RecurrentPolicy.load(path,spec)
    np.testing.assert_array_equal(p.step(senses[0],p.initial_state())[0]['walk'],q.step(senses[0],q.initial_state())[0]['walk'])
    with pytest.raises(ValueError,match='schema'):
        RecurrentPolicy.load(path,PolicySpec('wrong',spec.features,spec.heads))


def test_local_radio_is_delayed_and_does_not_need_line_of_sight():
    crew,enc,team=team_scene()
    enc.maze.walls.append(WallSegment((450,250),(450,600),4))
    team.commit({crew[0].agent_id:Intent(message=5),crew[1].agent_id:Intent(message=2)})
    assert team.inbox(crew[1]) == {}
    team.advance()
    assert team.inbox(crew[1])[crew[0].agent_id]==5
    assert team.inbox(crew[0])[crew[1].agent_id]==2
    assert team.inbox(crew[1],muted=True)=={}
    crew[1].x=900
    assert team.inbox(crew[1])=={}


def test_radio_is_roster_order_independent_and_releases_dead_senders():
    crew,enc,team=team_scene()
    actions={c.agent_id:Intent(message=c.agent_id+2) for c in crew}
    enc.roster._enemies.reverse()
    team.commit(actions);team.advance()
    assert team.inbox(crew[1])[crew[0].agent_id]==2
    crew[0].die();team.clean()
    assert team.inbox(crew[1])=={}


def test_actor_does_not_see_hidden_ship_or_private_teammate_target():
    crew,enc,team=team_scene()
    enc.maze.walls.append(WallSegment((200,400),(1000,400),4))
    x,_,_=observe(team,crew[0])
    start=SPEC.features.index('target_present')
    assert np.all(x[start:start+6]==0)
    enc.world.ship.x+=100
    y,_,_=observe(team,crew[0])
    np.testing.assert_array_equal(x,y)


def test_airborne_actions_are_masked_but_messages_are_enabled():
    crew,enc,team=team_scene();c=crew[0];c.wall_state='stunned'
    x,masks,_=observe(team,c)
    assert masks['fire'].tolist()==[True,False]
    assert masks['move'].tolist()==[False,True,False]
    assert masks['detach'].tolist()==[True,False]
    assert enabled(x,(1,1,0,0,0,7),masks)==[False,False,False,False,False,True]


def test_reservations_do_not_stack_and_priority_rotates():
    crew,enc,team=team_scene()
    for c in crew:c.wall_attach_cooldown=0
    wall=enc.maze.walls[1]
    site=Landing(wall,(450,600),(0,-1),(450,588))
    sites={c.agent_id:[site]+[None]*7 for c in crew}
    team.commit({c.agent_id:Intent(detach=True,landing=0) for c in crew},sites)
    assert list(team.reservations)==[crew[0].agent_id]
    assert crew[0].wall_state=='returning' and crew[0].wall_stun==0
    assert crew[1].wall_state=='attached'
    crew[0].die();team.clean();assert team.reservations=={}


def test_candidates_are_reachable_and_avoid_occupied_bodies():
    crew,enc,team=team_scene();c=crew[0];c.wall_attach_cooldown=0
    from creatures.wallcrawler_team import path_clear,space_free
    sites=[s for s in candidates(c,enc) if s is not None]
    assert sites
    assert all(path_clear(c,enc,s.position) and space_free(c,enc,s.position) for s in sites)


def test_walking_and_airborne_bodies_cannot_overlap():
    import math
    crew,enc,team=team_scene(((430,312),(470,312)))
    crew[0].wall_intent=Intent(move=-1);crew[1].wall_intent=Intent(move=1)
    for _ in range(100):
        enc.step(1)
        assert math.dist(crew[0].get_pos(),crew[1].get_pos()) >= 21-1e-4
    c=crew[0];c.wall_state='stunned';c.wall_stun=30;c.vx=15;c.vy=0
    for _ in range(10):
        enc.step(1)
        assert math.dist(crew[0].get_pos(),crew[1].get_pos()) >= 21-1e-4
        assert not c.just_fired


def test_selected_landing_is_cancelled_when_wall_is_destroyed():
    crew,enc,team=team_scene();c=crew[0];c.wall_attach_cooldown=0
    wall=enc.maze.walls[1];site=Landing(wall,(450,600),(0,-1),(450,588))
    team.commit({c.agent_id:Intent(detach=True)}, {c.agent_id:[site]+[None]*7})
    wall.active=False
    for _ in range(100):enc.step(1)
    assert c.wall_state=='returning' and c.wall_destination is None
    assert c.agent_id not in team.reservations


def test_gae_distinguishes_truncation_termination_and_padding():
    import torch
    from learning.ppo import bootstrapped_gae
    r=v=torch.zeros(2,3)
    valid=torch.tensor([[True,False,False],[True,True,True]])
    done=torch.zeros(2,3,dtype=torch.bool);done[1,-1]=True
    advantages,_=bootstrapped_gae(r,v,valid,done,torch.tensor([2.,2.]),1,1)
    assert advantages[0,0]==2 and advantages[0,1]==0
    assert advantages[1].sum()==0


def test_team_critic_cannot_change_actor_outputs_and_messages_receive_gradients():
    import torch
    from learning.training import build_network
    from learning.ppo import masked_statistics
    p=random_policy(SPEC,4,hidden=8,embed=4);net=build_network(p,52)
    x=torch.ones(1,3,len(SPEC.features))
    a,_=net(x,torch.zeros(1,3,52));b,_=net(x,torch.ones(1,3,52))
    for k in a:torch.testing.assert_close(a[k],b[k])
    actions=torch.zeros(1,3,6,dtype=torch.long)
    legal={k:torch.ones_like(z,dtype=torch.bool) for k,z in a.items()}
    active=torch.zeros(1,3,6);active[:,:,-1]=1
    lp,_=masked_statistics(a,actions,legal,active)
    (-lp.mean()).backward()
    assert net.heads['message'].weight.grad.abs().sum()>0
    assert net.heads['fire'].weight.grad.abs().sum()==0


def test_actual_trial_is_deterministic_and_credits_a_dead_shooters_hit_once():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.wallcrawler import teacher
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=.2)
    def trial():
        first=env.reset(321,level=11,team_size=2)
        action={c.agent_id:teacher(c,env.enc) for c in env.team.members()}
        result=env.step(action)
        return first,result
    a,ra=trial();b,rb=trial()
    for i in a.observations:np.testing.assert_array_equal(a.observations[i],b.observations[i])
    assert ra.events==rb.events
    c=env.world.roster.all()[0];c.die()
    shot=Projectile(env.world.ship.get_pos(),0,is_enemy=True);shot.actor_id=c.agent_id
    handler=env.world.collision_handler
    env.world.ship.shield_active=True
    assert not handler.handle_projectile_ship_collision(shot,env.world.ship,env.world.scoring)
    assert env.hits==0
    env.world.ship.shield_active=False
    assert handler.handle_projectile_ship_collision(shot,env.world.ship,env.world.scoring)
    env._hit(shot)
    assert env.hits==1 and env.contributions[c.agent_id]==1
    env.close()


def test_manager_can_start_fresh_team_without_hunter_checkpoint(tmp_path):
    from tools.trainer.control import start
    from tools import ppo_neural
    calls=[]
    result=start(from_='new',changes={'task':'wallcrawler_team','budget_seconds':10},root=tmp_path,
                 processes=[],launch=lambda command,log:calls.append(command))
    assert result.started_from=='random'
    args=ppo_neural.build_parser().parse_args(calls[0][3:])
    assert args.task=='wallcrawler_team' and args.workers==4 and args.horizon==60 and args.start==''


def test_shared_collector_steps_real_hunter_and_crawler_adapters():
    from learning.training import collect
    from learning.adapters.hunter import HunterEnvironment,SPEC as HUNTER_SPEC
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    for env,spec,case in ((HunterEnvironment(horizon=.2),HUNTER_SPEC,{'level':14}),
                          (CrawlerEnvironment(horizon=.2),SPEC,{'level':11,'team_size':2})):
        try:
            episodes,events,trace=collect(env,random_policy(spec,hidden=8,embed=4),33,case)
            assert trace and all(e['alive'][0] for e in episodes)
            assert all(len(e['x'])==len(e['rewards']) for e in episodes)
            assert all(not e['terminated'] for e in episodes)
        finally:
            env.close()


def test_scripted_and_neural_aim_have_same_turn_rate_and_outward_limit():
    crew,enc,team=team_scene();c=crew[0]
    for neural in (True,False):
        c.angle=90
        if neural:c.wall_intent=Intent(move=0,aim=-1,fire=True)
        else:c.__dict__.pop('wall_intent',None)
        enc.step(1)
        assert abs(c.angle-90)<=3.001
        if neural:
            for _ in range(100):enc.step(1)
            assert c.angle>=1-1e-6


def test_reservation_priority_rotates_and_attachment_cooldown_blocks_hops():
    for tick in (0,1):
        crew,enc,team=team_scene();team.tick=tick
        site=Landing(enc.maze.walls[1],(450,600),(0,-1),(450,588))
        actions={c.agent_id:Intent(detach=True) for c in crew}
        sites={c.agent_id:[site]+[None]*7 for c in crew}
        for c in crew:c.wall_attach_cooldown=60
        team.commit(actions,sites);assert not team.reservations
        for c in crew:c.wall_attach_cooldown=0
        team.commit(actions,sites)
        assert list(team.reservations)==[crew[tick].agent_id]


@pytest.mark.parametrize('state',['stunned','returning'])
def test_airborne_neural_fire_intentions_are_ignored_but_radio_operates(state):
    crew,enc,team=team_scene();c=crew[0];c.wall_state=state;c.y=400;c.wall_stun=36
    c.gun_charge=1
    for _ in range(3):
        team.commit({c.agent_id:Intent(fire=True,message=7)})
        enc.step(1);team.advance()
        assert c.wall_state!='attached' and not c.just_fired and not enc.world.projectiles
        assert team.inbox(crew[1])[c.agent_id]==7


def test_joint_collection_isolates_memory_normalisation_and_dead_agent_masks():
    from learning.environment import Snapshot,Transition
    from learning.training import collect
    calls=[]
    class ProbePolicy:
        spec=PolicySpec('probe',('a','b'),(('move',5),('symbol',4)))
        mean=np.ones(2,np.float32)
        scale=np.full(2,2,np.float32)
        def initial_state(self):return 0
        def choose(self,x,state,masks,greedy,rng):
            calls.append((int(x[0]),state))
            return (int(rng.integers(5)),int(rng.integers(4))),state+int(x[0])
    class Probe:
        adapter=SimpleNamespace(enabled=lambda *args:[True,True])
        def reset(self,seed):
            self.t=0;self.action_trace=[]
            return self.snapshot()
        def snapshot(self):
            ids=(0,1) if self.t==0 else (1,)
            return Snapshot({i:np.array([2+3*i,1],np.float32) for i in ids},
                {i:{'move':np.ones(5,bool),'symbol':np.ones(4,bool)} for i in ids},np.array([self.t],np.float32))
        def step(self,actions):
            self.action_trace.append(actions);self.t+=1
            return Transition(self.snapshot(),1.,False,self.t==3,{})
    a,_,trace=collect(Probe(),ProbePolicy(),3,{})
    assert calls==[(2,0),(5,0),(5,5),(5,10)]
    assert a[0]['alive']==[True,False,False] and a[1]['alive']==[True,True,True]
    assert a[0]['rewards']==[1.,1.,1.]
    np.testing.assert_array_equal(a[0]['x'][0],[.5,0])
    assert all(0 not in actions for actions in trace[1:])


def test_no_landing_waits_airborne_and_throttles_repeated_global_search(monkeypatch):
    import creatures.wallcrawler_team as module
    crew,enc,team=team_scene();c=crew[0];c.wall_state='returning'
    calls=[]
    monkeypatch.setattr(module,'candidates',lambda *args,**kwargs:calls.append(kwargs) or [])
    assert team.reserve_return(c) is None and len(calls)==2
    for frame in range(1,30):
        team.frames=frame
        assert team.reserve_return(c) is None
    assert len(calls)==2
    team.frames=30;team.reserve_return(c)
    assert len(calls)==4 and c.wall_state=='returning'


def test_voluntary_landing_candidates_stay_in_a_forward_ninety_degree_cone():
    import math
    crew,enc,team=team_scene();c=crew[0];c.wall_attach_cooldown=0
    sites=[s for s in candidates(c,enc) if s is not None]
    assert sites
    for site in sites:
        dx,dy=site.position[0]-c.x,site.position[1]-c.y
        assert dy>=math.hypot(dx,dy)*math.cos(math.pi/4)-1e-6
        assert math.hypot(dx,dy)<=300
    c.angle=270
    assert not any(candidates(c,enc))
    # Damage recovery can still find the nearest available wall behind it.
    assert candidates(c,enc,include_near=True)


def test_free_flight_keeps_angular_momentum_through_zero_without_firing():
    import math
    crew,enc,team=team_scene();c=crew[0]
    c.wall_state='returning';c.wall_phase='flight';c.wall_in_flight=True
    c.x,c.y=800,800;c.vx,c.vy=1,1
    c.angle=c.wall_body_angle=350;c.wall_angular_velocity=math.radians(60)
    c.wall_intent=Intent(fire=True)
    for _ in range(30):
        previous=c.angle
        enc.step(1)
        assert c.wall_state=='returning' and not c.just_fired
        assert (c.angle-previous+180)%360-180==pytest.approx(1)
    assert c.angle==pytest.approx(20)


def test_ppo_updates_learned_message_actions_without_a_fire_learning_signal():
    import torch
    from learning.training import build_network
    from learning.ppo import update_team
    p=random_policy(SPEC,7,hidden=8,embed=4);net=build_network(p,52)
    episodes=[]
    for symbol,reward in ((1,1.),(2,-1.)):
        episodes.append(dict(x=[np.ones(len(SPEC.features),np.float32)]*3,
            critic=[np.zeros(52,np.float32)]*3,actions=[(1,1,0,0,0,symbol)]*3,
            alive=[True]*3,rewards=[reward]*3,enabled=[[False]*5+[True]]*3,
            legal={k:[np.ones(n,bool)]*3 for k,n in SPEC.heads},terminated=True,
            final_critic=np.zeros(52,np.float32)))
    before={k:net.heads[k].weight.detach().clone() for k in ('message','fire')}
    update_team(net,torch.optim.Adam(net.parameters(),lr=.01),episodes,np.random.default_rng(0),epochs=1)
    assert not torch.equal(before['message'],net.heads['message'].weight)
    torch.testing.assert_close(before['fire'],net.heads['fire'].weight)


def test_curriculum_including_bootstrap_starts_with_two_and_excludes_holdouts():
    from learning.adapters.crawler_scenario import training_cases,HOLDOUT_LEVELS,promote
    for bootstrap in (False,True):
        cases=training_cases(0,8,2,bootstrap=bootstrap)
        assert all(c['team_size']==2 and c['level'] not in HOLDOUT_LEVELS for c in cases)
        assert not any(c['seed'] in (1000,1001) for c in cases)
    assert promote(2,{'hit_probability':.5,'hits':8,'episodes':8})==4
    assert promote(4,{'hit_probability':.5,'hits':8,'episodes':8})==6
    assert promote(2,{'hit_probability':.25,'hits':8,'episodes':8})==2
