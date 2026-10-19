"""The obstacle world: physics gates on a pymunk space.

The game moves everything itself, in px per frame. Once a frame, after everything has moved, `step` mirrors
the movers near a gate into the space as circle bodies, steps the space one frame, and writes back only to the
movers that touched a gate: the correction the physics made to where they went, and their new velocity.
Pushing a gate is free: this world only changes positions and velocities, never damage or score.
"""
import math
from typing import List, Optional, Sequence, Tuple

import pymunk

import config
from maze.wall_segment import WallSegment

Point = Tuple[float, float]

ANCHORED_KINDS = ('anemone', 'flighthouse')

# Shape categories: movers collide with walls and gates, never with each other
_WALL, _GATE, _MOVER = 0b001, 0b010, 0b100
_WALL_FILTER = pymunk.ShapeFilter(categories=_WALL, mask=_GATE | _MOVER)
_GATE_FILTER = pymunk.ShapeFilter(categories=_GATE, mask=_WALL | _GATE | _MOVER)
_MOVER_FILTER = pymunk.ShapeFilter(categories=_MOVER, mask=_WALL | _GATE)

_WALL_RADIUS = 1.0


class Gate:
    """A plank on a pin through its middle, free or turned by a motor."""

    def __init__(self, placement, pin: Point, half_length: float, thickness: float, body: pymunk.Body,
                 shape: pymunk.Segment):
        self.placement = placement
        self.pin = pin
        self.half_length = half_length
        self.thickness = thickness
        self.body = body
        self.shape = shape

    @property
    def motor(self) -> Optional[str]:
        return self.placement.motor

    @property
    def angle(self) -> float:
        """Radians; increasing turns clockwise on screen (y down)."""
        return self.body.angle

    @property
    def angular_velocity(self) -> float:
        """Radians per second."""
        return self.body.angular_velocity

    @angular_velocity.setter
    def angular_velocity(self, value: float) -> None:
        self.body.angular_velocity = value

    def ends(self) -> Tuple[Point, Point]:
        """The two tips of the plank's centre line."""
        dx = math.cos(self.angle) * self.half_length
        dy = math.sin(self.angle) * self.half_length
        px, py = self.pin
        return (px - dx, py - dy), (px + dx, py + dy)


