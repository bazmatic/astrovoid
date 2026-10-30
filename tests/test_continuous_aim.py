"""Continuous actuator probability, physical strength, transfer and optimisation contracts."""
import math
import numpy as np
import pytest

from learning.adapters.wallcrawler import SPEC, LEGACY_SPEC, CRITIC_SIZE, intention, observe
from learning.policy import random_policy, RecurrentPolicy
from learning.continuous import statistics, sample_activation


@pytest.mark.parametrize('strength',[-.9,-1/12,0.,1/12,.9])
def test_activation_scales_the_real_gun_turn_rate(strength):
    from tests.test_creature_learning import team_scene
    from creatures.wallcrawler_team import Intent, DECISION_FRAMES
    crew, enc, team = team_scene()
    crawler = crew[0]
    start = crawler.angle
    intent = intention((1,math.atanh(strength),0,0,0,0))
    assert intent.aim == pytest.approx(strength)
    team.commit({crawler.agent_id:intent,crew[1].agent_id:Intent(move=0)})
    for _ in range(DECISION_FRAMES):enc.step(1)
    assert crawler.angle-start == pytest.approx(18*strength)


def test_gaussian_sampling_log_density_and_bounded_entropy_agree():
    import torch
    parameters = torch.tensor([[[.3,math.log(.4)]]],requires_grad=True)
    activation = torch.tensor([[.12345]])
    logp, entropy = statistics(parameters,activation)
    normal = torch.distributions.Normal(parameters[...,0],parameters[...,1].exp())
    torch.testing.assert_close(logp,normal.log_prob(activation))
    transformed = torch.distributions.TransformedDistribution(normal,torch.distributions.TanhTransform())
    correction = torch.log1p(-activation.tanh().square())
    torch.testing.assert_close(logp-correction,transformed.log_prob(activation.tanh()))
    rng = np.random.default_rng(4)
    samples = np.array([sample_activation([.3,math.log(.4)],rng) for _ in range(10000)])
    assert samples.mean()==pytest.approx(.3,abs=.015)
    assert samples.std()==pytest.approx(.4,abs=.015)
    jacobian = 2*(math.log(2)-samples-np.logaddexp(0,-2*samples))
    assert entropy.item()==pytest.approx(.5*math.log(2*math.pi*math.e*.4**2)+jacobian.mean(),abs=.015)
    (logp+entropy).sum().backward()
    assert torch.isfinite(parameters.grad).all()


def test_saturated_actuators_have_finite_losses_and_gradients():
    import torch
    parameters = torch.tensor([[[30.,1.],[-30.,-5.]]],requires_grad=True)
    logp, entropy = statistics(parameters,torch.tensor([[29.9,-30.001]]))
    assert torch.isfinite(logp).all() and torch.isfinite(entropy).all()
    (logp+entropy).sum().backward()
    assert torch.isfinite(parameters.grad).all()


def test_policy_roundtrip_preserves_fractional_activations_and_airborne_neutral(tmp_path):
    from tests.test_creature_learning import team_scene
    policy = random_policy(SPEC,4,hidden=8,embed=4)
    policy.params['aim_w'][:]=0
    policy.params['aim_b'][0]=.123456
    crew, enc, team = team_scene()
    x,masks,_ = observe(team,crew[0])
    action,state = policy.choose(x,policy.initial_state(),masks)
    assert action[1] == pytest.approx(.123456)
    assert intention(action).aim == pytest.approx(math.tanh(.123456))
    path=tmp_path/'policy.npz';policy.save(path)
    loaded = RecurrentPolicy.load(path,SPEC)
    assert loaded.choose(x,loaded.initial_state(),masks)[0] == action
    crew[0].wall_state='stunned'
    x,masks,_=observe(team,crew[0])
    assert loaded.choose(x,loaded.initial_state(),masks)[0][1] == 0.
    assert loaded.spec.continuous == ('aim',)
    with pytest.raises(ValueError,match='schema'):RecurrentPolicy.load(path,LEGACY_SPEC)


