"""Projectile momentum produces recoil; neither aiming nor trigger requests provide thrust."""
import math
from types import SimpleNamespace
import pytest
from entities.projectile import Projectile
from physics.recoil import apply_firing_recoil
from physics.angular_motion import inertia


def body(radius=10,velocity=(0.,0.),state='returning'):
    return SimpleNamespace(x=0.,y=0.,radius=radius,vx=velocity[0],vy=velocity[1],
                           wall_state=state,wall_angular_velocity=0.)


@pytest.mark.parametrize('velocity',[(0.,0.),(2.5,-.5)])
def test_recoil_and_inherited_velocity_conserve_relative_launch_momentum(velocity):
    crawler=body(velocity=velocity)
    shot=Projectile((0,0),37,is_enemy=True)
    ejection=shot.vx,shot.vy
    assert apply_firing_recoil(crawler,shot)
    mass=shot.radius**2*shot.strength
    assert (shot.vx,shot.vy)==pytest.approx((velocity[0]+ejection[0],velocity[1]+ejection[1]))
    assert crawler.radius**2*(crawler.vx-velocity[0])+mass*(shot.vx-velocity[0])==pytest.approx(0)
    assert crawler.radius**2*(crawler.vy-velocity[1])+mass*(shot.vy-velocity[1])==pytest.approx(0)
    assert crawler.wall_angular_velocity==0


def test_recoil_scales_with_projectile_strength_and_inverse_body_mass():
    impulses=[]
    for radius,strength in ((10,1.),(20,1.),(10,.5)):
        crawler=body(radius=radius)
        shot=Projectile((0,0),0,is_enemy=True,strength=strength)
        apply_firing_recoil(crawler,shot)
        impulses.append(crawler.vx)
    assert impulses[0]<0
    assert impulses[1]==pytest.approx(impulses[0]/4)
    assert impulses[2]==pytest.approx(impulses[0]/2)


def test_off_centre_recoil_conserves_angular_launch_momentum():
    crawler=body()
    shot=Projectile((0,10),0,is_enemy=True)
    ejection=shot.vx,shot.vy
    apply_firing_recoil(crawler,shot)
    bullet_moment=shot.radius**2*(shot.x*ejection[1]-shot.y*ejection[0])
    assert crawler.wall_angular_velocity>0
    assert inertia(crawler.radius)*crawler.wall_angular_velocity/60+bullet_moment==pytest.approx(0)


def test_projectile_inherits_rotating_muzzle_velocity():
    crawler=body(velocity=(1.,0.));crawler.wall_angular_velocity=2.
    shot=Projectile((0,10),0,is_enemy=True)
    ejection=shot.vx
    apply_firing_recoil(crawler,shot)
    assert shot.vx==pytest.approx(ejection+1.-2.*10/60)
    assert shot.vy==0


def test_wall_support_absorbs_recoil():
    crawler=body(state='attached')
    shot=Projectile((0,0),0,is_enemy=True)
    velocity=shot.vx,shot.vy
    assert not apply_firing_recoil(crawler,shot)
    assert (crawler.vx,crawler.vy,crawler.wall_angular_velocity)==(0.,0.,0.)
    assert (shot.vx,shot.vy)==velocity


def test_trigger_without_a_shot_has_no_recoil_and_each_shot_kicks_once():
    from tests.test_creature_learning import team_scene
    from tests.test_wallcrawler_movement import airborne
    from creatures.wallcrawler_team import Intent
    crew,enc,team=team_scene();crawler=crew[0]
    airborne(crawler,(800,450),(.5,.2))
    crawler.wall_intent=Intent(move=0,aim=0,fire=True)
    crawler.gun_cooldown=2
    enc.step(1)
    assert not crawler.just_fired and not enc.world.projectiles
    assert (crawler.vx,crawler.vy)==(.5,.2)
    enc.step(1)
    assert crawler.just_fired and len(enc.world.projectiles)==1
    velocity=crawler.vx,crawler.vy
    assert velocity!=(.5,.2)
    enc.step(1)
    assert not crawler.just_fired and len(enc.world.projectiles)==1
    assert (crawler.vx,crawler.vy)==velocity


