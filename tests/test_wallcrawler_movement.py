"""Physical launch impulse, angular inertia, magnetic capture and grounded leg rendering."""
import math
from types import SimpleNamespace
import pygame
import pytest
from physics.angular_motion import turn
from creatures.wallcrawler_team import Intent,Landing
from tests.test_creature_learning import team_scene


def airborne(c,pos=(900,900),velocity=(1.1,.7)):
    c.x,c.y=pos;c.vx,c.vy=velocity
    c.wall_state='returning';c.wall_phase='flight';c.wall_in_flight=True
    c.wall_destination=None
    c.wall_intent=Intent(move=0,fire=False)


def test_angular_motion_accelerates_with_inertia_and_integrates_consistently():
    def body(radius=10):
        return SimpleNamespace(radius=radius,angle=0.,wall_body_angle=0.,wall_angular_velocity=0.)
    small,large=body(),body(20)
    turn(small,90,1);turn(large,90,1)
    first=small.wall_angular_velocity
    assert 0<large.wall_body_angle<small.wall_body_angle<3
    turn(small,90,1)
    assert small.wall_angular_velocity>first
    a,b=body(),body()
    for _ in range(30):turn(a,90,1)
    for _ in range(60):turn(b,90,.5)
    assert a.wall_body_angle==pytest.approx(b.wall_body_angle)
    assert a.wall_angular_velocity==pytest.approx(b.wall_angular_velocity)


def test_flight_and_a_midair_bump_keep_linear_momentum_without_homing():
    crew,enc,team=team_scene();c=crew[0]
    airborne(c)
    for _ in range(10):enc.step(1)
    assert c.get_pos()==pytest.approx((911,907))
    assert (c.vx,c.vy)==pytest.approx((1.1,.7))
    c.apply_momentum(2,-.4)
    for _ in range(50):
        enc.step(1)
        assert not c.just_fired
    assert (c.vx,c.vy)==pytest.approx((3.1,.3))
    assert c.get_pos()==pytest.approx((1066,922))
    assert c.wall_state=='returning'


def test_planted_legs_extend_during_the_launch_impulse(monkeypatch):
    crew,enc,team=team_scene();c=crew[0]
    c.wall_attach_cooldown=0
    site=Landing(enc.maze.walls[1],(400,600),(0,-1),(400,588))
    team.commit({c.agent_id:Intent(move=0,detach=True)},{c.agent_id:[site]+[None]*7})
    surface=pygame.Surface((1100,700));feet=[]
    monkeypatch.setattr(pygame.draw,'lines',lambda screen,colour,closed,points,width:feet.append(points[-1]))
    start=c.y
    speeds=[]
    for _ in range(10):
        enc.step(1);c.draw(surface);speeds.append(c.vy)
        assert not c.just_fired and c.wall_phase=='launch'
    assert speeds==sorted(speeds) and speeds[0]>0
    assert c.y>start+5
    assert feet and all(p[1]==pytest.approx(300) for p in feet)


def test_magnetic_capture_rotates_quickly_and_cushions_before_locking():
    crew,enc,team=team_scene();c=crew[0]
    airborne(c,pos=(400,560),velocity=(0,2.4))
    c.angle=c.wall_body_angle=90
    positions=[];spins=[];landing_frames=0
    for _ in range(100):
        enc.step(1)
        if c.wall_state=='attached':break
        assert not c.just_fired
        if c.wall_phase=='landing':
            positions.append(c.y);spins.append(abs(c.wall_angular_velocity));landing_frames+=1
    assert c.wall_state=='attached' and c.y==pytest.approx(588)
    assert 5<landing_frames<60
    assert positions[0]<positions[-1] and max(positions)<589.5
    assert max(spins)>math.pi  # Magnetic alignment is stronger than ordinary flight steering.
    assert c.wall_angular_velocity==0


def test_launch_spin_meets_the_wall_aligned_without_midair_steering():
    crew,enc,team=team_scene();c=crew[0];c.wall_attach_cooldown=0
    site=Landing(enc.maze.walls[1],(400,600),(0,-1),(400,588))
    team.commit({c.agent_id:Intent(move=0,detach=True)},{c.agent_id:[site]+[None]*7})
    spin=None;capture_error=None
    for _ in range(180):
        enc.step(1)
        if c.wall_phase=='flight':
            if spin is None:spin=c.wall_angular_velocity
            assert c.wall_angular_velocity==pytest.approx(spin)
        if c.wall_phase=='landing':
            capture_error=abs((c.wall_body_angle-270+180)%360-180)
            break
    assert capture_error is not None and capture_error<.01
    assert abs(spin)<=math.pi


@pytest.mark.parametrize('gap,offset',[(40,0),(120,25),(276,-45)])
def test_timed_spin_handles_short_and_diagonal_jumps(gap,offset):
    from maze.wall_segment import WallSegment
    crew,enc,team=team_scene();c=crew[0];c.wall_attach_cooldown=0
    wall=WallSegment((200,312+gap+12),(1000,312+gap+12),4)
    enc.maze.walls[1]=wall
    site=Landing(wall,(400+offset,wall.start[1]),(0,-1),(400+offset,312+gap))
    team.commit({c.agent_id:Intent(move=0,detach=True)},{c.agent_id:[site]+[None]*7})
    for _ in range(200):
        enc.step(1)
        if c.wall_phase=='landing':break
    assert c.wall_phase=='landing'
    assert abs((c.wall_body_angle-270+180)%360-180)<.01
    assert abs(c.wall_angular_velocity)<=math.pi+1e-8


