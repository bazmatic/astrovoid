"""Training seams, legal actions, local communication and actual damage events."""
from pathlib import Path
from collections import Counter
import math
from types import SimpleNamespace
import numpy as np
import pytest

from learning.policy import PolicySpec, RecurrentPolicy, random_policy
from learning.models import load_into, network_class
from creatures.wallcrawler_team import get_team, Intent, Landing, candidates
from learning.adapters.wallcrawler import observe, SPEC, intention, enabled, CRITIC_SIZE
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
    start=SPEC.features.index('player_present')
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
    assert enabled(x,(1,0.,0,0,0,7),masks)==[False,False,False,False,False,True]


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
    p=random_policy(SPEC,4,hidden=8,embed=4);net=build_network(p,CRITIC_SIZE)
    x=torch.ones(1,3,len(SPEC.features))
    a,_=net(x,torch.zeros(1,3,CRITIC_SIZE));b,_=net(x,torch.ones(1,3,CRITIC_SIZE))
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
    hunter=env.opponent
    assert hunter.type=='allied_hunter' and env.world.ship is None
    assert hunter.current_rotation_speed==5
    health=hunter.health
    shot=Projectile(hunter.get_pos(),0,is_enemy=True);shot.actor_id=c.agent_id
    hunter.immunity_remaining=.1
    assert env.opponent_hit(shot)
    assert env.hits==0 and not shot.active
    shot=Projectile(hunter.get_pos(),0,is_enemy=True);shot.actor_id=c.agent_id
    hunter.immunity_remaining=0
    assert env.opponent_hit(shot)
    env._hit(shot)
    assert env.hits==1 and env.contributions[c.agent_id]==1
    assert hunter.health==health and hunter.active and hunter.immunity_remaining>0
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
def test_airborne_firing_and_radio_work_but_stun_blocks_firing(state):
    crew,enc,team=team_scene();c=crew[0];c.wall_state=state;c.y=400;c.wall_stun=36
    c.gun_charge=1;c.gun_cooldown=0
    for _ in range(3):
        team.commit({c.agent_id:Intent(fire=True,message=7)})
        enc.step(1);team.advance()
        assert c.wall_state!='attached'
        assert bool(enc.world.projectiles)==(state=='returning')
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


def test_free_flight_keeps_angular_momentum_while_stabilized_gun_fires():
    import math
    crew,enc,team=team_scene();c=crew[0]
    c.wall_state='returning';c.wall_phase='flight';c.wall_in_flight=True
    c.x,c.y=800,800;c.vx,c.vy=1,1
    c.angle=c.wall_body_angle=350;c.wall_angular_velocity=math.radians(60)
    c.wall_intent=Intent(fire=True)
    for _ in range(30):
        previous=c.wall_body_angle
        enc.step(1)
        assert c.wall_state=='returning'
        assert (c.wall_body_angle-previous+180)%360-180==pytest.approx(1)
        assert c.angle==pytest.approx(350)
    assert c.wall_body_angle==pytest.approx(20)
    assert enc.world.projectiles


def test_ppo_updates_learned_message_actions_without_a_fire_learning_signal():
    import torch
    from learning.training import build_network
    from learning.ppo import update_team
    p=random_policy(SPEC,7,hidden=8,embed=4);net=build_network(p,CRITIC_SIZE)
    episodes=[]
    for symbol,reward in ((1,1.),(2,-1.)):
        episodes.append(dict(x=[np.ones(len(SPEC.features),np.float32)]*3,
            critic=[np.zeros(CRITIC_SIZE,np.float32)]*3,actions=[(1,0.,0,0,0,symbol)]*3,
            alive=[True]*3,rewards=[reward]*3,enabled=[[False]*5+[True]]*3,
            legal={k:[np.ones(n,bool)]*3 for k,n in SPEC.heads},terminated=True,
            final_critic=np.zeros(CRITIC_SIZE,np.float32)))
    before={k:net.heads[k].weight.detach().clone() for k in ('message','fire')}
    update_team(net,torch.optim.Adam(net.parameters(),lr=.01),episodes,np.random.default_rng(0),epochs=1)
    assert not torch.equal(before['message'],net.heads['message'].weight)
    torch.testing.assert_close(before['fire'],net.heads['fire'].weight)


def test_player_and_hunter_have_independent_visible_observations():
    crew,enc,team=team_scene();c=crew[0]
    enc.world.hunter=target((500,350));enc.world.hunter.vx=2;enc.world.hunter.vy=-1
    enc.world.hunter.get_pos=lambda:(enc.world.hunter.x,enc.world.hunter.y)
    def senses():return observe(team,c)[0]
    player=SPEC.features.index('player_present');hunter=SPEC.features.index('hunter_present')
    a=senses();assert a[player]==a[hunter]==1
    assert not np.array_equal(a[player:player+6],a[hunter:hunter+6])
    enc.world.ship.observer=True
    b=senses();assert np.all(b[player:player+6]==0)
    np.testing.assert_array_equal(b[hunter:hunter+6],a[hunter:hunter+6])
    enc.world.ship=None
    np.testing.assert_array_equal(senses(),b)
    enc.world.hunter.x=1600
    assert np.all(senses()[hunter:hunter+6]==0)
    enc.world.hunter.x=500
    enc.maze.walls.append(WallSegment((450,300),(450,400),4))
    assert np.all(senses()[hunter:hunter+6]==0)


@pytest.mark.parametrize('mode', ['hunter','mixed'])
def test_opponent_scenarios_are_deterministic_and_both_ships_can_be_hit(mode):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=.2)
    try:
        def trial():
            snap=env.reset(339,level=11,team_size=2,opponents=mode)
            result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
            return snap,result,env.opponent.get_pos(),env.world.ship.get_pos() if env.world.ship else None
        a,ra,ha,pa=trial();b,rb,hb,pb=trial()
        assert ra.events==rb.events and ha==hb and pa==pb
        for i in a.observations:np.testing.assert_array_equal(a.observations[i],b.observations[i])
        assert (env.world.ship is not None)==(mode=='mixed')
        assert len(b.critic)==CRITIC_SIZE
        if mode=='mixed':
            ship=env.world.ship;owner=env.agent_ids[0]
            shot=Projectile(ship.get_pos(),0,is_enemy=True);shot.actor_id=owner
            ship.shield_active=True
            assert not env.world.collision_handler.handle_projectile_ship_collision(shot,ship,env.world.scoring)
            assert env.hits==0
            ship.shield_active=False
            assert env.world.collision_handler.handle_projectile_ship_collision(shot,ship,env.world.scoring)
            assert env.hits==1
            shot=Projectile(env.opponent.get_pos(),0,is_enemy=True);shot.actor_id=owner
            env.opponent.immunity_remaining=0
            assert env.opponent_hit(shot) and env.hits==2
    finally:env.close()