def test_checkpoint_transfer_preserves_backbone_and_other_action_heads(tmp_path):
    from learning.adapters.wallcrawler import load_transfer_policy, load_policy
    old = random_policy(LEGACY_SPEC,5,hidden=8,embed=4)
    path=tmp_path/'old.npz';old.save(path)
    assert load_policy(path).spec == LEGACY_SPEC
    new = load_transfer_policy(path)
    assert new.spec == SPEC
    for key in old.params:
        if not key.startswith('aim_'):np.testing.assert_array_equal(new.params[key],old.params[key])
    np.testing.assert_array_equal(new.mean,old.mean)
    np.testing.assert_array_equal(new.scale,old.scale)
    x=np.random.default_rng(0).normal(size=len(SPEC.features)).astype(np.float32)
    a,ha=old.step(x,old.initial_state());b,hb=new.step(x,new.initial_state())
    np.testing.assert_array_equal(ha,hb)
    for head in a:
        if head!='aim':np.testing.assert_array_equal(a[head],b[head])


def test_mixed_ppo_uses_fractional_activations_and_updates_aim_distribution():
    import torch
    from learning.training import build_network
    from learning.ppo import update_team,masked_statistics
    policy=random_policy(SPEC,4,hidden=8,embed=4)
    net=build_network(policy,CRITIC_SIZE)
    x=np.ones(len(SPEC.features),np.float32)
    context=np.zeros(CRITIC_SIZE,np.float32)
    episodes=[]
    for activation,reward in ((.123,1.),(-.456,-1.)):
        episodes.append(dict(x=[x],critic=[context],actions=[(1,activation,0,0,0,0)],
            alive=[True],enabled=[[False,True,False,False,False,False]],
            legal={k:[np.ones(n,bool)] for k,n in SPEC.heads},rewards=[reward],
            terminated=True,final_critic=context))
    before=net.heads['aim'].weight.detach().clone()
    stats=update_team(net,torch.optim.Adam(net.parameters(),lr=.01),episodes,np.random.default_rng(0),epochs=1)
    assert np.isfinite(list(stats.values())).all()
    assert not torch.equal(before,net.heads['aim'].weight)
    assert episodes[0]['actions'][0][1] == .123
    parameters=torch.zeros(1,1,2)
    legal={'aim':torch.ones(1,1,2,dtype=torch.bool)}
    enabled=torch.ones(1,1,1)
    a,_=masked_statistics({'aim':parameters},torch.tensor([[[.123]]]),legal,enabled,('aim',))
    b,_=masked_statistics({'aim':parameters},torch.tensor([[[.456]]]),legal,enabled,('aim',))
    assert not torch.equal(a,b)


def test_continuous_demonstrations_teach_strength_without_categorical_labels():
    import torch
    from learning.training import build_network,clone_behaviour
    policy=random_policy(SPEC,7,hidden=8,embed=4)
    net=build_network(policy,CRITIC_SIZE)
    x=torch.ones(1,1,len(SPEC.features));context=torch.zeros(1,1,CRITIC_SIZE)
    target=math.atanh(.08)
    before=(net(x,context)[0]['aim'][...,0].tanh()-.08).square().item()
    episode=dict(x=[x[0,0].numpy()],critic=[context[0,0].numpy()],
                 actions=[(1,target,0,0,0,0)],alive=[True],enabled=[[False,True,False,False,False,False]])
    clone_behaviour(net,[episode],dict(SPEC.heads),selected_heads=('aim',),balanced=True,epochs=20,lr=.01)
    after=(net(x,context)[0]['aim'][...,0].tanh()-.08).square().item()
    assert after<before


def test_legacy_campaign_driver_keeps_original_categorical_aim():
    from tests.test_creature_learning import team_scene
    from learning.adapters.wallcrawler import CrawlerDriver
    policy=random_policy(LEGACY_SPEC,17,hidden=8,embed=4)
    crew,enc,team=team_scene()
    expected={}
    for crawler in crew:
        x,masks,_=observe(team,crawler)
        masks['aim']=np.ones(3,bool)
        action,_=policy.choose(x,policy.initial_state(),masks)
        expected[crawler.agent_id]=action[1]-1
    CrawlerDriver(policy).decide(team)
    assert all(c.wall_intent.aim==expected[c.agent_id] for c in crew)
