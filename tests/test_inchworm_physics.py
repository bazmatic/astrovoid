"""Conservation, contact, and actuator limits through the worm's motor interface."""
import math
from types import SimpleNamespace

import pytest

from maze.wall_segment import WallSegment
from physics.inchworm import InchwormCommand, InchwormPhysics, MAX_BEND
from creatures.inchworm_control import ARCH


def floor():
    return WallSegment((0., 300.), (1000., 300.), 1)


def momentum(p):
    return tuple(sum(getattr(b.velocity, axis)*b.mass for b in p.links) for axis in ('x', 'y'))


def angular_momentum(p):
    return sum(b.position.cross(b.velocity*b.mass)+b.moment*b.angular_velocity for b in p.links)


def test_free_muscles_bend_but_cannot_create_linear_or_angular_momentum():
    p = InchwormPhysics((400., 200.))
    p.space.damping = 1.
    p.step(InchwormCommand(ARCH), 60.)
    assert p.centre == pytest.approx((400., 200.), abs=1e-6)
    assert momentum(p) == pytest.approx((0., 0.), abs=1e-7)
    assert angular_momentum(p) == pytest.approx(0., abs=.05)
    assert max(abs(v) for v in p.observe()['joint_angles']) > .5
    assert not any(p.observe()['grips'])


def test_motor_changes_are_gradual_and_bones_do_not_stretch():
    p = InchwormPhysics((400., 200.))
    before = p.pose()
    p.step(InchwormCommand((1.,)*5), 1.)
    assert max(abs(a) for a in p.activation) <= .071
    assert max(math.dist(a, b) for old, new in zip(before, p.pose()) for a, b in zip(old, new)) < 1.
    p.step(InchwormCommand((1.,)*5), 80.)
    for left, right in zip(p.pose(), p.pose()[1:]):
        assert math.dist(left[1], right[0]) < .15
    assert max(abs(a) for a in p.observe()['joint_angles']) * MAX_BEND <= MAX_BEND+.25


def test_alternating_grips_produce_repeatable_forward_progress():
    p, wall = InchwormPhysics((400., 286.)), floor()
    for _ in range(4):
        x = p.centre[0]
        p.step(InchwormCommand(ARCH, False, True), 80., [wall])
        assert p.grips[1] is not None
        front = p.head
        assert p.centre[0] > x+3
        p.step(InchwormCommand(ARCH, True, True), 2., [wall])
        assert p.grips[0] is not None
        p.step(InchwormCommand((0.,)*5, True, False), 80., [wall])
        assert p.head[0] > front[0]+8
        assert abs(p.tail[1]-288.1) < 1.
    assert p.centre[0] > 440.


def test_grip_requests_in_empty_space_do_not_anchor_and_release_keeps_momentum():
    p = InchwormPhysics((400., 200.), velocity=(3., -2.))
    p.space.damping = 1.
    p.step(InchwormCommand(rear_grip=True, front_grip=True), 12.)
    assert not any(p.grips)
    assert p.centre == pytest.approx((436., 176.), abs=1e-6)
    assert p.velocity == pytest.approx((3., -2.))


def test_destroyed_wall_and_overloaded_grips_release():
    p, wall = InchwormPhysics((400., 286.)), floor()
    cmd = InchwormCommand(rear_grip=True, front_grip=True)
    p.step(cmd, 10., [wall])
    assert all(p.grips)
    wall.active = False
    p.step(cmd, 1., [wall])
    assert not any(p.grips)
    wall.active = True
    p.step(cmd, 10., [wall])
    p.impulse((0., -p.mass*20))
    p.step(cmd, 4., [wall])
    assert not any(p.grips)
    assert p.velocity[1] < -1.


def test_fast_detached_body_cannot_tunnel_through_a_wall():
    wall = WallSegment((460., 0.), (460., 600.), 1)
    p = InchwormPhysics((400., 200.), velocity=(70., 0.))
    p.step(InchwormCommand(), 4., [wall])
    assert max(point[0] for segment in p.pose() for point in segment) <= 460-p.skin+.2
    assert p.velocity[0] <= .1


