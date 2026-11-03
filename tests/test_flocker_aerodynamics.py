"""Flocker turns steer their path, rather than rotating above sideways momentum."""
import math
import pytest
from creatures.flocker_team import Intent
from tests.test_neural_flocker import scene


def heading(c):
    return math.degrees(math.atan2(c.vy,c.vx))


def difference(a,b):
    return (a-b+180)%360-180


def test_turning_bends_the_flight_path_without_thrust():
    (c,),enc,team=scene(positions=((500.,400.),))
    c.vx,c.vy=2.,0.
    team.commit({0:Intent(turn=1.)})
    enc.step(1.)
    assert c.y>400.
    assert c.vy>0
    assert abs(difference(heading(c),c.angle))<1e-9
    assert math.hypot(c.vx,c.vy)<=2.


def test_stationary_flocker_cannot_rotate_in_place():
    (c,),enc,team=scene(positions=((500.,400.),))
    team.commit({0:Intent(turn=1.)})
    for _ in range(12):
        enc.step(1.)
    assert c.angle==0.
    assert c.get_pos()==(500.,400.)


def test_faster_flight_has_a_wider_turning_radius():
    def fly(speed):
        (c,),enc,team=scene(positions=((500.,400.),))
        c.vx=speed
        team.commit({0:Intent(turn=1.)})
        enc.step(1.)
        return math.hypot(c.vx,c.vy)/math.radians(c.angle),c.angle
    slow,slow_turn=fly(1.)
    fast,fast_turn=fly(3.2)
    assert fast>slow*2
    assert fast_turn<slow_turn


def test_left_and_right_arcs_are_symmetric():
    results=[]
    for turn in (-1.,1.):
        (c,),enc,team=scene(positions=((500.,400.),))
        c.vx=2.
        team.commit({0:Intent(turn=turn,throttle=.4)})
        for _ in range(12):
            enc.step(1.)
        results.append((c.x,c.y,c.vx,c.vy))
    a,b=results
    assert a[0]==pytest.approx(b[0])
    assert a[1]-400==pytest.approx(400-b[1])
    assert a[2]==pytest.approx(b[2])
    assert a[3]==pytest.approx(-b[3])


def test_a_sustained_turn_traces_a_circle_without_losing_speed():
    (c,),enc,team=scene(positions=((500.,400.),))
    trait=next(t for t in c.traits if t.NAME=='thrusters')
    c.vx=1.5
    # Sustain speed against drag, then fly a half-circle at maximum turn.
    throttle=-math.log(trait.friction)*1.5/trait.force
    team.commit({0:Intent(turn=1.,throttle=throttle)})
    omega=min(math.radians(trait.turn_rate),trait.lateral_accel/1.5)
    radius=1.5/omega
    enc.step(math.pi/omega)
    assert c.angle==pytest.approx(180.)
    assert c.x==pytest.approx(500.,abs=1e-7)
    assert c.y==pytest.approx(400.+2*radius,abs=1e-7)
    assert math.hypot(c.vx,c.vy)==pytest.approx(1.5)


def test_throttle_off_glides_and_drag_reduces_speed():
    (c,),enc,team=scene(positions=((500.,400.),))
    c.vx=2.
    team.commit({0:Intent()})
    enc.step(1.)
    first=c.vx
    assert 0<first<2.
    assert c.x>500.
    for _ in range(30):
        enc.step(1.)
    assert 0<c.vx<first and c.vy==pytest.approx(0.)


def test_external_sideways_momentum_recovers_gradually():
    (c,),enc,team=scene(positions=((500.,400.),))
    c.vy=2.
    team.commit({0:Intent()})
    enc.step(1.)
    assert 0<heading(c)<90.
    assert c.vy>1.5  # no instantaneous erasure of the collision's sideways motion
    assert c.vx>0


def test_frame_substeps_follow_the_same_flight():
    def fly(dt,count):
        (c,),enc,team=scene(positions=((500.,400.),))
        c.vx=1.5
        team.commit({0:Intent(turn=.4,throttle=.3)})
        for _ in range(count):
            enc.step(dt)
        return c.x,c.y,c.vx,c.vy,c.angle
    whole=fly(1.,12)
    half=fly(.5,24)
    assert whole==pytest.approx(half,abs=.002)
    assert fly(2.,6)==pytest.approx(whole,abs=1e-9)


def test_old_policy_is_rejected_for_new_flight(tmp_path):
    from dataclasses import replace
    from learning.adapters.flocker import SPEC,load_policy
    from learning.policy import random_policy
    path=tmp_path/'space-flight.npz'
    random_policy(replace(SPEC,version=1),0).save(path)
    with pytest.raises(ValueError,match='schema'):
        load_policy(path)


def test_scripted_flocker_builds_airspeed_to_turn_towards_target_behind_it():
    import creatures
    from tests.creature_parts import encounter,target,world
    c=creatures.build('flocker',(500.,400.),angle=180.)
    enc=encounter(c,world_=world(ship=target((800.,400.))))
    for _ in range(120):
        enc.step(1.)
    assert math.hypot(c.vx,c.vy)>.5
    assert c.x>500.
    assert abs(difference(heading(c),c.angle))<1e-7


def test_forward_throttle_does_not_accelerate_a_backwards_collision_impulse():
    speeds=[]
    for throttle in (0.,1.):
        (c,),enc,team=scene(positions=((500.,400.),))
        c.vx=-2.
        team.commit({0:Intent(throttle=throttle)})
        enc.step(1.)
        speeds.append(math.hypot(c.vx,c.vy))
    assert speeds[1]<speeds[0]
