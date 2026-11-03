"""A temporary reflex controller; it has exactly the same motors as a future policy."""
from dataclasses import dataclass
import math

from physics.inchworm import InchwormCommand, MAX_BEND

ARCH = (-.8, .4, .8, .4, -.8)


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
            loop = tuple(v*self.turn_sign for v in (-1., -1., -1., -.34/1.4, 1.3984/1.4))
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
            if self.elapsed > 240.:
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
        if self.phase == 'plant_front':
            requests[:] = [True, True]
            if physics.grips[leading] is not None:
                self.phase, self.elapsed = 'contract', 0.
            elif self.elapsed > self.stride_frames/2 and physics.grips[trailing] is not None:
                self.reverse = not self.reverse
                self.elapsed = 0.
            return InchwormCommand((0.,)*5, *requests)
        if self.phase == 'contract':
            requests[leading] = True
            if self.elapsed >= self.stride_frames/2:
                self.phase, self.elapsed = 'plant_rear', 0.
            return InchwormCommand(arch, *requests)
        if self.phase == 'plant_rear':
            requests[:] = [True, True]
            if physics.grips[trailing] is not None:
                self.phase, self.elapsed = 'extend', 0.
            elif self.elapsed > self.stride_frames/2:
                # An edge or obstruction: unfold on the supporting end and retry.
                self.phase, self.elapsed = 'recover', 0.
                self.reverse = not self.reverse
            return InchwormCommand(arch, *requests)
        requests[trailing] = True
        if self.elapsed >= self.stride_frames/2:
            self.phase, self.elapsed = 'plant_front', 0.
        return InchwormCommand((0.,)*5, *requests)