def test_neural_player_matches_hunter_controls_and_has_independent_memory():
    import config
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=.2)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='mixed')
        player,hunter=env.world.ship,env.opponent
        assert player.current_rotation_speed==hunter.current_rotation_speed
        assert player.thrust_force==hunter.thrust_force
        assert player.max_speed==hunter.max_speed and player.friction==hunter.friction
        assert player.current_rotation_speed != config.SHIP_ROTATION_SPEED
        a,b=env.player.controller,env.hunter.flight.controller
        assert a is not b and not np.shares_memory(a._state,b._state)
        before=b._state.copy();a._state[:]=1
        np.testing.assert_array_equal(b._state,before)
        # Changing global player controls cannot leak into either frozen opponent.
        assert player.base_rotation_speed==config.SETTINGS.hunterShip.rotationSpeed*env.opponent.settings.turn_rate_multiplier
    finally:env.close()


def test_previous_crawler_observation_checkpoint_is_rejected(tmp_path):
    old=PolicySpec(SPEC.task,SPEC.features,SPEC.heads,version=2)
    path=tmp_path/'old.npz';random_policy(old).save(path)
    with pytest.raises(ValueError,match='schema'):
        RecurrentPolicy.load(path,SPEC)


@pytest.mark.parametrize('source', ['player','hunter'])
def test_practice_ship_bullets_take_forty_hits_to_kill_a_crawler(source):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=.2)
    try:
        env.reset(339,level=11,team_size=2,opponents='mixed')
        c=env.world.roster.alive()[0]
        shot=Projectile(c.get_pos(),0,source=source)
        enemy=Projectile(c.get_pos(),0,is_enemy=True)
        env.world.projectiles=[shot,enemy];env.weaken_ship_shots()
        assert shot.creature_damage==.1
        assert not hasattr(enemy,'creature_damage')
        for _ in range(39):env.enc.apply_hit(c,shot)
        assert c.active and c.hit_points==pytest.approx(.1)
        env.enc.apply_hit(c,shot)
        assert not c.active and env.hits==0
    finally:env.close()


def test_regular_gameplay_projectiles_still_take_one_crawler_health():
    from entities.projectile import Projectile
    crew,enc,team=team_scene();c=crew[0]
    enc.apply_hit(c,Projectile(c.get_pos(),0,source='player'))
    assert c.hit_points==3 and c.active


def test_movement_only_policy_preserves_movement_and_memory_but_disables_fire():
    from learning.adapters.player_pilot import MovementOnlyPolicy
    class AlwaysFires:
        def initial_state(self):return np.zeros(2)
        def act(self,x,state,*args,**kwargs):return (2,True,True),state+1
    policy=MovementOnlyPolicy(AlwaysFires())
    action,state=policy.act(None,policy.initial_state())
    assert action==(2,True,False)
    np.testing.assert_array_equal(state,np.ones(2))


def test_both_frozen_opponents_cannot_fire_even_if_network_requests_it():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.player_pilot import MovementOnlyPolicy
    class AlwaysFires:
        def initial_state(self):return np.zeros(2)
        def act(self,x,state,*args,**kwargs):return (2,True,True),state
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='mixed')
        controllers=(env.hunter.flight.controller,env.player.controller)
        for controller in controllers:
            assert isinstance(controller.policy,MovementOnlyPolicy)
            controller.policy.policy=AlwaysFires()
        start=(env.opponent.angle,env.world.ship.angle)
        for _ in range(30):
            env.hunter.frame(env.world);env.player.frame(env.world)
        assert env.world.projectiles==[]
        assert env.opponent.shots_fired==0
        assert (env.opponent.angle,env.world.ship.angle)!=start
        assert all(not controller.last_controls[2] for controller in controllers)
    finally:env.close()


def test_jump_cost_counts_successful_launches_not_rejected_or_airborne_requests():
    from learning.adapters.crawler_scenario import CrawlerEnvironment,JUMP_COST
    crew,enc,team=team_scene()
    for c in crew:c.wall_attach_cooldown=0
    site=Landing(enc.maze.walls[1],(450,600),(0,-1),(450,588))
    env=CrawlerEnvironment();env.team=team;env.voluntary_jumps=0;env.agent_jumps=Counter()
    env._pending_landings=set()
    env._sites={c.agent_id:[site]+[None]*7 for c in crew}
    actions={c.agent_id:(1,0.,0,1,0,0) for c in crew}
    env.commit_actions(actions)
    assert env.voluntary_jumps==1 and JUMP_COST==.1
    env.commit_actions(actions)
    assert env.voluntary_jumps==1
    # An externally dislodged crawler was never attached at commit time.
    crew[1].wall_state='stunned'
    env.commit_actions(actions)
    assert env.voluntary_jumps==1


@pytest.mark.parametrize('size',[2,4,6])
def test_practice_trials_provide_many_clear_targets_and_real_bullet_hit_rewards(size):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.practice_targets import TARGET_COUNT
    from entities.projectile import Projectile
    from creatures.traits.rooted import wall_between
    env=CrawlerEnvironment(horizon=.2)
    try:
        snap=env.reset(339,level=11,team_size=size,opponents='practice')
        targets=env.world.additional_targets
        assert len(targets)==TARGET_COUNT and env.world.ship is None and env.world.hunter is None
        assert len(snap.critic)==CRITIC_SIZE
        first=[t.get_pos() for t in targets]
        for c in env.team.members():
            assert c.wall_state=='attached'
            assert any(not wall_between(c.get_pos(),t.get_pos(),env.world.maze) for t in targets)
            assert observe(env.team,c)[0][SPEC.features.index('target0_present')]==1
        c=env.team.members()[0];c.die()
        shot=Projectile(targets[0].get_pos(),0,is_enemy=True);shot.actor_id=c.agent_id
        assert env.opponent_hit(shot) and env.hits==1 and not shot.active
        assert not env.opponent_hit(shot) and env.hits==1
        env.reset(339,level=11,team_size=size,opponents='practice')
        assert [t.get_pos() for t in env.world.additional_targets]==first
    finally:env.close()


