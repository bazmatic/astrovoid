"""Precision and tracking drills isolate the continuous actuator without forced aiming."""
from collections import Counter
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
        angles={c.agent_id:c.angle for c in crew}
        targets=env.world.additional_targets
        initial=[(t.get_pos(),t.vx,t.vy) for t in targets]
        assert len(targets)==12 and env.opponent is None
        assert all(c.wall_state=='attached' for c in crew)
        assert env.walking_enabled and env.jumping_enabled
        assert all(snap.masks[c.agent_id]['move'].all() for c in crew)
        assert all(snap.masks[c.agent_id]['aim'].all() and snap.masks[c.agent_id]['fire'].all() for c in crew)
        speeds=[math.hypot(t.vx,t.vy) for t in targets]
        assert all(speed==0 if stage=='precision' else .5<=speed<=1.5 for speed in speeds)
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


def test_curriculum_keeps_tracking_emphasis_and_four_crawler_combat():
    def mix(iteration):return Counter(c['practice_stage'] for c in training_cases(iteration,12,4))
    assert mix(0)==mix(49)=={'precision':3,'tracking':6,'pursuit':3}
    assert mix(50)==mix(100)=={'precision':3,'tracking':6,'pursuit':3}
    assert all(not c['neural_hunter'] for c in validation_cases())
    assert {c['practice_stage'] for c in validation_cases()}=={'precision','tracking'}


def test_aim_validation_requires_real_throughput_and_ignores_hopping_bonuses():
    base=dict(episodes=4,aim_drill_episodes=4,accuracy=.2,hits_per_minute=40.)
    assert selection_score(base)==pytest.approx(8.)
    assert selection_score(dict(base,accuracy=.3))>selection_score(base)
    assert selection_score(dict(base,hits_per_minute=60.))>selection_score(base)
    assert selection_score(dict(base,accuracy=1.,hits_per_minute=0.))==0
    assert selection_score(dict(base,landings_per_minute=1000.,jump_reward_per_minute=1000.))==selection_score(base)


def test_metric_labels_aim_validation_for_checkpoint_selection():
    row=dict(seconds=10.,hits=2,shots=10,alive=4,team_size=4,practice_stage='tracking')
    summary=metrics([row])
    assert summary['aim_drill_episodes']==1
    assert selection_score(summary)==pytest.approx(.2*12)


def test_aim_drills_reject_a_hunter_opponent():
    env=CrawlerEnvironment()
    with pytest.raises(ValueError,match='harmless practice targets'):
        env.reset(0,opponents='practice',practice_stage='precision',neural_hunter=True)


def test_report_separates_precision_and_tracking_accuracy():
    rows=[dict(seconds=10.,hits=4,shots=10,alive=4,team_size=4,practice_stage='precision'),
          dict(seconds=20.,hits=2,shots=20,alive=4,team_size=4,practice_stage='tracking')]
    summary=metrics(rows)
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


def test_aim_drills_use_two_crawlers_and_combat_retains_four():
    for iteration in (0,50,100):
        for bootstrap in (False,True):
            cases=training_cases(iteration,12,4,bootstrap=bootstrap)
            assert all(case['team_size']==(4 if case['practice_stage']=='pursuit' else 2) for case in cases)
    assert all(case['team_size']==2 for case in validation_cases())
    env=CrawlerEnvironment(horizon=.1)
    try:
        case=next(case for case in training_cases(0,12,4) if case['practice_stage']=='precision')
        snap=env.reset(**case)
        assert len(env.team.members())==len(snap.observations)==2
        assert env.walking_enabled and env.jumping_enabled
        assert len(env.world.additional_targets)==12
    finally:env.close()
