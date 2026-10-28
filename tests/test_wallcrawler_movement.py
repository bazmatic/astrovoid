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
