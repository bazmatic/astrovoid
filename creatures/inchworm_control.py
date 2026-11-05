"""A temporary reflex controller; it has exactly the same motors as a future policy."""
from dataclasses import dataclass
import math

from physics.inchworm import InchwormCommand, MAX_BEND, POSTURE_BEND

ARCH = tuple(v*POSTURE_BEND/MAX_BEND for v in (-.8, .4, .8, .4, -.8))
# The walking stride bends into a tall arch whose end bends cancel, so the tail and head links lie roughly parallel to
# the ground. With 1.8 rad joints the feet come to about 2.6 links apart (stretch ~0.44) before the rear plants.
STRIDE_ARCH = (-1., .5, 1., .5, -1.)
STRAIGHT_POSE = (-.156, .078, .156, .078, -.156)   # "straight" holds a very slight upward bend, never a drooping belly
REST_POSE = tuple(v*.4 for v in STRIDE_ARCH)        # how a worm sits when it appears: a relaxed hump, feet down
EXTEND_HEAD = None      # optional head-joint setpoint while the front is letting go (None: the straight pose's)
FOLDED = .5             # stretch (head-tail distance / full length) at which the arch is tall enough: the rear plants
STRAIGHT = .93          # stretch at which the body is straight again: the front plants
UNFOLDED = .35   # radians: no joint bent more than this counts as straight after a turn


def reach_angles(physics, point):
    """Five joint setpoints from bounded inverse kinematics; never writes the pose."""
    angles = [max(-MAX_BEND, min(MAX_BEND, b.angle-a.angle))
              for a, b in zip(physics.links, physics.links[1:])]
    base = physics.links[0].angle
    origin = physics.tail

    def points():
        result = [origin]
        angle = base
        for i in range(6):
            if i:
                angle += angles[i-1]
            result.append((result[-1][0]+math.cos(angle)*physics.length,
                           result[-1][1]+math.sin(angle)*physics.length))
        return result

    for _ in range(8):
        for j in reversed(range(5)):
            chain = points()
            pivot, head = chain[j+1], chain[-1]
            a = math.atan2(head[1]-pivot[1], head[0]-pivot[0])
            b = math.atan2(point[1]-pivot[1], point[0]-pivot[0])
            delta = (b-a+math.pi) % math.tau-math.pi
            angles[j] = max(-MAX_BEND, min(MAX_BEND, angles[j]+delta*.65))
    return tuple(a/MAX_BEND for a in angles)