def test_walking_penalty_counts_real_reversals_across_stops_and_resets_in_air():
    from learning.adapters.crawler_scenario import CrawlerEnvironment,WALK_REVERSAL_COST
    crew,enc,team=team_scene();c=crew[0]
    env=CrawlerEnvironment();env.team=team;env.walk_reversals=0;env._walk_directions={};env.agent_reversals=Counter()
    def walk(direction):
        c.wall_intent=Intent(move=direction)
        old={c.agent_id:c.get_pos()}
        enc.step(1);env.record_walking(old)
    walk(1);walk(1);assert env.walk_reversals==0
    walk(0);walk(-1);assert env.walk_reversals==1
    walk(-1);assert env.walk_reversals==1
    walk(0);walk(1);assert env.walk_reversals==2
    env.record_walking({c.agent_id:c.get_pos()})
    assert env.walk_reversals==2  # held command without movement
    c.wall_state='returning';env.record_walking({c.agent_id:c.get_pos()})
    c.wall_state='attached';walk(-1)
    assert env.walk_reversals==2 and WALK_REVERSAL_COST==.02


def test_practice_target_dies_once_disappears_and_clearance_ends_trial():
    import pygame
    from entities.projectile import Projectile
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice')
        target=env.world.additional_targets[0];owner=env.agent_ids[0]
        def hit(t):
            shot=Projectile(t.get_pos(),0,is_enemy=True);shot.actor_id=owner
            return env.opponent_hit(shot)
        assert hit(target) and not target.active and env.hits==1
        assert not hit(target) and env.hits==1
        position=target.get_pos();target.step(env.world.maze);assert target.get_pos()==position
        screen=pygame.Surface((1352,878));screen.fill((0,0,0));target.draw(screen)
        assert pygame.surfarray.array3d(screen).max()==0
        for other in env.world.additional_targets[1:]:other.active=False
        assert env.trial_complete()
        for c in env.team.members():
            x,_,_=observe(env.team,c)
            assert x[SPEC.features.index('target0_present')]==0
        with pytest.raises(RuntimeError,match='ended'):env.step({})
    finally:env.close()


def test_no_shot_receives_no_predicted_quality_bonus():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=.1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
        assert env.aim_quality_sum==0 and result.events['hits']==0 and result.reward==0
    finally:env.close()


def test_last_target_hit_rewards_once_and_terminates_without_time_bootstrap():
    from entities.projectile import Projectile
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        target=env.world.additional_targets[0]
        for other in env.world.additional_targets[1:]:other.active=False
        shot=Projectile(target.get_pos(),0,is_enemy=True);shot.actor_id=env.agent_ids[0]
        env.world.projectiles.append(shot)
        result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
        assert result.reward==pytest.approx(1+.02*env.aim_quality_sum) and result.terminated and not result.truncated
        assert result.events['targets_cleared'] and result.events['targets_remaining']==0
        assert result.events['hits']==1 and env.frames==1
    finally:env.close()


@pytest.mark.parametrize('walking',[False,True])
def test_practice_walking_setting_matches_masks_and_intents_without_enabling_jumps(walking,monkeypatch):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    monkeypatch.setattr('learning.adapters.crawler_scenario.PRACTICE_WALKING',walking)
    monkeypatch.setattr('learning.adapters.crawler_scenario.PRACTICE_JUMPING',False)
    env=CrawlerEnvironment(horizon=.2)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        positions={c.agent_id:c.get_pos() for c in env.team.members()}
        for masks in snap.masks.values():
            assert masks['move'].tolist()==([True,True,True] if walking else [False,True,False])
            assert masks['detach'].tolist()==[True,False]
            assert masks['aim'].all() and masks['fire'].all()
        result=env.step({i:(2,2,1,1,0,0) for i in snap.observations})
        assert result.events['voluntary_jumps']==0
        for c in env.team.members():
            assert c.wall_state=='attached'
            assert (math.dist(c.get_pos(),positions[c.agent_id])>1e-4)==walking
            assert c.wall_intent.move==(1 if walking else 0) and not c.wall_intent.detach
    finally:env.close()


def test_aiming_rewards_credit_only_the_shooter_and_charge_only_the_firer():
    from entities.projectile import Projectile
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        owner,other=env.team.members()
        target=env.world.additional_targets[0]
        credited=Projectile(target.get_pos(),0,is_enemy=True);credited.actor_id=owner.agent_id
        env.world.projectiles.append(credited)
        original=env.opponent_hit
        env.opponent_hit=lambda shot:original(shot) if shot is credited else False
        other.gun_cooldown=0
        result=env.step({owner.agent_id:(1,0.,0,0,0,0),other.agent_id:(1,0.,1,0,0,0)})
        assert result.agent_rewards[owner.agent_id]==pytest.approx(1.+.02*env.agent_quality[owner.agent_id])
        assert result.agent_rewards[other.agent_id]==pytest.approx(-.05+.02*env.agent_quality[other.agent_id])
        assert result.reward==pytest.approx(.95+.02*env.aim_quality_sum)
        assert sum(result.agent_rewards.values())==pytest.approx(result.reward)
        assert snap.agent_critics is not None
        assert not np.array_equal(snap.agent_critics[owner.agent_id],snap.agent_critics[other.agent_id])
    finally:env.close()


@pytest.mark.parametrize('individual',[False,True])
def test_collector_uses_individual_rewards_and_focal_critics_without_changing_shared_tasks(individual):
    from learning.environment import Snapshot,Transition
    from learning.training import collect
    spec=PolicySpec('numeric',('a','b'),(('act',1),))
    class NumericEnvironment:
        adapter=SimpleNamespace(enabled=lambda *args:[True])
        def reset(self,seed,**kwargs):
            self.action_trace=[]
            self.snap=Snapshot({i:np.zeros(2,np.float32) for i in (0,1)},
                {i:{'act':np.array([True])} for i in (0,1)},np.zeros(2,np.float32),
                {0:np.array([1.,0.]),1:np.array([0.,1.])} if individual else None)
            return self.snap
        def step(self,actions):
            self.action_trace.append(actions)
            return Transition(self.snap,100.,True,False,{}, {0:1.,1:-.05} if individual else None)
    episodes,_,_=collect(NumericEnvironment(),random_policy(spec,hidden=4,embed=3),0,{})
    assert episodes[0]['rewards']==([1.] if individual else [100.])
    assert episodes[1]['rewards']==([-.05] if individual else [100.])
    if individual:
        np.testing.assert_array_equal(episodes[0]['critic'][0],[1,0])
        np.testing.assert_array_equal(episodes[1]['final_critic'],[0,1])


