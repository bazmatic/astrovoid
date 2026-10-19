"""The obstacle world: physics gates on a pymunk space.

The game moves everything itself, in px per frame. Once a frame, after everything has moved, `step` mirrors
the movers near a gate into the space as circle bodies at where they were before that frame's move, replays the
frame in the space, and writes back only to the movers that touched a gate: where the space put them and their
new velocity.
Pushing a gate is free: this world only changes positions and velocities, never damage or score.
"""
import logging
import math
from typing import List, Optional, Sequence, Tuple

import pymunk

import config
from level_layout import ANCHORED_KINDS  # noqa: F401 - the game asks this module which enemies are anchored
from maze.wall_segment import WallSegment

Point = Tuple[float, float]

# Shape categories: movers collide with walls and gates, never with each other
_WALL, _GATE, _MOVER = 0b001, 0b010, 0b100
_WALL_FILTER = pymunk.ShapeFilter(categories=_WALL, mask=_GATE | _MOVER)
_GATE_FILTER = pymunk.ShapeFilter(categories=_GATE, mask=_WALL | _GATE | _MOVER)
_MOVER_FILTER = pymunk.ShapeFilter(categories=_MOVER, mask=_WALL | _GATE)

_WALL_RADIUS = 1.0
# Daylight, in px, a resting plank keeps from wall shapes, kept-clear cells and other planks
FIT_CLEARANCE = 1.0

logger = logging.getLogger(__name__)


def plank_size(maze, settings=None) -> Tuple[float, float]:
    """A gate's half-length (pin to the centre of a rounded end) and thickness in px on this maze: the plank is
    `gateLengthCells` (average) cells long tip to tip."""
    s = settings if settings is not None else config.SETTINGS.obstacles
    thickness = max(6.0, s.gateThicknessCells * maze.cell_size)
    return max(thickness, s.gateLengthCells / 2 * maze.cell_size - thickness / 2), thickness


def _plank_line(maze, placement, half_length: float) -> Tuple[Point, Point]:
    px, py = maze.position_calculator.grid_center_to_screen(*placement.cell)
    dx = math.cos(math.radians(placement.angle)) * half_length
    dy = math.sin(math.radians(placement.angle)) * half_length
    return (px - dx, py - dy), (px + dx, py + dy)


def _cross(o: Point, p: Point, q: Point) -> float:
    return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])


def _closest_on(p: Point, a: Point, b: Point) -> Point:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq))
    return a[0] + dx * t, a[1] + dy * t


def _segment_gap(p1: Point, p2: Point, q1: Point, q2: Point) -> Tuple[float, Point]:
    """The shortest distance between segments p1-p2 and q1-q2, and the point of q1-q2 that is nearest."""
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    if d1 * d2 < 0 and _cross(p1, p2, q1) * _cross(p1, p2, q2) < 0:
        t = d1 / (d1 - d2)
        return 0.0, (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)
    best = None
    for p in (p1, p2):
        c = _closest_on(p, q1, q2)
        gap = math.hypot(p[0] - c[0], p[1] - c[1])
        if best is None or gap < best[0]:
            best = (gap, c)
    for q in (q1, q2):
        c = _closest_on(q, p1, p2)
        gap = math.hypot(q[0] - c[0], q[1] - c[1])
        if gap < best[0]:
            best = (gap, q)
    return best


def _segment_rect_gap(a: Point, b: Point, left: float, top: float, right: float, bottom: float) -> float:
    """The shortest distance between segment a-b and an axis-aligned rectangle (0 if they meet)."""
    def inside(p):
        return left <= p[0] <= right and top <= p[1] <= bottom

    if inside(a) or inside(b):
        return 0.0
    corners = ((left, top), (right, top), (right, bottom), (left, bottom))
    return min(_segment_gap(a, b, corners[i], corners[(i + 1) % 4])[0] for i in range(4))


