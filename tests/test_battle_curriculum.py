"""Battle success stops value bootstrapping; difficulty advances from accumulated outcomes."""
import json
import pytest

from learning.adapters import battle_curriculum as curriculum
from learning.adapters.crawler_scenario import CrawlerEnvironment, training_cases, evaluation_cases


def quiet_actions(snapshot):
    return {i:(1,0.,0,0,0,0) for i in snapshot.observations}


def test_horizon_survival_is_terminal_success_with_one_personal_bonus():
    env=CrawlerEnvironment(horizon=.1)
    try:
        snapshot=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit',jelly_count=1)
        result=env.step(quiet_actions(snapshot))
        assert result.terminated and not result.truncated
        assert result.events['battle_success']
        assert result.events['targets_remaining']>0
        assert result.events['battle_survival_bonus']==40
        assert result.reward==pytest.approx(sum(result.agent_rewards.values()))
        before=env.agent_returns()
        env.record_battle_outcomes()
        assert env.agent_returns()==before
        with pytest.raises(RuntimeError,match='ended'):
            env.step(quiet_actions(result.snapshot))
    finally:env.close()


def test_hunter_free_clear_succeeds_early_and_dead_crawlers_do_not_share_bonus():
    from entities.projectile import Projectile
    env=CrawlerEnvironment(horizon=60)
    try:
        snapshot=env.reset(339,level=11,team_size=2,opponents='practice',practice_stage='pursuit',jelly_count=1)
        victim=env.team.members()[1]
        env.enc.kill(victim)
        target=env.world.additional_targets[0]
        target.step=lambda maze:None
        shot=Projectile(target.get_pos(),0,is_enemy=True);shot.actor_id=0
        assert env.opponent_hit(shot)
        shot=Projectile(target.get_pos(),0,is_enemy=True);shot.actor_id=0
        env.world.projectiles.append(shot)
        result=env.step({0:(1,0.,0,0,0,0)})
        assert result.terminated and not result.truncated and result.events['battle_success']
        assert result.events['seconds']<env.horizon
        assert result.events['battle_survival_bonus']==20
        assert env.agent_battle_survival=={0:20}
        assert result.agent_rewards[1]==0  # death was already accounted before this step
    finally:env.close()


def test_promotion_requires_enough_successful_battles_and_state_round_trips():
    state=dict(curriculum.INITIAL_STATE)
    insufficient=dict(battle_trials=curriculum.MIN_TRIALS-1,battle_crawlers=4*(curriculum.MIN_TRIALS-1),
                      battle_survivors=4*(curriculum.MIN_TRIALS-1),battle_successes=curriculum.MIN_TRIALS-1)
    pending=curriculum.advance(state,insufficient)
    assert state==curriculum.INITIAL_STATE
    assert pending['stage']==state['stage']
    restored=json.loads(json.dumps(pending))
    final=dict(battle_trials=1,battle_crawlers=4,battle_survivors=4,battle_successes=1)
    promoted=curriculum.advance(restored,final)
    assert promoted['stage']==state['stage']+1 and promoted['trials']==0
    failed=curriculum.advance(state,dict(battle_trials=curriculum.MIN_TRIALS,
                             battle_crawlers=4*curriculum.MIN_TRIALS,battle_survivors=0,battle_successes=0))
    assert failed['stage']==state['stage'] and failed['trials']==0


def test_progression_changes_real_encounters_but_not_heldout_difficulty():
    env=CrawlerEnvironment(horizon=.1)
    try:
        populations=[];hunters=[]
        for stage in range(len(curriculum.STAGES)):
            state=dict(curriculum.INITIAL_STATE,stage=stage)
            cases=training_cases(0,12,4,curriculum=state)
            case=next(c for c in cases if c['practice_stage']=='pursuit')
            snapshot=env.reset(**case)
            populations.append(len(env.world.additional_targets));hunters.append(env.opponent is not None)
            assert len(snapshot.observations)==case['team_size']
        assert populations[0]==1 and populations==sorted(populations) and populations[-1]>populations[0]
        assert not hunters[0] and hunters[-1]
        heldout=[c for c in evaluation_cases() if c['practice_stage']=='pursuit']
        assert heldout and all(c['neural_hunter'] and c.get('jelly_count',populations[-1])==populations[-1] for c in heldout)
    finally:env.close()
