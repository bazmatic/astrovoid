"""Precision and tracking drills isolate the continuous actuator without forced aiming."""
import math
import numpy as np
import pytest

from learning.adapters.crawler_scenario import CrawlerEnvironment, training_cases, validation_cases, selection_score, metrics


@pytest.mark.parametrize('stage',['precision','tracking'])
@pytest.mark.parametrize('level,seed',[(11,339),(23,800)])
def test_aim_drills_allow_walking_and_keep_targets_harmless(stage,level,seed):
    env=CrawlerEnvironment(horizon=2)
    try:
        snap=env.reset(seed,level=level,team_size=4,opponents='practice',practice_stage=stage)
        crew=env.team.members()
        positions={c.agent_id:c.get_pos() for c in crew}
        targets=env.world.additional_targets
        initial=[(t.get_pos(),t.vx,t.vy) for t in targets]
        assert targets and env.opponent is None
        assert all(c.wall_state=='attached' for c in crew)
        assert env.walking_enabled and env.jumping_enabled
        assert all(snap.masks[c.agent_id]['move'].all() for c in crew)
        assert all(snap.masks[c.agent_id]['aim'].all() and snap.masks[c.agent_id]['fire'].all() for c in crew)
        speeds=[math.hypot(t.vx,t.vy) for t in targets]
        assert all(speed==0 if stage=='precision' else speed>0 for speed in speeds)
        for target in targets:
            target.fire_cooldown=0
            assert target.fire(crew,env.world.maze) is None
        # Walking remains a policy action while targets cannot attack.
        actions={c.agent_id:(2,math.atanh(1/12),1,0,0,5) for c in crew}
        result=env.step(actions)
        assert any(c.get_pos()!=positions[c.agent_id] for c in crew)
        for _ in range(9):result=env.step(actions)
        assert result.events['voluntary_jumps']==0 and result.events['successful_landings']==0
        assert result.events['target_shots']==0 and result.events['bullet_hits_taken']==0
        assert result.events['shots']>0
        assert any(c.get_pos()!=positions[c.agent_id] for c in crew)
        env.reset(seed,level=level,team_size=4,opponents='practice',practice_stage=stage)
        assert [(t.get_pos(),t.vx,t.vy) for t in env.world.additional_targets]==initial
    finally:env.close()


def test_aim_validation_requires_real_throughput_and_ignores_hopping_bonuses():
    base=dict(episodes=4,aim_drill_episodes=4,accuracy=.2,hits_per_minute=40.)
    assert selection_score(base)==pytest.approx(8.)
    assert selection_score(dict(base,accuracy=.3))>selection_score(base)
    assert selection_score(dict(base,hits_per_minute=60.))>selection_score(base)
    assert selection_score(dict(base,accuracy=1.,hits_per_minute=0.))==0
    assert selection_score(dict(base,landings_per_minute=1000.,jump_reward_per_minute=1000.))==selection_score(base)


def test_aim_drills_reject_a_hunter_opponent():
    env=CrawlerEnvironment()
    with pytest.raises(ValueError,match='harmless practice targets'):
        env.reset(0,opponents='practice',practice_stage='precision',neural_hunter=True)


def test_report_separates_precision_and_tracking_accuracy():
    rows=[dict(seconds=10.,hits=4,shots=10,alive=4,team_size=4,practice_stage='precision'),
          dict(seconds=20.,hits=2,shots=20,alive=4,team_size=4,practice_stage='tracking')]
    summary=metrics(rows)
    assert summary['aim_drill_episodes']==len(rows)
    assert selection_score(summary)==pytest.approx(summary['accuracy']*summary['hits_per_minute'])
    assert summary['accuracy']==pytest.approx(.2)
    assert summary['precision_accuracy']==pytest.approx(.4)
    assert summary['tracking_accuracy']==pytest.approx(.1)
    assert summary['precision_hits_per_minute']==24
    assert summary['tracking_hits_per_minute']==6


@pytest.mark.parametrize('stage',['precision','tracking'])
def test_aim_drills_execute_legal_voluntary_jumps(stage):
    env=CrawlerEnvironment(horizon=2)
    try:
        env.reset(339,level=11,team_size=4,opponents='practice',practice_stage=stage)
        for c in env.team.members():c.wall_attach_cooldown=0
        snap=env.snapshot()
        jumper=next(c for c in env.team.members() if snap.masks[c.agent_id]['detach'][1])
        landing=int(np.flatnonzero(snap.masks[jumper.agent_id]['landing'])[0])
        actions={c.agent_id:(1,0.,0,int(c is jumper),landing if c is jumper else 0,0)
                 for c in env.team.members()}
        result=env.step(actions)
        assert result.events['voluntary_jumps']==1
        assert jumper.wall_state=='returning'
        assert result.snapshot.masks[jumper.agent_id]['fire'][1]
        assert result.events['target_shots']==0
    finally:env.close()




def test_scenario_cases_are_repeatable_and_keep_holdouts_out_of_training():
    from learning.adapters.crawler_scenario import evaluation_cases, INITIAL_STAGE
    heldout=evaluation_cases()
    heldout_levels={case['level'] for case in heldout}
    heldout_seeds={case['seed'] for case in heldout}
    for bootstrap in (False,True):
        for iteration in (0,17):
            cases=training_cases(iteration,24,INITIAL_STAGE,bootstrap=bootstrap)
            assert cases==training_cases(iteration,24,INITIAL_STAGE,bootstrap=bootstrap)
            assert len(cases)==24
            assert all(case['level'] not in heldout_levels and case['seed'] not in heldout_seeds for case in cases)
    for case in training_cases(0,24,INITIAL_STAGE)+validation_cases()+heldout:
        if case['practice_stage'] in ('precision','tracking'):
            assert case['opponents']=='practice' and not case['neural_hunter']