def test_volley_recoil_sums_all_bullets_with_one_launch_reference():
    from creatures.traits.combat import Gun
    from tests.creature_parts import creature,encounter
    gun=Gun(intervalMin=15,intervalMax=15,startsLoaded=True,upgrades=True,recoil=True)
    crawler=creature([gun],pos=(400,400),key='aggressive')
    enc=encounter(crawler);enc.ready()
    crawler.vx,crawler.vy=2.,.5
    crawler.gun_upgrade_level=2
    crawler.upgrade_remaining=10.
    crawler.controls.fire=True;crawler.controls.aim=(1000,400)
    gun.on_frame(crawler,enc,1.)
    shots=enc.world.projectiles
    assert len(shots)==3
    px=sum(s.radius**2*s.strength*(s.vx-2.) for s in shots)
    py=sum(s.radius**2*s.strength*(s.vy-.5) for s in shots)
    assert crawler.radius**2*(crawler.vx-2.)+px==pytest.approx(0)
    assert crawler.radius**2*(crawler.vy-.5)+py==pytest.approx(0)
    assert crawler.shots_fired==1


def test_firing_impulse_establishes_flight_when_no_initial_wall_exists():
    from tests.test_wallcrawler import scene
    from creatures.wallcrawler_team import Intent
    crawler,enc=scene((500,500),walls=[])
    crawler.wall_intent=Intent(move=0,fire=True)
    crawler.gun_cooldown=0
    assert not crawler.wall_in_flight
    enc.step(1)
    assert crawler.wall_in_flight and crawler.just_fired
    velocity=crawler.vx,crawler.vy
    assert math.hypot(*velocity)>0
    start=crawler.get_pos()
    crawler.wall_intent=Intent(move=0,fire=False)
    for _ in range(10):enc.step(1)
    assert (crawler.vx,crawler.vy)==velocity
    assert crawler.get_pos()==pytest.approx((start[0]+velocity[0]*10,start[1]+velocity[1]*10))


def test_outward_recoil_releases_landing_capture_instead_of_erasing_the_kick():
    from tests.test_creature_learning import team_scene
    from tests.test_wallcrawler_movement import airborne
    from creatures.wallcrawler_team import Intent,Landing
    crew,enc,team=team_scene();crawler=crew[0]
    airborne(crawler,(400,587),(0.,.01))
    crawler.wall_phase='landing'
    crawler.wall_destination=Landing(enc.maze.walls[1],(400,600),(0,-1),(400,588))
    team.reservations[crawler.agent_id]=crawler.wall_destination
    crawler.angle=90;crawler.gun_cooldown=0
    crawler.wall_intent=Intent(move=0,fire=True)
    enc.step(1)
    assert crawler.just_fired and crawler.vy<0
    assert crawler.wall_phase=='flight' and crawler.wall_destination is None
    assert crawler.agent_id not in team.reservations
    velocity=crawler.vx,crawler.vy
    crawler.wall_intent=Intent(move=0,fire=False)
    enc.step(1)
    assert (crawler.vx,crawler.vy)==velocity


@pytest.mark.parametrize('curved',[False,True])
def test_recoiling_crawler_remains_clear_of_real_rock_and_steel(monkeypatch,curved):
    import config
    from level_layout import Layout
    from maze.generator import Maze
    from maze.config import MazeComplexity
    from creatures.wallcrawler_team import Intent
    from tests.test_wallcrawler import scene
    from tests.test_wallcrawler_movement import airborne
    monkeypatch.setattr(config,'SCREEN_WIDTH',1352);monkeypatch.setattr(config,'SCREEN_HEIGHT',878)
    layout=Layout(12,frozenset((5,y) for y in range(3,8)),(1,1),(10,10),
                  strong_walls=frozenset((7,y) for y in range(3,8)))
    maze=Maze(8,MazeComplexity.EMPTY,12,layout=layout,seed=41,curved=curved)
    position=maze.position_calculator.grid_center_to_screen(2,5)
    crawler,enc=scene(position);enc.world.maze=maze
    airborne(crawler,position,(3.,.2))
    crawler.angle=0;crawler.gun_cooldown=0
    crawler.wall_intent=Intent(move=0,fire=True)
    for _ in range(300):
        enc.step(1)
        assert maze.is_open(crawler.get_pos(),crawler.radius)
    assert crawler.shots_fired>0