def test_practice_firing_respects_configured_cadence():
    from learning.adapters.crawler_scenario import CrawlerEnvironment,PRACTICE_FIRE_INTERVAL
    env=CrawlerEnvironment(horizon=1.1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        for c in env.team.members():assert c.gun_interval==c.gun_cooldown==PRACTICE_FIRE_INTERVAL
        actions={i:(1,0.,1,0,0,0) for i in snap.observations}
        for _ in range(10):env.step(actions)
        assert env.frames==60
        for c in env.team.members():assert c.shots_fired==env.frames//PRACTICE_FIRE_INTERVAL and c.gun_interval==PRACTICE_FIRE_INTERVAL
    finally:env.close()


def test_gun_range_controls_perception_and_projectile_reach():
    from entities.projectile import Projectile
    crew,enc,team=team_scene();c=crew[0]
    enc.world.ship=None
    victim=target((c.x+c.gun_range*.75,c.y));victim.vx=victim.vy=0
    enc.world.hunter=victim
    assert observe(team,c)[0][SPEC.features.index('hunter_present')]==1
    enc.world.hunter=target((c.x+c.gun_range*1.1,c.y));enc.world.hunter.vx=enc.world.hunter.vy=0
    assert observe(team,c)[0][SPEC.features.index('hunter_present')]==0
    c.gun_cooldown=0;c.wall_intent=Intent(move=0,fire=True)
    enc.step(1)
    shot=enc.world.projectiles[0]
    gun=next(trait for trait in c.traits if trait.NAME=='gun')
    assert shot.lifetime==pytest.approx(Projectile((0,0),0).lifetime*gun.shot_lifetime)
    assert shot.aim_range==c.gun_range


def test_practice_targets_have_varied_seeded_speeds_in_the_recorded_range():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.practice_targets import TARGET_SPEED_MIN,TARGET_SPEED_MAX
    env=CrawlerEnvironment(horizon=.1)
    try:
        def speeds(seed):
            env.reset(seed,level=11,team_size=2,opponents='practice')
            assert all(t.radius==10 for t in env.world.additional_targets)
            return [math.hypot(t.vx,t.vy) for t in env.world.additional_targets]
        first=speeds(339)
        assert all(TARGET_SPEED_MIN<=s<=TARGET_SPEED_MAX for s in first)
        assert len({round(s,5) for s in first})>1
        assert first==speeds(339)
        assert first!=speeds(340)
    finally:env.close()


def test_practice_targets_fire_slow_weak_bullets_and_stop_on_death():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.practice_targets import TARGET_FIRE_INTERVAL
    env=CrawlerEnvironment(horizon=.2)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice')
        targets=env.world.additional_targets
        assert all(90<=t.fire_cooldown<=180 for t in targets)
        assert len({t.fire_cooldown for t in targets})>1
        target=targets[0];target.fire_cooldown=0
        bullet=target.fire(env.team.members(),env.world.maze)
        assert bullet is not None and not bullet.is_enemy
        assert math.hypot(bullet.vx,bullet.vy)==pytest.approx(2)
        assert bullet.creature_damage==.1 and bullet.lifetime==240
        assert target.fire_cooldown==TARGET_FIRE_INTERVAL
        assert target.fire(env.team.members(),env.world.maze) is None
        env.world.projectiles.append(bullet)
        assert any(observe(env.team,c)[0][SPEC.features.index('bullet0_present')]==1 for c in env.team.members())
        target.active=False;target.fire_cooldown=0
        assert target.fire(env.team.members(),env.world.maze) is None
        assert env.hits==0 and sum(c.shots_fired for c in env.team.members())==0
    finally:env.close()


def test_practice_targets_do_not_shoot_through_rock():
    from learning.adapters.practice_targets import PracticeTarget
    maze=open_maze([WallSegment((150,0),(150,300),4)])
    target_=PracticeTarget((100,100),0,1,fire_delay=0)
    victim=target((200,100))
    assert target_.fire([victim],maze) is None and target_.shots_fired==0


def test_slow_target_bullet_is_consumed_after_one_crawler_impact():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=.2)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice')
        c=env.team.members()[0]
        bullet=Projectile(c.get_pos(),0,source='player')
        bullet.vx=2;bullet.vy=0;bullet.creature_damage=.1
        env.world.projectiles.append(bullet)
        before=c.hit_points
        result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
        assert c.hit_points==pytest.approx(before-.1)
        assert not bullet.active and bullet not in env.world.projectiles
        assert env.hits==0
        assert result.agent_rewards[c.agent_id]==pytest.approx(-1.)
        assert result.agent_rewards[1-c.agent_id]==0
        assert result.events["bullet_hits_taken"]==1
        env._bullet_damage(c,bullet)
        assert env.agent_hits_taken[c.agent_id]==1
    finally:env.close()


def test_received_bullet_penalty_includes_lethal_hits_but_not_zero_damage():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice')
        c=env.team.members()[0]
        harmless=Projectile(c.get_pos(),0,source='player')
        harmless.creature_damage=0
        env.enc.apply_hit(c,harmless)
        assert not env.agent_hits_taken
        lethal=Projectile(c.get_pos(),0,source='player')
        lethal.creature_damage=c.hit_points+1
        env.enc.apply_hit(c,lethal)
        assert not c.active
        assert env.agent_hits_taken[c.agent_id]==1
        assert env.agent_returns()[c.agent_id]==pytest.approx(-1.)
    finally:env.close()


@pytest.mark.parametrize('practice_stage,expected_cost',[('shooting',.1),('dodge',.02)])
def test_practice_jumping_uses_legal_landings_and_charges_only_jumper(practice_stage,expected_cost):
    from learning.adapters.crawler_scenario import CrawlerEnvironment, JUMP_COST
    env=CrawlerEnvironment(horizon=2)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage=practice_stage)
        assert env.jumping_enabled and env.walking_enabled
        for c in env.team.members():c.wall_attach_cooldown=0
        snap=env.snapshot()
        eligible=[i for i,masks in snap.masks.items() if masks['detach'][1]]
        assert eligible
        jumper=eligible[0]
        landing=next(i for i,legal in enumerate(snap.masks[jumper]['landing']) if legal)
        actions={i:(1,0.,0,int(i==jumper),landing if i==jumper else 0,0) for i in snap.observations}
        result=env.step(actions)
        assert result.events['voluntary_jumps']==1
        assert result.agent_rewards[jumper]==pytest.approx(-expected_cost)
        assert all(value==0 for i,value in result.agent_rewards.items() if i!=jumper)
        c=next(c for c in env.team.members() if c.agent_id==jumper)
        assert c.wall_phase=='launch' and not c.just_fired
        assert result.snapshot.masks[jumper]['fire'][1]
        assert not result.snapshot.masks[jumper]['detach'][1]
    finally:env.close()