class ObstacleWorld:
    """The maze's walls as static segments and each gate as a pinned plank, in one pymunk space."""

    def __init__(self, maze, placements: Sequence, settings=None):
        self.maze = maze
        self.settings = settings if settings is not None else config.SETTINGS.obstacles
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)
        self._wall_shapes: List[pymunk.Segment] = []
        self._wall_generation: Optional[int] = None
        self._sync_walls()
        self.gates: List[Gate] = [self._add_gate(p) for p in placements]
        self._segments: List[WallSegment] = []
        self._refresh_segments()

    # --- building ---

    def _sync_walls(self) -> None:
        """Rebuild the static wall segments when a block has been destroyed since the last build."""
        if self._wall_generation == self.maze.wall_generation:
            return
        if self._wall_shapes:
            self.space.remove(*self._wall_shapes)
        static = self.space.static_body
        self._wall_shapes = []
        for wall in self.maze.walls:
            if not wall.active:
                continue
            shape = pymunk.Segment(static, wall.start, wall.end, _WALL_RADIUS)
            shape.elasticity = config.COLLISION_RESTITUTION
            shape.friction = 0.0
            shape.filter = _WALL_FILTER
            self._wall_shapes.append(shape)
        if self._wall_shapes:
            self.space.add(*self._wall_shapes)
        self._wall_generation = self.maze.wall_generation

    def _add_gate(self, placement) -> Gate:
        s = self.settings
        pin = self.maze.position_calculator.grid_center_to_screen(*placement.cell)
        half_length = self.maze.cell_size
        thickness = max(6.0, s.gateThicknessCells * self.maze.cell_size)
        a, b = (-half_length, 0.0), (half_length, 0.0)
        body = pymunk.Body(s.gateMass, pymunk.moment_for_segment(s.gateMass, a, b, thickness / 2))
        body.position = pin
        body.angle = math.radians(placement.angle)
        shape = pymunk.Segment(body, a, b, thickness / 2)
        shape.elasticity = s.gateElasticity
        shape.friction = 0.0
        shape.filter = _GATE_FILTER
        pivot = pymunk.PivotJoint(self.space.static_body, body, pin)
        self.space.add(body, shape, pivot)
        if placement.motor is not None:
            # A SimpleMotor drives (body - static) angular velocity to -rate, so 'cw' (angle up) takes -motorRate
            rate = -s.motorRate if placement.motor == 'cw' else s.motorRate
            motor = pymunk.SimpleMotor(self.space.static_body, body, rate)
            motor.max_force = s.motorMaxForce
            self.space.add(motor)
        return Gate(placement, pin, half_length, thickness, body, shape)

    # --- stepping ---

    def _near_a_gate(self, mover) -> bool:
        margin = self.settings.moverReachMargin
        for gate in self.gates:
            reach = gate.half_length + mover.radius + margin
            if (mover.x - gate.pin[0]) ** 2 + (mover.y - gate.pin[1]) ** 2 < reach * reach:
                return True
        return False

    def _mirror(self, mover, anchored: bool):
        radius = float(mover.radius)
        if anchored:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        else:
            mass = radius * radius
            body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, radius))
            body.velocity = (mover.vx * config.FPS, mover.vy * config.FPS)
        body.position = (mover.x, mover.y)
        shape = pymunk.Circle(body, radius)
        shape.elasticity = 1.0  # the wall's or the gate's elasticity decides the bounce
        shape.friction = 0.0
        shape.filter = _MOVER_FILTER
        self.space.add(body, shape)
        return body, shape

    def step(self, dt: float, movers: Sequence, anchored: Sequence = ()) -> None:
        """Advance the gates one frame (`dt` in frames) and push back on the movers that touched one."""
        self._sync_walls()
        seconds = dt / config.FPS
        decay = config.SHIP_FRICTION ** dt
        for gate in self.gates:
            if gate.motor is None:
                gate.body.angular_velocity *= decay

        gate_shapes = {gate.shape for gate in self.gates}
        mirrored = []  # (mover, body, shape, start position, start velocity, touched)
        for mover in movers:
            if self._near_a_gate(mover):
                body, shape = self._mirror(mover, anchored=False)
                mirrored.append([mover, body, shape, body.position, body.velocity, False])
        fixed = []
        for mover in anchored:
            if self._near_a_gate(mover):
                fixed.append(self._mirror(mover, anchored=True))

        substeps = max(1, int(self.settings.substeps))
        for _ in range(substeps):
            self.space.step(seconds / substeps)
            for entry in mirrored:
                if not entry[5]:
                    entry[5] = self._touches_gate(entry[1], gate_shapes)

        for mover, body, shape, start, velocity, touched in mirrored:
            if touched:
                moved = body.position - start
                correction = moved - velocity * seconds
                mover.x += correction.x
                mover.y += correction.y
                mover.vx = body.velocity.x / config.FPS
                mover.vy = body.velocity.y / config.FPS
            self.space.remove(body, shape)
        for body, shape in fixed:
            self.space.remove(body, shape)
        self._refresh_segments()

    @staticmethod
    def _touches_gate(body: pymunk.Body, gate_shapes) -> bool:
        touched = []

        def look(arbiter):
            a, b = arbiter.shapes
            if a in gate_shapes or b in gate_shapes:
                touched.append(True)

        body.each_arbiter(look)
        return bool(touched)

    # --- bullets and sight ---

    def bullet_hit(self, projectile) -> bool:
        """Stop a projectile that touches a plank, giving the gate a small push along its flight."""
        for gate in self.gates:
            (ax, ay), (bx, by) = gate.ends()
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((projectile.x - ax) * dx + (projectile.y - ay) * dy) / length_sq))
            cx, cy = ax + dx * t, ay + dy * t
            reach = gate.thickness / 2 + projectile.radius
            if (projectile.x - cx) ** 2 + (projectile.y - cy) ** 2 > reach * reach:
                continue
            speed = math.hypot(projectile.vx, projectile.vy)
            if speed > 0:
                impulse = self.settings.bulletImpulse
                gate.body.apply_impulse_at_world_point(
                    (projectile.vx / speed * impulse, projectile.vy / speed * impulse), (cx, cy)
                )
            projectile.active = False
            return True
        return False

    def _refresh_segments(self) -> None:
        self._segments = [WallSegment(*gate.ends(), hit_points=1, destructible=False) for gate in self.gates]

    def segments(self) -> List[WallSegment]:
        """Each plank's centre line, as a wall segment that can never be damaged."""
        return list(self._segments)
