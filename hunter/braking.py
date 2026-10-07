"""Braking: is the ship going too fast for the wall on its course, and how to stop.

What matters is the wall the hull will actually reach on its present motion,
and whether the ship can stop short of it. Sliding quickly along a wall is not
closing on it. And the slower the ship, the shorter its stopping distance, so
the less any wall matters; below a crawl a wall is no threat at all.

Everything here is in the simulation's own units: pixels, frames, degrees.
"""
import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class BrakingSolution:
    """Whether the ship must brake for the wall on its course, and the burn that stops it."""
    wall_distance: Optional[float]  # Travel left before the hull touches a wall; None if none on course
    frames_to_impact: Optional[float]  # Coasting time to that wall; None if it is never reached
    stopping_distance: float  # Travel needed to stop, including the swing to the braking attitude
    safe_speed: float  # Fastest speed from which the ship could still stop in the room it has
    must_brake: bool  # The stop no longer fits: start braking now
    heading_degrees: float  # Absolute braking attitude: nose against the motion
    degrees_off_nose: float  # The same, relative to the nose now
    turn_frames: float  # Frames to swing there
    burn_frames: float  # Frames of thrust that then bring the ship to rest


def hull_travel(
    origin: Point, direction: Point, radius: float,
    walls: Sequence[Tuple[Point, Point]], limit: float
) -> Optional[float]:
    """How far a round hull can travel in a straight line before it touches a wall.

    This sweeps the whole hull, not a ray from its centre: a wall the hull
    would slide past is ignored however close it is, and the end of a wall the
    hull would clip is found even when the centre line misses it.

    Args:
        origin: Hull centre.
        direction: Direction of travel (any length).
        radius: Hull radius.
        walls: Wall segments, each as (start, end).
        limit: Furthest distance worth reporting.

    Returns:
        Distance the centre travels before contact, or None if no wall is met
        within `limit`.
    """
    length = math.hypot(*direction)
    if length < 1e-12:
        return None
    dx, dy = direction[0] / length, direction[1] / length
    best = None

    def consider(distance):
        nonlocal best
        if 0.0 <= distance <= limit and (best is None or distance < best):
            best = distance

    for start, end in walls:
        ex, ey = end[0] - start[0], end[1] - start[1]
        wall_length = math.hypot(ex, ey)
        ox, oy = origin[0] - start[0], origin[1] - start[1]
        if wall_length > 1e-12:
            ux, uy = ex / wall_length, ey / wall_length
            # Signed distance of the centre from the wall's line, and how fast it closes
            offset = ox * -uy + oy * ux
            closing = -(dx * -uy + dy * ux) * (1.0 if offset >= 0 else -1.0)
            if closing > 1e-12:
                distance = (abs(offset) - radius) / closing
                if distance >= 0.0:
                    # Touches the wall's face only if it arrives between its ends
                    along = (ox + dx * distance) * ux + (oy + dy * distance) * uy
                    if 0.0 <= along <= wall_length:
                        consider(distance)
        # The rounded ends of the wall: a circle of the hull's radius about each
        for px, py in (start, end):
            cx, cy = origin[0] - px, origin[1] - py
            b = cx * dx + cy * dy
            c = cx * cx + cy * cy - radius * radius
            if c <= 0.0:
                # Already touching: it counts only if the hull is pushing in
                if b < 0.0:
                    consider(0.0)
                continue
            disc = b * b - c
            if disc >= 0.0 and b < 0.0:
                consider(-b - math.sqrt(disc))
        # Already overlapping the face
        if wall_length > 1e-12:
            along = ox * ux + oy * uy
            offset = ox * -uy + oy * ux
            if 0.0 <= along <= wall_length and abs(offset) < radius:
                if (dx * -uy + dy * ux) * offset < 0.0:
                    consider(0.0)
    return best


