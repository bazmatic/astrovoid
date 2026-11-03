"""Articulated inchworm mechanics, in pixels and game frames (60 frames/second).

Six capsule links, five torque-limited bend muscles, and two breakable leg grips.
The solver owns motion. Controllers only supply InchwormCommand; they cannot place
feet, move the centre, or steer a detached body. No gravity in Astrovoid's arena.
"""
from dataclasses import dataclass
import math

import pymunk

from utils import get_closest_point_on_line

MUSCLES = 5
MAX_BEND = 1.4


@dataclass(frozen=True)
class InchwormCommand:
    """Signed joint setpoints (-1..1), rear/front grip requests, and jaw closure.

    Values outside the range are clipped; nonfinite values and wrong shapes fail.
    A released grip stays released even beside a surface. Grips only engage within
    leg reach, can slip under load, and do not supply propulsion on their own.
    """
    muscles: tuple = (0.,) * MUSCLES
    rear_grip: bool = False
    front_grip: bool = False
    bite: bool = False

    def __post_init__(self):
        values = tuple(float(v) for v in self.muscles)
        if len(values) != MUSCLES or not all(math.isfinite(v) for v in values):
            raise ValueError('inchworm requires five finite muscle commands')
        object.__setattr__(self, 'muscles', tuple(max(-1., min(1., v)) for v in values))


@dataclass
class Grip:
    surface: object
    foot: tuple
    normal: tuple
    pivot: object
    rotation: object
    anchor: tuple
    overload: float = 0.
    load: float = 0.