def test_practice_replay_accepts_overridden_gameplay_reload_but_rejects_effective_changes(tmp_path,monkeypatch):
    import copy,json
    from types import SimpleNamespace
    from learning import replay
    from learning.adapters import crawler_scenario
    manifest={'horizon':60,'arenas':{},'training':{},'aiming_practice':True,'opponent_body':'practice_targets',
              'practice_fire_interval_frames':30,'creatures':{'wallcrawler':{'traits':[
                  ['gun',{'intervalMin':100,'intervalMax':140,'range':1100}]]}}}
    (tmp_path/'config.json').write_text(json.dumps({'manifest':manifest}))
    current=copy.deepcopy(manifest)
    current['creatures']['wallcrawler']['traits'][0][1].update(intervalMin=30,intervalMax=30)
    monkeypatch.setattr(crawler_scenario,'metadata',lambda args:current)
    monkeypatch.setattr(crawler_scenario,'CrawlerEnvironment',lambda **kwargs:SimpleNamespace(**kwargs))
    assert replay.open_environment(tmp_path).horizon==60
    current['creatures']['wallcrawler']['traits'][0][1]['range']=1200
    with pytest.raises(ValueError,match='replay rules'):replay.open_environment(tmp_path)
    current['creatures']['wallcrawler']['traits'][0][1]['range']=1100
    current['practice_fire_interval_frames']=20
    with pytest.raises(ValueError,match='replay rules'):replay.open_environment(tmp_path)
    assert manifest['creatures']['wallcrawler']['traits'][0][1]['intervalMin']==100


def test_dodge_encounter_is_seeded_has_relocation_targets_and_matches_no_jump_ablation():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from creatures.traits.rooted import wall_between
    env=CrawlerEnvironment(horizon=2)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='dodge')
        assert env.jump_cost==.02
        targets=env.world.additional_targets
        assert len(targets)==6 and all(t.burst_size==3 for t in targets)
        assert all(60<=t.fire_cooldown<=120 for t in targets)
        relocated=[t for t in targets if getattr(t,'reposition_target',False)]
        assert relocated
        for t in relocated:
            c=next(c for c in env.team.members() if c.agent_id==t.reposition_from)
            outward=(t.x-c.x)*c.wall_normal[0]+(t.y-c.y)*c.wall_normal[1]
            assert outward<=0 or wall_between(c.get_pos(),t.get_pos(),env.world.maze)
            assert not wall_between(t.reposition_landing.position,t.get_pos(),env.world.maze)
        fingerprint=[(t.get_pos(),t.vx,t.vy,t.fire_cooldown) for t in targets]
        starts=[c.get_pos() for c in env.team.members()]
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='dodge',jumping=False)
        assert [(t.get_pos(),t.vx,t.vy,t.fire_cooldown) for t in env.world.additional_targets]==fingerprint
        assert [c.get_pos() for c in env.team.members()]==starts
        for c in env.team.members():c.wall_attach_cooldown=0
        snap=env.snapshot()
        assert not any(m['detach'][1] for m in snap.masks.values())
        env.step({i:(1,0.,0,1,0,0) for i in snap.observations})
        assert not env.voluntary_jumps
        assert not any(c.wall_intent.detach for c in env.team.members())
    finally:env.close()


def test_practice_burst_fires_three_locked_aim_shots_then_pauses():
    from learning.adapters.practice_targets import PracticeTarget
    from tests.creature_parts import open_maze,target
    t=PracticeTarget((500,500),0,0,fire_delay=0,burst_size=3,burst_spacing=12)
    victim=target((600,500))
    first=t.fire([victim],open_maze([]))
    assert first is not None
    victim.x,victim.y=500,600
    bullets=[first]
    for _ in range(24):
        shot=t.fire([victim],open_maze([]))
        if shot:bullets.append(shot)
    assert len(bullets)==3 and t.fire_cooldown==180
    assert all(b.vx==pytest.approx(2) and b.vy==pytest.approx(0) for b in bullets)
    assert all(t.fire([victim],open_maze([])) is None for _ in range(179))
    next_shot=t.fire([victim],open_maze([]))
    assert next_shot.vx==pytest.approx(0) and next_shot.vy==pytest.approx(2)


def test_jump_evaluation_requires_avoided_hits_without_losing_shooting_or_survival():
    from learning.adapters.crawler_scenario import compare_jumping
    def report(received,hits,survival=1):
        return {'episodes':[{'hits':hits,'bullet_hits_taken':received} for _ in range(6)],
                'summary':{'survival':survival}}
    base=report(5,6)
    assert compare_jumping(report(2,6),base)['supports_progression']
    assert not compare_jumping(report(5,6),base)['supports_progression']
    assert not compare_jumping(report(2,4),base)['supports_progression']
    assert not compare_jumping(report(2,6,.5),base)['supports_progression']