def test_subdividing_elapsed_time_preserves_the_trajectory():
    a, b, wall = InchwormPhysics((400., 286.)), InchwormPhysics((400., 286.)), floor()
    cmd = InchwormCommand(ARCH, False, True)
    a.step(cmd, 40., [wall])
    for _ in range(160):
        b.step(cmd, .25, [wall])
    for x, y in zip(a.pose(), b.pose()):
        assert x[0] == pytest.approx(y[0], abs=1e-7)
        assert x[1] == pytest.approx(y[1], abs=1e-7)


def test_grab_applies_equal_opposite_impulse_without_teleporting_prey():
    p = InchwormPhysics((400., 200.))
    p.space.damping = 1.
    prey = SimpleNamespace(x=445., y=200., vx=0., vy=0., radius=10.)
    prey.get_pos = lambda: (prey.x, prey.y)
    p.step(InchwormCommand(front_grip=True, bite=True), 2., target=prey)
    assert p.grab is not None
    assert prey.get_pos() == (445., 200.)
    assert prey.vx < 0
    total = momentum(p)
    assert (total[0]+prey.vx*100, total[1]+prey.vy*100) == pytest.approx((0., 0.), abs=1e-6)
    p.step(InchwormCommand(front_grip=True), 1., target=prey, can_grab=False)
    assert p.grab is None


def test_front_landing_grabs_and_holds_without_a_grip_request():
    p, wall = InchwormPhysics((400., 280.), velocity=(0., 1.)), floor()
    p.step(InchwormCommand(), 8., [wall])
    assert p.grips[1] is not None
    assert p.grips[0] is None
    grip = p.grips[1]
    p.step(InchwormCommand(), 2., [wall])
    assert p.grips[1] is grip


def test_front_reflex_release_stays_released_until_clear_then_relands():
    p, wall = InchwormPhysics((400., 286.)), floor()
    p.step(InchwormCommand(front_grip=True), 1., [wall])
    p.step(InchwormCommand(), 1., [wall])
    assert p.grips[1] is None
    p.step(InchwormCommand(), 1., [wall])
    assert p.grips[1] is None
    # Move clear and return to isolate the contact/reflex state machine.
    p.translate((0., -40.))
    p.step(InchwormCommand(), .1, [wall])
    p.translate((0., 40.))
    p.step(InchwormCommand(), 1., [wall])
    assert p.grips[1] is not None


def test_front_reflex_can_grab_prey_but_respects_can_grab():
    p = InchwormPhysics((400., 200.))
    prey = SimpleNamespace(x=470., y=200., vx=0., vy=0., radius=10.)
    prey.get_pos = lambda: (prey.x, prey.y)
    p.step(InchwormCommand(), .1, target=prey)
    prey.x = 445.
    p.step(InchwormCommand(), 1., target=prey, can_grab=False)
    assert p.grab is None
    p.step(InchwormCommand(), 1., target=prey)
    assert p.grab is not None
    grab = p.grab
    p.step(InchwormCommand(), 1., target=prey)
    assert p.grab is grab
    p.step(InchwormCommand(front_grip=True), .1, target=prey)
    p.step(InchwormCommand(), .1, target=prey)
    assert p.grab is None


def test_unpowered_front_reflex_does_not_grab():
    p, wall = InchwormPhysics((400., 246.)), floor()
    p.step(InchwormCommand(), .1, [wall])  # Arm in free space before the stun.
    p.translate((0., 40.))
    p.step(InchwormCommand(), 1., [wall], powered=False)
    assert p.grips[1] is None


@pytest.mark.parametrize('muscles', [(1.,)*4, (float('nan'),)*5, (float('inf'),)*5])
def test_invalid_motor_commands_are_rejected(muscles):
    with pytest.raises(ValueError):
        InchwormCommand(muscles)