class InchwormPhysics:
    """A private articulated space with locally mirrored world surfaces and prey.

    step() advances forces/contacts and transfers the target's reaction impulse.
    pose() and observe() are plain data, safe for rendering, snapshots and future
    training. Wall objects need active/start/end. A target needs position, velocity
    and radius; health and allegiance are exclusively the creature trait's concern.
    """
    def __init__(self, position, radius=14., angle=0., velocity=(0., 0.)):
        self.radius = radius
        self.length = radius * .7
        self.skin = radius * .24
        self.reach = radius * 1.25
        self.mass = radius * radius
        self.space = pymunk.Space()
        self.space.iterations = 30
        self.space.damping = .996
        self.space.collision_slop = .05
        self.space.collision_bias = .1
        self.links, self.shapes, self.hinges = [], [], []
        self.activation = [0.] * MUSCLES
        self.roll = [0.] * 6
        self.roll_goal = [0.] * 6
        self.effort = 0.
        self.grips = [None, None]
        self.grip_cooldown = [0., 0.]
        self.surfaces = {}
        self.prey = self.prey_body = self.prey_shape = self.grab = None
        self.grab_load = self.grab_overload = self.grab_cooldown = 0.
        self.surface_contacts = [False] * 6
        direction = pymunk.Vec2d(math.cos(angle), math.sin(angle))
        centre = pymunk.Vec2d(*position)
        mass = self.mass / 6
        for i in range(6):
            a, b = (-self.length/2, 0.), (self.length/2, 0.)
            body = pymunk.Body(mass, pymunk.moment_for_segment(mass, a, b, self.skin))
            body.position = centre + direction * ((i-2.5)*self.length)
            body.velocity = velocity
            body.angle = angle
            shape = pymunk.Segment(body, a, b, self.skin)
            shape.friction, shape.elasticity = .55, .1
            shape.collision_type = 1
            self.space.add(body, shape)
            self.links.append(body)
            self.shapes.append(shape)
        for a, b in zip(self.links, self.links[1:]):
            joint = pymunk.PivotJoint(a, b, (self.length/2, 0.), (-self.length/2, 0.))
            joint.collide_bodies = False
            joint.error_bias = .01
            joint.max_bias = 4.
            limit = pymunk.RotaryLimitJoint(a, b, -1.6, 1.6)
            limit.collide_bodies = False
            self.space.add(joint, limit)
            self.hinges.append(joint)
        self.space.on_collision(1, 2, post_solve=self._wall_contact)

    @property
    def centre(self):
        return tuple(sum((b.position for b in self.links), pymunk.Vec2d(0, 0)) / 6)

    @property
    def velocity(self):
        return tuple(sum((b.velocity for b in self.links), pymunk.Vec2d(0, 0)) / 6)

    @property
    def head(self):
        return tuple(self.links[-1].local_to_world((self.length/2, 0.)))

    @property
    def tail(self):
        return tuple(self.links[0].local_to_world((-self.length/2, 0.)))

    @property
    def heading(self):
        return math.atan2(self.head[1]-self.tail[1], self.head[0]-self.tail[0])

    def pose(self):
        return tuple((tuple(b.local_to_world((-self.length/2, 0.))),
                      tuple(b.local_to_world((self.length/2, 0.)))) for b in self.links)

    def observe(self):
        """Body-relative proprioception; no privileged target/controller state."""
        forward = pymunk.Vec2d(math.cos(self.heading), math.sin(self.heading))
        side = forward.perpendicular()
        velocity = pymunk.Vec2d(*self.velocity)
        return {
            'joint_angles': tuple((b.angle-a.angle)/MAX_BEND for a, b in zip(self.links, self.links[1:])),
            'joint_rates': tuple(b.angular_velocity-a.angular_velocity for a, b in zip(self.links, self.links[1:])),
            'activation': tuple(self.activation),
            'roll_sin': tuple(math.sin(v) for v in self.roll),
            'roll_cos': tuple(math.cos(v) for v in self.roll),
            'velocity': (velocity.dot(forward)/self.length, velocity.dot(side)/self.length),
            'angular_velocity': sum(b.angular_velocity for b in self.links)/6,
            'grips': (self.grips[0] is not None, self.grips[1] is not None or self.grab is not None),
            'grip_loads': (self.grips[0].load if self.grips[0] else 0.,
                           self.grips[1].load if self.grips[1] else self.grab_load),
            'contacts': tuple(self.surface_contacts),
            'grabbing': self.grab is not None,
            'effort': self.effort,
        }

    def translate(self, delta):
        """Reconcile an external collision correction, including the saved anatomy."""
        if delta == (0., 0.):
            return
        for body in self.links:
            body.position += delta
            self.space.reindex_shapes_for_body(body)

    def impulse(self, impulse, point=None):
        """A point impulse spins the struck link; a bulk impulse shoves all links."""
        impulse = pymunk.Vec2d(*impulse)
        if point is None:
            for body in self.links:
                body.apply_impulse_at_world_point(impulse/6, body.position)
        else:
            body = min(self.links, key=lambda b: b.position.get_distance(point))
            body.apply_impulse_at_world_point(impulse, point)

    def release(self):
        for i in range(2):
            self._release_foot(i)
        self._release_prey()

    def _wall_contact(self, arbiter, space, data):
        for shape in arbiter.shapes:
            if shape in self.shapes:
                self.surface_contacts[self.shapes.index(shape)] = True

    def _sync_surfaces(self, walls, gates):
        present = {}
        for is_gate, surfaces in ((False, walls), (True, gates)):
            for wall in surfaces:
                if not wall.active or wall.start == wall.end:
                    continue
                key = id(wall)
                geometry = (tuple(wall.start), tuple(wall.end))
                previous = self.surfaces.get(key)
                if previous is not None and previous[1] == geometry:
                    present[key] = previous
                    continue
                if previous is not None:
                    for i, grip in enumerate(self.grips):
                        if grip is not None and grip.surface is wall:
                            self._release_foot(i)
                shape = pymunk.Segment(self.space.static_body, *geometry, 0.)
                shape.friction, shape.elasticity = .55, .1
                shape.collision_type = 2
                self.space.add(shape)
                present[key] = (wall, geometry, shape, is_gate)
        for key, old in self.surfaces.items():
            if key not in present or present[key] is not old:
                self.space.remove(old[2])
        self.surfaces = present

    def _release_foot(self, index):
        grip = self.grips[index]
        if grip is not None:
            self.space.remove(grip.pivot, grip.rotation)
            self.grips[index] = None

    def _try_foot(self, index):
        body = self.links[0 if index == 0 else -1]
        point = body.position
        candidates = []
        for wall, _, _, gate in self.surfaces.values():
            if gate:
                continue  # moving planks collide but cannot be anchored to
            foot = get_closest_point_on_line(point, wall.start, wall.end)
            delta = point-pymunk.Vec2d(*foot)
            distance = delta.length
            if self.skin-.1 <= distance <= self.reach:
                normal = delta/distance
                tangent = pymunk.Vec2d(-normal.y, normal.x)
                belly = body.rotation_vector.perpendicular()*math.cos(self.roll[0 if index == 0 else -1])
                if abs(body.rotation_vector.dot(tangent)) > .75 and belly.dot(normal) < -.65:
                    candidates.append((distance, wall, foot, normal))
        if not candidates:
            return
        _, wall, foot, normal = min(candidates, key=lambda c: c[0])
        # Planted legs support a resting height with bounded force and speed.
        # Only the surface normal is corrected; the tangential contact stays put.
        anchor = pymunk.Vec2d(*foot)+normal*self.radius*.85
        pivot = pymunk.PivotJoint(self.space.static_body, body, tuple(anchor), (0., 0.))
        pivot.max_force = self.mass * 1.8
        pivot.max_bias = .6
        pivot.error_bias = .001
        tangent_angle = math.atan2(normal.x, -normal.y)
        if math.cos(tangent_angle-body.angle) < 0:
            tangent_angle += math.pi
        tangent_angle = body.angle + (tangent_angle-body.angle+math.pi) % math.tau-math.pi
        rotation = pymunk.GearJoint(self.space.static_body, body, tangent_angle, 1.)
        rotation.max_force = self.mass * self.length * 1.2
        rotation.max_bias = .15
        rotation.error_bias = .01
        self.space.add(pivot, rotation)
        self.grips[index] = Grip(wall, tuple(foot), tuple(normal), pivot, rotation, tuple(anchor))

    def _release_prey(self):
        if self.grab is not None:
            self.space.remove(self.grab)
        self.grab = None
        self.grab_load = self.grab_overload = 0.

    def _sync_prey(self, target):
        if target is not self.prey:
            self._release_prey()
            if self.prey_body is not None:
                self.space.remove(self.prey_shape, self.prey_body)
            self.prey = target
            self.prey_body = self.prey_shape = None
            if target is not None:
                mass = max(1., target.radius**2)
                body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, target.radius))
                shape = pymunk.Circle(body, target.radius)
                shape.friction, shape.elasticity = .5, .15
                self.space.add(body, shape)
                self.prey_body, self.prey_shape = body, shape
        if target is not None:
            self.prey_body.position = target.get_pos()
            self.prey_body.velocity = (target.vx, target.vy)
            self.prey_body.angular_velocity = 0.
            self.prey_body.angle = 0.
            self.space.reindex_shapes_for_body(self.prey_body)

    def _try_prey(self):
        if self.prey_body is None:
            return
        offset = pymunk.Vec2d(*self.head)-self.prey_body.position
        if offset.length > self.prey.radius+self.skin+self.reach*.3:
            return
        point = offset.normalized()*self.prey.radius if offset.length > 1e-8 else pymunk.Vec2d(-self.prey.radius, 0)
        pivot = pymunk.PivotJoint(self.links[-1], self.prey_body, (self.length/2, 0.), tuple(point))
        pivot.collide_bodies = False
        pivot.max_force = self.mass*.65
        pivot.max_bias = .6
        pivot.error_bias = .1
        self.space.add(pivot)
        self.grab = pivot
        self._release_foot(1)

    @property
    def mouth_contact(self):
        return (self.grab is not None and
                math.dist(self.head, self.prey_body.position) <= self.prey.radius+self.skin+1.)

    def _twist_reflex(self, dt):
        """Roll free links belly-toward-surface after a turn, without planar thrust.

        This is a bounded torsional posture in the planar simulation, not a third
        spatial dimension. A foot cannot replant until its belly faces the wall.
        """
        surfaces = [w for w, _, _, gate in self.surfaces.values() if not gate]
        for i, body in enumerate(self.links):
            if (i == 0 and self.grips[0]) or (i == 5 and self.grips[1]):
                continue
            nearest = None
            for wall in surfaces:
                foot = get_closest_point_on_line(body.position, wall.start, wall.end)
                delta = body.position-pymunk.Vec2d(*foot)
                if .1 < delta.length < self.reach*4 and (nearest is None or delta.length < nearest.length):
                    nearest = delta
            if nearest is not None:
                toward = body.rotation_vector.perpendicular().dot(-nearest.normalized())
                if abs(toward) > .6:
                    self.roll_goal[i] = 0. if toward > 0 else math.pi
            self.roll[i] += max(-.07*dt, min(.07*dt, self.roll_goal[i]-self.roll[i]))

    def step(self, command, dt, walls=(), gates=(), target=None, can_grab=True, powered=True):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('inchworm dt must be finite and nonnegative')
        if dt == 0:
            return
        self._sync_surfaces(walls, gates)
        self._sync_prey(target)
        self.surface_contacts[:] = [False]*6
        initial_velocity = self.prey_body.velocity if self.prey_body is not None else None
        self.effort = 0.
        remaining = dt
        while remaining > 1e-9:
            # Bound travel per solve as well as duration: shots/blasts cannot tunnel
            # a thin link through a wall on a long game frame.
            speed = max(b.velocity.length+abs(b.angular_velocity)*self.length for b in self.links)
            h = min(.125, remaining, self.skin*.4/max(1., speed))
            if powered:
                self._twist_reflex(h)
            for i, requested in enumerate((command.rear_grip, command.front_grip)):
                self.grip_cooldown[i] = max(0., self.grip_cooldown[i]-h)
                grip = self.grips[i]
                if grip and (not requested or not grip.surface.active or id(grip.surface) not in self.surfaces):
                    self._release_foot(i)
                if requested and self.grips[i] is None and self.grip_cooldown[i] == 0 and not (i == 1 and self.grab):
                    self._try_foot(i)
            self.grab_cooldown = max(0., self.grab_cooldown-h)
            if not command.front_grip or not can_grab:
                self._release_prey()
            elif self.grab is None and self.grab_cooldown == 0:
                self._try_prey()
            for i, (a, b) in enumerate(zip(self.links, self.links[1:])):
                self.activation[i] += max(-.07*h, min(.07*h, command.muscles[i]-self.activation[i]))
                error = self.activation[i]*MAX_BEND-(b.angle-a.angle)
                inertia = a.moment*b.moment/(a.moment+b.moment)
                stiffness = inertia*2.0
                damping = 2*math.sqrt(stiffness*inertia)*.9
                maximum = self.mass*self.length*.25
                torque = max(-maximum, min(maximum, stiffness*error-damping*(b.angular_velocity-a.angular_velocity))) if powered else 0.
                a.torque -= torque
                b.torque += torque
                self.effort += abs(torque)/maximum*h/dt/MUSCLES
            self.space.step(h)
            for i, grip in enumerate(self.grips):
                if grip is None:
                    continue
                body = self.links[0 if i == 0 else -1]
                grip.load = max(abs(grip.pivot.impulse)/h/grip.pivot.max_force,
                                abs(grip.rotation.impulse)/h/grip.rotation.max_force)
                grip.overload = grip.overload+h if grip.load > .98 else 0.
                stretch = body.position.get_distance(grip.anchor)
                if stretch > self.reach*.6 or (grip.overload > 3. and stretch > 1.):
                    self._release_foot(i)
                    self.grip_cooldown[i] = 12.
            if self.grab is not None:
                self.grab_load = abs(self.grab.impulse)/h/self.grab.max_force
                self.grab_overload = self.grab_overload+h if self.grab_load > .98 else 0.
                if math.dist(self.head, self.prey_body.position) > self.prey.radius+self.reach or self.grab_overload > 1.5:
                    self._release_prey()
                    self.grab_cooldown = 12.
            remaining -= h
        if target is not None:
            # The game integrates the target's trajectory. Only transfer reaction
            # impulses here, excluding our space's ambient drag on its mirror.
            reaction = self.prey_body.velocity-initial_velocity*self.space.damping**dt
            target.vx += reaction.x
            target.vy += reaction.y
