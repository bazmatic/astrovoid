import math
from types import SimpleNamespace
import pytest
from entities.projectile import Projectile
from maze.wall_segment import WallSegment
from tests.creature_parts import open_maze
from learning.adapters.shot_accuracy import shot_quality, ACCURACY_WEIGHT, SHOT_COST


def target(x=200,y=100,vx=0,vy=0):
    obj=SimpleNamespace(x=x,y=y,vx=vx,vy=vy,radius=9,active=True,observer=False)
    obj.get_pos=lambda:(obj.x,obj.y)
    return obj


def shot(angle=0):
    return Projectile((100,100),angle,is_enemy=True)


def test_quality_metric_is_smooth_and_bonus_stays_below_the_shot_cost():
    bullet=shot();maze=open_maze([])
    scores=[shot_quality(bullet,[target(y=y)],maze) for y in (100,115,125,145)]
    assert scores[0]==1 and all(a>b for a,b in zip(scores,scores[1:]))
    assert ACCURACY_WEIGHT==.02 and ACCURACY_WEIGHT<SHOT_COST
    assert -SHOT_COST+ACCURACY_WEIGHT*scores[0]==pytest.approx(-.03)


def test_quality_accounts_for_target_motion_and_rewards_leading():
    enemy=target(vy=2);maze=open_maze([])
    # Solve constant-speed interception for a target moving across the firing line.
    speed=math.hypot(shot().vx,shot().vy)
    angle=math.degrees(math.asin(enemy.vy/speed))
    assert shot_quality(shot(angle),[enemy],maze)==pytest.approx(1)
    assert shot_quality(shot(),[enemy],maze)<.5


@pytest.mark.parametrize('change', ['behind','expired','distant','hidden','observer','shield','inactive','wall','gate','future_wall'])
def test_invalid_predictions_are_not_rewarded(change):
    enemy=target();bullet=shot();maze=open_maze([])
    wall=WallSegment((150,50),(150,150),4)
    if change=='behind':enemy.x=50
    if change=='expired':bullet.lifetime=1
    if change=='distant':enemy.x=700
    if change=='hidden':enemy.x=300;maze.walls.append(wall)
    if change=='observer':enemy.observer=True
    if change=='shield':enemy.is_shield_active=lambda:True
    if change=='inactive':enemy.active=False
    if change=='wall':maze.walls.append(wall)
    if change=='gate':maze.gate_segments=[wall]
    if change=='future_wall':
        enemy.y=50;enemy.vy=2
        maze.walls.append(WallSegment((150,90),(150,110),4))
    assert shot_quality(bullet,[enemy],maze)==0


def test_two_opponents_do_not_double_the_reward():
    bullet=shot();enemy=target();maze=open_maze([])
    assert shot_quality(bullet,[enemy,enemy],maze)==1


def test_actual_scenario_scores_each_crawler_projectile_once():
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    env=CrawlerEnvironment(horizon=.2)
    try:
        env.reset(339,level=11,team_size=2)
        bullet=shot();bullet.actor_id=env.agent_ids[0]
        env.opponent.x=200;env.opponent.y=100;env.opponent.vx=env.opponent.vy=0
        env.world.maze=open_maze([])
        env.world.projectiles=[bullet]
        owner=next(c for c in env.world.roster.all() if c.agent_id==bullet.actor_id)
        owner.shots_fired=1
        env.score_shots();first=env.aim_quality_sum
        assert first==1
        assert env.agent_returns()[owner.agent_id]==pytest.approx(-.03)
        assert env.agent_returns()[1-owner.agent_id]==0
        env.score_shots();assert env.aim_quality_sum==first
        assert env.agent_returns()[owner.agent_id]==pytest.approx(-.03)
        bullet=shot();bullet.actor_id=None;env.world.projectiles.append(bullet)
        env.score_shots();assert env.aim_quality_sum==first
        assert env.hits==0
    finally:env.close()