def test_allied_jellyfish_reuses_real_body_and_chase_targets_only_crawlers():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.jellyfish import Jellyfish
    from learning.adapters.wallcrawler import SPEC
    env=CrawlerEnvironment(horizon=1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        assert env.world.additional_targets
        assert len(env.team.members())==len(env.world.roster.alive())==2
        for t in env.world.additional_targets:
            assert t.type=='aggressive' and t.allegiance=='ally'
            assert isinstance(t.creature.body,Jellyfish) and .5<=t.speed<=2.5
            expected=min(env.team.members(),key=lambda c:math.dist(c.get_pos(),t.get_pos()))
            assert t.encounter.target_for(t.creature)==expected.get_pos()
            t.step(env.world.maze)
            assert t.creature.is_alert and t.fire(env.team.members(),env.world.maze) is None
        assert any(x[SPEC.features.index('target0_present')] for x in snap.observations.values())
    finally:env.close()


def test_pursuit_contact_damage_and_penalty_are_individual_and_have_shared_cooldown(monkeypatch):
    monkeypatch.setattr("learning.adapters.allied_jellyfish.CONTACT_DAMAGE",.25)
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        c=env.team.members()[0];before=c.hit_points
        for _ in range(4):env.contact_hit(c)
        assert c.hit_points==pytest.approx(before-.25)
        assert env.agent_returns()[c.agent_id]==pytest.approx(-5.)
        assert env.agent_returns()[1-c.agent_id]==0
        assert sum(env.agent_contact_hits.values())==1 and not env.agent_hits_taken
        assert not env.hits and c.wall_state=='stunned'
        env.frames=30
        env.contact_hit(c)
        assert c.hit_points==pytest.approx(before-.5)
    finally:env.close()


def test_allied_jelly_takes_two_hits_and_rewards_each_accepted_bullet_once():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        t=env.world.additional_targets[0]
        assert t.hit_points==t.max_hit_points==2
        for hit in range(1,3):
            shot=Projectile(t.get_pos(),0,is_enemy=True);shot.actor_id=0
            assert env.opponent_hit(shot)
            assert t.hit_points==2-hit and t.active==(hit<2)
            assert not shot.active and env.contributions[0]==hit
            assert not env.opponent_hit(shot) and env.hits==hit
        assert not env.contributions[1]
        import creatures
        ordinary=creatures.build('aggressive',(500,500))
        assert next(t for t in ordinary.traits if t.NAME=='takesHits').hit_points==1
        assert env.world.powerup_crystals==[] and len(env.world.roster.alive())==2
    finally:env.close()


def test_allied_jellyfish_group_steps_once_per_frame_and_contact_uses_collision():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        targets=env.world.additional_targets
        assert len({id(t.encounter) for t in targets})==1
        targets[0].step(env.world.maze)
        positions=[t.get_pos() for t in targets]
        for t in targets[1:]:t.step(env.world.maze)
        assert [t.get_pos() for t in targets]==positions
        c=env.team.members()[0];t=targets[0]
        t.creature.x=c.x+c.wall_normal[0]*17
        t.creature.y=c.y+c.wall_normal[1]*17
        before=c.hit_points
        t.on_contacts()
        assert c.hit_points==pytest.approx(before-4)
        assert not c.active
        assert env.agent_contact_hits[c.agent_id]==1 and not env.agent_hits_taken
    finally:env.close()


def test_lethal_jelly_contact_ends_actor_without_free_escape_or_teammate_penalty():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=1)
    try:
        snap=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit')
        c=env.team.members()[0];victim=c.agent_id
        jelly=env.world.additional_targets[0].creature
        jelly.x=c.x+c.wall_normal[0]*17
        jelly.y=c.y+c.wall_normal[1]*17
        result=env.step({i:(1,0.,0,0,0,0) for i in snap.observations})
        assert not c.active and c.hit_points<=0
        assert c.wall_state=='attached'  # no damage-induced escape before death
        assert victim not in result.snapshot.observations
        assert result.agent_rewards[victim]==pytest.approx(-45.)
        assert result.agent_rewards[1-victim]==pytest.approx(.1*env.frames/60)
        assert result.events['contact_hits_taken']==1
        assert result.events['bullet_hits_taken']==0 and result.events['voluntary_jumps']==0
        env.contact_hit(c)
        assert sum(env.agent_contact_hits.values())==1
    finally:env.close()


def test_jump_teacher_contact_prediction_handles_approach_miss_and_overlap():
    from learning.adapters.crawler_jump_teacher import contact_time
    assert contact_time((100,0),(-2,0),20)==pytest.approx(40)
    assert math.isinf(contact_time((100,0),(2,0),20))
    assert math.isinf(contact_time((100,50),(-2,0),20))
    assert contact_time((10,0),(0,0),20)==0


def test_escape_motion_forecast_matches_launch_landing_and_walking_without_side_effects():
    from learning.adapters.crawler_jump_teacher import motion_path
    crew,enc,team=team_scene();c=crew[0]
    for other in crew:
        other.wall_attach_cooldown=0
        other.wall_intent=Intent(move=0)
    site=next(s for s in candidates(c,enc) if s is not None)
    env=SimpleNamespace(team=team,world=enc.world)
    original=(c.get_pos(),c.wall_state,c.wall_destination,c.controls.fire,c.wall_attach_cooldown)
    points,landed=motion_path(env,c,(2,1,0,1,0,0),site)
    assert (c.get_pos(),c.wall_state,c.wall_destination,c.controls.fire,c.wall_attach_cooldown)==original
    assert team.reservations=={}
    assert landed is not None
    team.commit({c.agent_id:Intent(move=1,detach=True,landing=0)},
                {c.agent_id:[site]+[None]*7})
    for frame,point in enumerate(points[1:],1):
        if frame>1 and (frame-1)%6==0:
            c.wall_intent=Intent(move=int(c.walk_direction) if c.wall_state=='attached' else 0)
        enc.step(1)
        assert c.get_pos()==pytest.approx(point,abs=1e-8)


def test_revised_teacher_escape_survives_real_landing_and_cooldown_vs_contact_without_jump(monkeypatch):
    # Preserve the original unrecoiling gun, health, cadence and spacing of this historical fixture.
    monkeypatch.setattr('physics.recoil.apply_firing_recoil',lambda *args,**kwargs:False)
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_HEALTH',4)
    monkeypatch.setattr('learning.adapters.crawler_scenario.PRACTICE_FIRE_INTERVAL',30)
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_START_DISTANCE',120.)
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_SPEED_MIN',1.2)
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_SPEED_MAX',1.2)
    from learning.validate_crawler_teacher import audit
    result=audit(dict(seed=1000,level=20,team_size=2,
                      opponents='practice',practice_stage='pursuit'))
    assert result['demonstrations']
    for demo in result['demonstrations']:
        assert demo['safe'] and demo['avoided_contact']
        assert demo['jump']['landed'] and demo['jump']['alive']
        assert demo['jump']['contacts']==0
        assert demo['no_jump']['contacts']>0


def test_teacher_prepares_a_route_with_legal_aiming_without_bypassing_cooldown(monkeypatch):
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_START_DISTANCE',120.)
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.wallcrawler import teacher_action
    env=CrawlerEnvironment(horizon=12)
    try:
        snap=env.reset(1001,level=20,team_size=2,opponents='practice',practice_stage='pursuit')
        env.step({i:teacher_action(env,i,(1,0.,0,0,0,6)) for i in snap.observations})
        c=next(c for c in env.team.members() if c.agent_id==1)
        c.wall_attach_cooldown=12
        snap=env.snapshot()
        original=c.get_pos(),c.angle,c.wall_attach_cooldown,dict(env.team.reservations)
        action=teacher_action(env,1,(1,0.,0,0,0,6))
        assert action[0]==1 and action[1]<0 and action[2:4]==(0,0)  # plant feet, aim left, no detach
        assert action[5]==6
        assert (c.get_pos(),c.angle,c.wall_attach_cooldown,dict(env.team.reservations))==original
        assert not snap.masks[1]['detach'][1]
        env.step({other.agent_id: action if other is c else (1,0.,0,0,0,0)
                  for other in env.team.members()})
        assert c.get_pos()==pytest.approx(original[0])
        assert c.angle==pytest.approx(original[1]-18)
        assert c.wall_state=='attached' and c.wall_attach_cooldown==6
    finally:env.close()