def test_two_airborne_crawlers_bounce_instead_of_halting():
    crew,enc,team=team_scene()
    left,right=crew
    airborne(left,(400,450),(10.,0.))
    airborne(right,(450,450),(-10.,0.))
    for _ in range(4):enc.step(1)
    assert left.vx<0 and right.vx>0, (left.vx,right.vx)
    assert left.vx+right.vx==pytest.approx(0.)
    assert math.dist(left.get_pos(),right.get_pos())>=left.radius+right.radius


def test_peer_bounce_preserves_momentum_and_glancing_tangent():
    import config
    from creatures.wallcrawler_team import swept_peers
    crew,enc,team=team_scene()
    first,second=crew
    airborne(first,(430,450),(30.,7.))
    first.prev_x,first.prev_y=400,443
    airborne(second,(450,450),(-10.,-3.))
    second.radius=20
    before=(first.vx,first.vy,second.vx,second.vy)
    assert swept_peers(first,enc)
    nx,ny=first.x-second.x,first.y-second.y
    distance=math.hypot(nx,ny);nx,ny=nx/distance,ny/distance
    old_relative=(before[0]-before[2],before[1]-before[3])
    relative=(first.vx-second.vx,first.vy-second.vy)
    assert first.radius**2*first.vx+second.radius**2*second.vx==pytest.approx(100*before[0]+400*before[2])
    assert first.radius**2*first.vy+second.radius**2*second.vy==pytest.approx(100*before[1]+400*before[3])
    assert relative[0]*nx+relative[1]*ny==pytest.approx(-config.COLLISION_RESTITUTION*(old_relative[0]*nx+old_relative[1]*ny))
    assert relative[0]*-ny+relative[1]*nx==pytest.approx(old_relative[0]*-ny+old_relative[1]*nx)


def test_crawlers_moving_together_do_not_block_each_other():
    crew,enc,team=team_scene()
    left,right=crew
    airborne(left,(400,450),(50.,0.))
    airborne(right,(425,450),(50.,0.))
    enc.step(1)
    assert left.get_pos()==pytest.approx((450,450))
    assert right.get_pos()==pytest.approx((475,450))
    assert left.vx==right.vx==50


def test_high_speed_peer_collision_does_not_tunnel_and_keeps_bouncing():
    crew,enc,team=team_scene()
    left,right=crew
    airborne(left,(350,450),(150.,0.))
    airborne(right,(550,450),(-150.,0.))
    enc.step(1)
    assert left.x<right.x and math.dist(left.get_pos(),right.get_pos())>=left.radius+right.radius
    assert left.vx<0 and right.vx>0
    velocities=left.vx,right.vx
    enc.step(1)
    assert (left.vx,right.vx)==velocities


def test_flying_crawler_bounces_off_planted_peer_and_cancels_capture():
    import config
    from creatures.wallcrawler_team import swept_peers
    crew,enc,team=team_scene(((400,312),(500,312)))
    flying,planted=crew
    airborne(flying,(490,312),(40.,0.))
    flying.prev_x,flying.prev_y=450,312
    flying.wall_destination=Landing(enc.maze.walls[0],(450,300),(0,1),(450,312))
    flying.wall_phase='landing'
    team.reservations[flying.agent_id]=flying.wall_destination
    position=planted.get_pos()
    assert swept_peers(flying,enc)
    assert flying.vx==pytest.approx(-40*config.COLLISION_RESTITUTION)
    assert planted.get_pos()==position and planted.wall_state=='attached'
    assert flying.wall_phase=='flight' and flying.wall_destination is None and flying.wall_in_flight
    assert flying.agent_id not in team.reservations


def test_separating_peer_contact_does_not_apply_a_second_bounce():
    from creatures.wallcrawler_team import swept_peers
    crew,enc,team=team_scene()
    left,right=crew
    airborne(left,(400,450),(-10.,0.));left.prev_x,left.prev_y=405,450
    airborne(right,(420,450),(10.,0.))
    assert not swept_peers(left,enc)
    assert (left.vx,right.vx)==(-10.,10.)


def test_moving_planted_peer_impulse_is_consistent_for_subframe_steps():
    from creatures.wallcrawler_team import swept_peers
    import config
    velocities=[]
    for dt in (1.,.5):
        crew,enc,team=team_scene()
        planted,floating=crew
        planted.prev_x,planted.prev_y=500,312
        planted.x,planted.y=500+.65*dt,312
        airborne(floating,(521.1,312),(0.,0.))
        assert swept_peers(planted,enc,dt)
        velocities.append(floating.vx)
    assert velocities==pytest.approx([(1+config.COLLISION_RESTITUTION)*.65]*2)