def test_loop_twist_reflex_and_grip_handover_turn_the_head_around():
    from creatures.inchworm_control import InchwormController
    p,wall = InchwormPhysics((400.,286.)),floor()
    controller = InchwormController()
    controller.request_turn(p)
    saw_loop = saw_front_grip = False
    stretched = 0.
    for _ in range(520):
        p.step(controller.command(p,1.),1.,[wall])
        saw_loop |= max(abs(b.angle-p.links[0].angle) for b in p.links) > math.pi
        saw_front_grip |= p.grips[1] is not None and math.cos(p.links[-1].angle) < -.9
        if saw_front_grip:
            stretched = max(stretched,math.dist(p.head,p.tail))      # it walks on after the turn, so it is not always stretched
    assert saw_loop and saw_front_grip
    assert math.cos(p.heading) < -.9
    assert math.cos(p.roll[-1]) < -.9
    assert p.head[0] < p.tail[0]
    assert stretched > p.length*5


def test_runaway_velocity_fails_explicitly_instead_of_spinning_forever():
    p = InchwormPhysics((400.,200.))
    p.links[0].velocity = (1e16,0.)
    with pytest.raises(RuntimeError, match='stable substep budget'):
        p.step(InchwormCommand(),1.)


def test_a_single_bent_joint_drags_its_neighbours_into_an_arc():
    p = InchwormPhysics((400., 200.))
    p.step(InchwormCommand((0., 0., 1., 0., 0.)), 90.)
    bends = [b.angle-a.angle for a, b in zip(p.links, p.links[1:])]
    assert bends[2] > 0 and bends[1] > .05 and bends[3] > .05
    assert bends[2] > bends[1] and bends[2] > bends[3]


def test_front_reflex_grips_a_head_landing_at_a_slant():
    p, wall = InchwormPhysics((400., 286.)), floor()
    head = p.links[-1]
    head.angle = math.radians(50)   # well off parallel: the rear feet could not plant like this
    p.translate((0., -40.))
    p.step(InchwormCommand(), .1, [wall])
    p.translate((0., 40.))
    p.step(InchwormCommand(), .2, [wall])
    assert p.grips[1] is not None


def test_front_reflex_rearms_for_a_head_resting_at_the_surface_after_release():
    p, wall = InchwormPhysics((400., 286.)), floor()
    p.step(InchwormCommand(front_grip=True), 1., [wall])
    p.step(InchwormCommand(), 1., [wall])
    assert p.grips[1] is None
    p.step(InchwormCommand(), 30., [wall])
    assert p.grips[1] is not None


def test_a_foot_asking_to_grip_is_pulled_onto_a_nearby_surface():
    def rear_grip_after(request):
        p, wall = InchwormPhysics((400., 268.)), floor()   # the rear foot starts out of reach of the floor, but near it
        p.step(InchwormCommand(rear_grip=request), 60., [wall])
        return p.grips[0] is not None
    assert rear_grip_after(True)
    assert not rear_grip_after(False)


def test_scripted_crawl_walks_like_an_inchworm():
    """Straight with both feet down; release the rear and arch; land the rear beside the front; release the front and
    straighten, pushing the head on; plant the front again."""
    from creatures.inchworm_control import InchwormController
    p,wall = InchwormPhysics((200.,286.)),WallSegment((0.,300.),(4000.,300.),1)
    controller = InchwormController()
    seen = set()
    for frame in range(1500):
        p.step(controller.command(p,1.),1.,[wall])
        if frame < 300:
            continue
        stretch = min(1.,math.dist(p.head,p.tail)/(6*p.length))
        rear,front = p.grips[0] is not None,p.grips[1] is not None
        seen.add(('straight, both down' if stretch > .93 and rear and front else
                  'arching, rear up' if stretch < .85 and front and not rear else
                  'folded, both down' if stretch < .7 and rear and front else
                  'straightening, front up' if stretch > .7 and rear and not front else None))
    assert {'straight, both down','arching, rear up','folded, both down','straightening, front up'} <= seen
    assert p.centre[0] > 200.+20.*(1200/60)        # and it covers ground: well over 20 px/s