def test_jump_bonus_grows_with_visible_enemy_proximity_without_stacking_enemies():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    crew,enc,team=team_scene();c=crew[0]
    env=CrawlerEnvironment();env.world=enc.world;env.practice_stage='pursuit'
    threat=SimpleNamespace(active=True,allegiance='ally',radius=10,get_pos=lambda:(c.x,c.y+95))
    env.world.additional_targets=[threat]
    far=env.jump_bonus(c)
    threat.get_pos=lambda:(c.x,c.y+45)
    near=env.jump_bonus(c)
    assert 0<far<near<1
    env.world.additional_targets.append(threat)
    assert env.jump_bonus(c)==near
    threat.active=False
    assert env.jump_bonus(c)==0
    threat.active=True;threat.get_pos=lambda:(c.x,c.y+200)
    assert env.jump_bonus(c)==0
    threat.get_pos=lambda:(c.x,c.y-45)  # behind the attachment wall
    assert env.jump_bonus(c)==0
    env.practice_stage='shooting'
    threat.get_pos=lambda:(c.x,c.y+45)
    assert env.jump_bonus(c)==0


def test_proximity_jump_reward_is_personal_and_awarded_only_once_per_real_launch(monkeypatch):
    # Put an enemy inside reward range; normal curriculum starts are farther away.
    monkeypatch.setattr('learning.adapters.allied_jellyfish.PURSUER_START_DISTANCE',120.)
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=2)
    try:
        snap=env.reset(1000,level=20,team_size=2,opponents='practice',practice_stage='pursuit')
        jumper=next(i for i,m in snap.masks.items() if m['detach'][1])
        c=next(c for c in env.team.members() if c.agent_id==jumper)
        bonus=env.jump_bonus(c)
        assert bonus>0 and env.jump_cost==0
        landing=next(i for i,v in enumerate(snap.masks[jumper]['landing']) if v)
        actions={i:(1,0.,0,int(i==jumper),landing if i==jumper else 0,0) for i in snap.observations}
        result=env.step(actions)
        assert result.events['voluntary_jumps']==1
        assert result.events['jump_proximity_reward']==pytest.approx(bonus)
        assert result.reward==pytest.approx(bonus+.02)
        assert result.agent_rewards[jumper]==pytest.approx(bonus+.01)
        assert all(v==pytest.approx(.01) for i,v in result.agent_rewards.items() if i!=jumper)
        again=env.step(actions)
        assert again.events['jump_proximity_reward']==pytest.approx(bonus)
        assert again.agent_rewards[jumper]==pytest.approx(.01)
    finally:env.close()


def test_battle_landing_is_recorded_without_extra_reward():
    from learning.adapters.crawler_scenario import CrawlerEnvironment,LANDING_REWARD
    env=CrawlerEnvironment(horizon=10)
    try:
        snap=env.reset(1000,level=20,team_size=2,opponents='practice',practice_stage='pursuit')
        # Isolate the actual takeoff/landing mechanics from enemy attacks.
        for t in env.world.additional_targets:
            t.step=lambda maze:None
            t.on_contacts=lambda:None
        jumper=next(i for i,m in snap.masks.items() if m['detach'][1])
        c=next(c for c in env.team.members() if c.agent_id==jumper)
        landing=next(i for i,v in enumerate(snap.masks[jumper]['landing']) if v)
        actions={i:(1,0.,0,int(i==jumper),landing if i==jumper else 0,0) for i in snap.observations}
        result=env.step(actions)
        total=result.reward
        assert result.events['successful_landings']==0
        while c.wall_state!='attached' and not result.truncated:
            result=env.step({other.agent_id:(1,0.,0,0,0,0) for other in env.team.members()})
            total+=result.reward
        assert c.wall_state=='attached'
        assert result.events['successful_landings']==1
        assert result.agent_rewards[jumper]==pytest.approx(.01)
        assert all(v==pytest.approx(.01) for i,v in result.agent_rewards.items() if i!=jumper)
        assert total==pytest.approx(.2*env.frames/60)
        again=env.step({other.agent_id:(1,0.,0,0,0,0) for other in env.team.members()})
        assert again.reward==pytest.approx(.02) and again.events['successful_landings']==1
        # A damage interruption cancels pending credit; later automatic recovery
        # and ordinary attached frames cannot produce another landing reward.
        env._pending_landings.add(jumper);c.wall_state='stunned'
        env.record_landings()
        c.wall_state='attached';env.record_landings()
        assert env.agent_landings[jumper]==1
        env._pending_landings.add(jumper);c.die();env.record_landings()
        assert jumper not in env._pending_landings
        assert env.agent_landings[jumper]==1
    finally:env.close()


def test_pre_contact_teacher_produces_legal_examples_and_never_forces_airborne_jumps():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.wallcrawler import teacher_action
    env=CrawlerEnvironment(horizon=12)
    jumps=0
    try:
        snap=env.reset(101,level=13,team_size=2,opponents='practice',practice_stage='pursuit')
        while True:
            actions={i:teacher_action(env,i,(1,0.,0,0,0,6)) for i in snap.observations}
            for i,a in actions.items():
                assert a[5]==6
                if a[3]:
                    jumps+=1
                    assert snap.masks[i]['detach'][1] and snap.masks[i]['landing'][a[4]]
                    assert env.agent_contact_hits[i]==0  # demonstration precedes contact
            result=env.step(actions);snap=result.snapshot
            if result.terminated or result.truncated:break
        assert jumps>0
    finally:env.close()


def test_jump_imitation_updates_detach_and_landing_but_not_message_head():
    import torch
    from learning.training import build_network,clone_behaviour
    p=random_policy(SPEC,7,hidden=8,embed=4);net=build_network(p,CRITIC_SIZE)
    before={name:net.heads[name].weight.detach().clone() for name in ('detach','landing','message')}
    episode=dict(x=[np.ones(len(SPEC.features),np.float32)]*3,
                 critic=[np.zeros(CRITIC_SIZE,np.float32)]*3,actions=[(1,0.,0,1,3,5)]*3,
                 alive=[True]*3,enabled=[[False,False,False,True,True,False]]*3)
    clone_behaviour(net,[episode],dict(SPEC.heads),selected_heads=('detach','landing'),epochs=2)
    assert not torch.equal(before['detach'],net.heads['detach'].weight)
    assert not torch.equal(before['landing'],net.heads['landing'].weight)
    torch.testing.assert_close(before['message'],net.heads['message'].weight)


def test_balanced_demonstration_loss_is_not_dominated_by_negative_only_episodes():
    from learning.imitation import Demonstrations
    from learning.training import build_network
    p=random_policy(SPEC,7,hidden=8,embed=4);net=build_network(p,CRITIC_SIZE)
    def episode(jump):
        return dict(x=[np.ones(len(SPEC.features),np.float32)],critic=[np.zeros(CRITIC_SIZE,np.float32)],
                    actions=[(1,0.,0,jump,0,0)],alive=[True],enabled=[[False,False,False,True,False,False]])
    small=Demonstrations([episode(1),episode(0)],dict(SPEC.heads),('detach',))
    large=Demonstrations([episode(1)]+[episode(0) for _ in range(40)],dict(SPEC.heads),('detach',))
    assert float(small.loss(net,[0,1]).detach())==pytest.approx(float(large.loss(net,list(range(41))).detach()))