def stopping_run(speed: float, lag_frames: float, thrust: float, friction: float = 1.0) -> Tuple[float, int]:
    """Distance covered, and frames of thrust used, bringing the ship to rest.

    The ship coasts for `lag_frames` (deciding, then swinging the nose round),
    then burns against its motion. Each frame applies thrust, then drag, then
    moves, exactly as the ship does.
    """
    lag = int(math.ceil(lag_frames))
    if thrust <= 0.0:
        return math.inf, 0
    if friction >= 1.0:
        burn = int(math.ceil(speed / thrust)) if speed > 0.0 else 0
        # Speeds after each burn frame fall by `thrust`; the last, at or below zero, moves nothing
        moving = max(0, burn - 1)
        return speed * lag + moving * speed - thrust * moving * (moving + 1) / 2, burn
    coasted = speed * friction * (1.0 - friction ** lag) / (1.0 - friction)
    speed *= friction ** lag
    if speed <= 0.0:
        return coasted, 0
    # After k burn frames the speed is friction**k * (speed + pull) - pull
    pull = thrust * friction / (1.0 - friction)
    burn = max(1, int(math.ceil(math.log(pull / (speed + pull)) / math.log(friction) - 1e-9)))
    moving = burn - 1
    braked = (speed + pull) * friction * (1.0 - friction ** moving) / (1.0 - friction) - pull * moving
    return coasted + braked, burn


def braking_solution(
    position: Point,
    velocity: Point,
    heading: float,
    walls: Sequence[Tuple[Point, Point]],
    radius: float,
    *,
    thrust: float,
    rotation_per_frame: float,
    sensor_range: float,
    friction: float = 1.0,
    reaction_frames: float = 0.0,
    harmless_speed: float = 0.0
) -> BrakingSolution:
    """Work out whether the ship must brake for the wall on its course.

    The ship must brake when the distance it needs to stop no longer fits in
    the room it has: the travel left before the hull touches a wall on its
    present motion, less the ground it covers before a decision takes effect.
    With no wall in sight the room is the sensor range, since nothing is known
    beyond it. A ship at or below `harmless_speed` is never asked to brake.

    Args:
        position: Ship position.
        velocity: Ship velocity per frame.
        heading: Nose heading in degrees.
        walls: Wall segments the ship can see.
        radius: Hull radius.
        thrust: Deceleration per frame of thrust.
        rotation_per_frame: Degrees the nose can swing per frame.
        sensor_range: How far the ship can see.
        friction: Share of its velocity the ship keeps each frame.
        reaction_frames: Frames before a decision to brake takes effect.
        harmless_speed: Speed at or below which touching a wall does not matter.

    Returns:
        The braking solution. At rest it reports no need to brake.
    """
    speed = math.hypot(*velocity)
    if speed < 1e-9 or thrust <= 0.0 or rotation_per_frame <= 0.0:
        return BrakingSolution(None, None, 0.0, harmless_speed, False, heading % 360, 0.0, 0.0, 0.0)
    retrograde = math.degrees(math.atan2(-velocity[1], -velocity[0]))
    off_nose = (retrograde - heading + 180) % 360 - 180
    turn_frames = abs(off_nose) / rotation_per_frame
    lag = reaction_frames + turn_frames
    wall_distance = hull_travel(position, velocity, radius, walls, sensor_range)
    room = sensor_range if wall_distance is None else wall_distance
    stopping_distance, burn_frames = stopping_run(speed, lag, thrust, friction)

    # Fastest speed whose stop fits in the room: found by halving the search range
    low, high = 0.0, max(speed, 1.0)
    while stopping_run(high, lag, thrust, friction)[0] <= room and high < 1e4:
        high *= 2.0
    for _ in range(30):
        middle = (low + high) / 2
        if stopping_run(middle, lag, thrust, friction)[0] <= room:
            low = middle
        else:
            high = middle
    safe_speed = max(low, harmless_speed)

    frames_to_impact = None
    if wall_distance is not None:
        if friction >= 1.0:
            frames_to_impact = wall_distance / speed
        else:
            # Each frame applies drag and then moves, so n frames cover
            # speed*friction*(1-friction**n)/(1-friction).
            remaining = 1.0 - wall_distance * (1.0 - friction) / (speed * friction)
            if remaining > 0.0:
                frames_to_impact = math.log(remaining) / math.log(friction)
    return BrakingSolution(
        wall_distance, frames_to_impact, stopping_distance, safe_speed,
        speed > safe_speed, retrograde % 360, off_nose, turn_frames, float(burn_frames))