def plank_fits(maze, placement, others: Sequence = (), keep_clear: Sequence = (), settings=None) -> bool:
    """Whether a gate's plank, at rest at its angle, keeps clear of the maze's wall blocks, of the `keep_clear`
    cells and of the planks of the `others` gates, in px on this maze (whose cells need not be square)."""
    half_length, thickness = plank_size(maze, settings)
    a, b = _plank_line(maze, placement, half_length)
    calc = maze.position_calculator
    cw, ch = calc.cell_size_x, calc.cell_size_y
    reach = thickness / 2 + _WALL_RADIUS + FIT_CLEARANCE
    origin_x, origin_y = calc.grid_to_screen(0, 0)
    cols = range(max(0, int((min(a[0], b[0]) - reach - origin_x) // cw)),
                 min(len(maze.grid[0]), int((max(a[0], b[0]) + reach - origin_x) // cw) + 1))
    rows = range(max(0, int((min(a[1], b[1]) - reach - origin_y) // ch)),
                 min(len(maze.grid), int((max(a[1], b[1]) + reach - origin_y) // ch) + 1))
    clear = set(keep_clear)
    for row in rows:
        for col in cols:
            if maze.grid[row][col] != 1 and (col, row) not in clear:
                continue
            left, top = calc.grid_to_screen(col, row)
            if _segment_rect_gap(a, b, left, top, left + cw, top + ch) < reach:
                return False
    for other in others:
        if _segment_gap(a, b, *_plank_line(maze, other, half_length))[0] < thickness + FIT_CLEARANCE:
            return False
    return True


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
        self.gates: List[Gate] = []
        for placement in placements:
            # The layout's checks are in cells; whether the plank really clears the walls depends on the screen
            if not plank_fits(self.maze, placement, [g.placement for g in self.gates], settings=self.settings):
                logger.warning('Skipping the gate at %s (angle %s): its plank does not fit here',
                               placement.cell, placement.angle)
                continue
            self.gates.append(self._add_gate(placement))
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
        half_length, thickness = plank_size(self.maze, s)
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

    def _mirror(self, mover, anchored: bool, dt: float = 0.0):
        """A circle body for a mover. A free mover starts where it was before this frame's move (`dt` frames
        of its velocity back), so the space replays the move and meets the plank where the mover would."""
        radius = float(mover.radius)
        if anchored:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = (mover.x, mover.y)
        else:
            mass = radius * radius
            body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, radius))
            body.velocity = (mover.vx * config.FPS, mover.vy * config.FPS)
            body.position = (mover.x - mover.vx * dt, mover.y - mover.vy * dt)
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
        mirrored = []  # [mover, body, shape, touched]
        for mover in movers:
            if self._near_a_gate(mover):
                body, shape = self._mirror(mover, anchored=False, dt=dt)
                mirrored.append([mover, body, shape, False])
        fixed = []
        for mover in anchored:
            if self._near_a_gate(mover):
                fixed.append(self._mirror(mover, anchored=True))

        substeps = max(1, int(self.settings.substeps))
        for _ in range(substeps):
            self.space.step(seconds / substeps)
            for entry in mirrored:
                if not entry[3]:
                    entry[3] = self._touches_gate(entry[1], gate_shapes)

        # Only a mover that touched a gate takes the space's version of its move; the rest keep their own
        for mover, body, shape, touched in mirrored:
            if touched:
                mover.x, mover.y = body.position.x, body.position.y
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

    def bullet_hit(self, projectile, dt: float = 1.0) -> bool:
        """Stop a projectile whose flight this frame (`dt` frames of its velocity back to where it is) touched a
        plank, giving the gate a small push along its flight. A fast shot can cross a thin plank between frames."""
        before = (projectile.x - projectile.vx * dt, projectile.y - projectile.vy * dt)
        now = (projectile.x, projectile.y)
        for gate in self.gates:
            gap, (cx, cy) = _segment_gap(before, now, *gate.ends())
            if gap > gate.thickness / 2 + projectile.radius:
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