def test_ppo_rehearsal_updates_jump_head_without_forcing_rollout_actions():
    import torch
    from learning.imitation import Demonstrations
    from learning.training import build_network
    from learning.ppo import update_team
    p=random_policy(SPEC,7,hidden=8,embed=4);net=build_network(p,CRITIC_SIZE)
    e=dict(x=[np.ones(len(SPEC.features),np.float32)],critic=[np.zeros(CRITIC_SIZE,np.float32)],
           actions=[(1,0.,0,1,2,5)],alive=[True],enabled=[[False,False,False,True,True,False]],
           legal={k:[np.ones(n,bool)] for k,n in SPEC.heads},rewards=[0.],terminated=True,
           final_critic=np.zeros(CRITIC_SIZE,np.float32))
    demo=Demonstrations([e],dict(SPEC.heads),('detach','landing'),'landing')
    rollout=dict(e,enabled=[[False]*6],actions=[(1,0.,0,0,0,5)])
    before={k:net.heads[k].weight.detach().clone() for k in ('detach','message')}
    stats=update_team(net,torch.optim.Adam(net.parameters(),lr=.01),[rollout],np.random.default_rng(0),epochs=1,
                      imitation_loss=lambda model,rng:demo.rehearse(model,rng,('detach','landing'))*.1)
    assert stats['imitation_loss']>0
    assert not torch.equal(before['detach'],net.heads['detach'].weight)
    torch.testing.assert_close(before['message'],net.heads['message'].weight)
    assert rollout['actions']==[(1,0.,0,0,0,5)]


@pytest.mark.parametrize('level',(15,20,23))
def test_escape_curriculum_starts_after_a_feasible_cooldown_window(level):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from learning.adapters.allied_jellyfish import PURSUER_START_DISTANCE
    env=CrawlerEnvironment(horizon=1)
    try:
        env.reset(1000,level=level,team_size=2,opponents='practice',practice_stage='pursuit')
        assert env.world.additional_targets
        assert all(math.dist(t.get_pos(),c.get_pos())>=PURSUER_START_DISTANCE
                   for t in env.world.additional_targets for c in env.team.members())
        for _ in range(10):
            env.step({c.agent_id:(1,0.,0,0,0,0) for c in env.team.members()})
        assert len(env.team.members())==2
        assert all(c.wall_attach_cooldown==0 for c in env.team.members())
    finally:env.close()


@pytest.mark.parametrize('practice_stage', ['shooting', 'dodge', 'pursuit'])
def test_practice_crawlers_start_facing_spacious_clear_area(practice_stage):
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from creatures.traits.rooted import wall_between
    env = CrawlerEnvironment()
    try:
        env.reset(339, level=11, opponents='practice', practice_stage=practice_stage)
        maze = env.world.maze
        for crawler in env.team.members():
            nx, ny = crawler.wall_normal
            for depth in (50, 90, 130, 180):
                for side in (-60, -30, 0, 30, 60):
                    point = (crawler.x + nx*depth - ny*side,
                             crawler.y + ny*depth + nx*side)
                    assert maze.is_open(point, 11), 'cramped crawler start'
                    assert not wall_between(crawler.get_pos(), point, maze)
    finally:
        env.close()


def test_pursuit_jellyfish_speeds_are_individual_seeded_and_fixed_per_trial():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env = CrawlerEnvironment(horizon=.1)
    try:
        def speeds(seed):
            env.reset(seed, level=11, opponents='practice', practice_stage='pursuit')
            targets = env.world.additional_targets
            initial = [t.speed for t in targets]
            for t in targets:
                t.step(env.world.maze)
            assert initial == [t.speed for t in targets]
            return initial
        first = speeds(339)
        assert all(.5 <= speed <= 2.5 for speed in first)
        assert len(set(first)) == 4
        assert first == speeds(339)
        assert first != speeds(340)
        # The actual drift trait carries each sampled speed into creature spawn.
        assert all(next(t for t in target.creature.traits if t.NAME == 'drift').speed
                   == target.speed for target in env.world.additional_targets)
    finally:
        env.close()


def test_practice_neural_hunter_fires_weak_bullets_alongside_random_speed_jellies():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env = CrawlerEnvironment(horizon=1)
    try:
        def trial():
            snapshot = env.reset(339, level=11, opponents='practice',
                                 practice_stage='pursuit', neural_hunter=True)
            assert env.world.hunter is env.opponent and env.hunter is not None
            assert len(env.world.additional_targets) == 4
            assert all(.5 <= t.speed <= 2.5 for t in env.world.additional_targets)
            assert all(math.dist(c.get_pos(), env.opponent.get_pos()) >= 180
                       for c in env.team.members())
            shots = set()
            weaken = CrawlerEnvironment.weaken_ship_shots.__get__(env)
            def record_shots():
                weaken()
                for shot in env.world.projectiles:
                    if shot.source == 'hunter':
                        assert shot.creature_damage == .1
                        shots.add(shot)
            env.weaken_ship_shots = record_shots
            actions = {i:(1,0.,0,0,0,0) for i in snapshot.observations}
            for _ in range(10):
                transition = env.step(actions)
                if transition.terminated or transition.truncated:
                    break
            assert shots, 'the real frozen neural hunter must fire'
            assert transition.truncated
            return transition.events
        assert trial() == trial()
        # Clearing the Jellies does not remove the still-active hunter from the trial.
        for target in env.world.additional_targets:
            target.creature.active = False
        assert not env.trial_complete()
    finally:
        env.close()


def test_four_crawlers_exchange_messages_in_actor_observations():
    crew, enc, team = team_scene(((400,312),(480,312),(560,312),(640,312)))
    team.commit({c.agent_id:Intent(message=i+1) for i,c in enumerate(crew)})
    assert all(team.inbox(c) == {} for c in crew)
    team.advance()
    for c in crew:
        inbox = team.inbox(c)
        assert len(inbox) == 3
        x, masks, _ = observe(team, c)
        assert masks['message'].all()
        for symbol in inbox.values():
            assert any(x[SPEC.features.index(f'teammate{i}_message{symbol}')] == 1
                       for i in range(3))
        muted, _, _ = observe(team, c, muted=True)
        assert all(muted[SPEC.features.index(f'teammate{i}_message{symbol}')] == 0
                   for i in range(3) for symbol in range(1,8))
