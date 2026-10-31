"""The recoil experiment changes body motion without silently changing bullet ballistics."""
from types import SimpleNamespace
import pytest

from entities.projectile import Projectile
from learning.recoil_evaluation import body_recoil, phase_metrics
from physics import recoil


def test_ablation_keeps_inherited_bullet_velocity_and_removes_body_impulses():
    def body():
        return SimpleNamespace(x=0.,y=0.,radius=10.,vx=2.,vy=-.5,
                               wall_state='returning',wall_angular_velocity=1.5)
    normal=body();ablated=body()
    normal_shot=Projectile((0,10),20,is_enemy=True)
    ablated_shot=Projectile((0,10),20,is_enemy=True)
    original=recoil.apply_firing_recoil
    assert original(normal,normal_shot)
    with body_recoil(False):
        assert not recoil.apply_firing_recoil(ablated,ablated_shot)
    assert (ablated_shot.vx,ablated_shot.vy)==pytest.approx((normal_shot.vx,normal_shot.vy))
    assert (ablated.vx,ablated.vy,ablated.wall_angular_velocity)==(2.,-.5,1.5)
    assert (normal.vx,normal.vy,normal.wall_angular_velocity)!=(2.,-.5,1.5)
    assert recoil.apply_firing_recoil is original


def test_failed_ablation_restores_normal_physics():
    original=recoil.apply_firing_recoil
    with pytest.raises(RuntimeError):
        with body_recoil(False):
            raise RuntimeError('failed encounter')
    assert recoil.apply_firing_recoil is original


def test_delayed_hits_remain_attributed_to_the_launch_phase():
    attached,airborne,missed,unrelated=object(),object(),object(),object()
    result=phase_metrics({attached:'attached',airborne:'airborne',missed:'airborne'},
                         {attached,airborne,unrelated})
    assert result==dict(attached_shots=1,attached_hits=1,airborne_shots=2,airborne_hits=1)


def test_partly_constructed_encounter_can_be_closed_after_spawn_failure(monkeypatch):
    import creatures
    import config
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    original_size=config.SCREEN_WIDTH,config.SCREEN_HEIGHT
    def fail(*args,**kwargs):
        raise ValueError('failed creature setup')
    monkeypatch.setattr(creatures,'build',fail)
    env=CrawlerEnvironment()
    try:
        with pytest.raises(ValueError,match='failed creature setup'):
            env.reset(339,opponents='practice',practice_stage='pursuit')
    finally:
        env.close()
    assert env.world is None
    assert (config.SCREEN_WIDTH,config.SCREEN_HEIGHT)==original_size