@dataclass
class InchwormController:
    stride_frames: float = 160.
    phase: str = 'plant_front'
    elapsed: float = 0.
    reverse: bool = False
    attacking: bool = False
    turn_sign: float = 1.

    def request_turn(self, physics):
        self.phase, self.elapsed = 'turn_plant', 0.
        self.turn_sign = 1. if math.cos(physics.roll[0]) >= 0 else -1.

    def command(self, physics, dt, target=None):
        self.elapsed += dt
        if (target is not None and not self.phase.startswith('turn_') and physics.grab is None
                and (target.x-physics.centre[0])*math.cos(physics.heading)
                    +(target.y-physics.centre[1])*math.sin(physics.heading) < -physics.radius):
            self.request_turn(physics)
        if self.phase.startswith('turn_'):
            loop = tuple(v/MAX_BEND*self.turn_sign for v in (-1.4, -1.4, -1.4, -.34, 1.3984))   # fixed angles, whatever the joint range
            if self.phase == 'turn_plant':
                if physics.grips[0] is not None:
                    self.phase, self.elapsed = 'turn_loop', 0.
                return InchwormCommand(tuple(physics.activation), True, True)
            if self.phase == 'turn_loop':
                if self.elapsed >= 180.:
                    self.phase, self.elapsed = 'turn_land', 0.
                return InchwormCommand(loop, True, False)
            if self.phase == 'turn_land':
                if physics.grips[1] is not None:
                    self.phase, self.elapsed = 'turn_unfold', 0.
                elif self.elapsed > 240.:
                    self.phase, self.elapsed = 'recover', 0.
                return InchwormCommand(loop, True, True)
            # Unfold until the body is straight again (the setpoints take a few frames to relax), then walk on at once.
            straight = max(abs(b.angle-a.angle) for a, b in zip(physics.links, physics.links[1:])) < UNFOLDED
            if self.elapsed > 240. or (self.elapsed >= 20. and straight):
                self.phase, self.elapsed, self.reverse = 'plant_front', 0., False
            return InchwormCommand((0.,)*5, False, True)
        arch = tuple(v*(1. if math.cos(physics.roll[0]) >= 0 else -1.) for v in ARCH)
        if physics.grab is not None:
            return InchwormCommand(tuple(physics.activation), True, True, True)
        if target is not None and math.dist(physics.tail, target.get_pos()) < physics.length*5+target.radius:
            self.attacking = True
            self.phase, self.elapsed = 'plant_front', 0.
            dx, dy = target.x-physics.tail[0], target.y-physics.tail[1]
            distance = max(1e-8, math.hypot(dx, dy))
            # Reach for the near surface of the adversary, not its centre.
            point = (target.x-dx/distance*(target.radius+physics.skin*.5),
                     target.y-dy/distance*(target.radius+physics.skin*.5))
            close = math.dist(physics.head, target.get_pos()) <= target.radius+physics.skin+physics.reach*.3
            return InchwormCommand(reach_angles(physics, point), True, close, True)
        if self.attacking:
            self.attacking = False
            self.phase, self.elapsed = 'recover', 0.
        if self.phase == 'recover':
            # Lower the head while keeping the supporting legs planted.
            if self.elapsed > self.stride_frames/2:
                self.phase, self.elapsed = 'plant_front', 0.
            return InchwormCommand((0.,)*5, True, True)
        if target is not None and self.phase == 'plant_front':
            along = (target.x-physics.centre[0])*math.cos(physics.heading)+(target.y-physics.centre[1])*math.sin(physics.heading)
            self.reverse = along < 0
        leading, trailing = ((0, 1) if self.reverse else (1, 0))
        requests = [False, False]
        stretch = min(1., math.dist(physics.head, physics.tail)/(6*physics.length))
        stride = tuple(v*(1. if math.cos(physics.roll[0]) >= 0 else -1.) for v in STRIDE_ARCH)
        straight = tuple(v*(1. if math.cos(physics.roll[0]) >= 0 else -1.) for v in STRAIGHT_POSE)
        if self.phase == 'plant_front':
            # 1. Body straight, front planted (and the rear too, from the last stride).
            requests[:] = [True, True]
            if physics.grips[leading] is not None:
                self.phase, self.elapsed = 'contract', 0.
            elif self.elapsed > self.stride_frames/2 and physics.grips[trailing] is not None:
                self.reverse = not self.reverse
                self.elapsed = 0.
            return InchwormCommand(straight, *requests)
        if self.phase == 'contract':
            # 2. Release the rear and arch the body until the tail is up beside the front foot.
            requests[leading] = True
            if stretch <= FOLDED or self.elapsed >= self.stride_frames/2:
                self.phase, self.elapsed = 'plant_rear', 0.
            return InchwormCommand(stride, *requests)
        if self.phase == 'plant_rear':
            # 3. Plant the rear beside the front, holding the arch.
            requests[:] = [True, True]
            if physics.grips[trailing] is not None:
                self.phase, self.elapsed = 'extend', 0.
            elif self.elapsed > self.stride_frames/2:
                # The rear missed its landing (a bump, say): unfold on the supporting end and retry the same way.
                self.phase, self.elapsed = 'recover', 0.
            if EXTEND_HEAD is not None and physics.grips[trailing] is not None:
                stride = self._head_up(stride, EXTEND_HEAD, physics)     # start lifting the head before the front lets go
            return InchwormCommand(stride, *requests)
        # 4. Release the front and straighten on the planted rear, pushing the head forward.
        requests[trailing] = True
        if stretch >= STRAIGHT or self.elapsed >= self.stride_frames/2:
            self.phase, self.elapsed = 'plant_front', 0.
        if EXTEND_HEAD is not None:
            straight = self._head_up(straight, EXTEND_HEAD, physics)
        return InchwormCommand(straight, *requests)

    def _head_up(self, pose, value, physics):
        sign = 1. if math.cos(physics.roll[0]) >= 0 else -1.
        return pose[:-1]+(sign*value,) if not self.reverse else (sign*value,)+pose[1:]
