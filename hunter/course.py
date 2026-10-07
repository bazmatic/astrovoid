"""Course correction: the turn and burn that point the ship's motion at a target.

The ship flies like the one in Asteroids: thrust only pushes along the nose
and adds to the motion it already has. Getting somewhere is therefore not a
matter of pointing at it. The nose has to point wherever the *change* in motion
needs to go, and the engine has to burn for just long enough.

Everything here is in the simulation's own units: pixels, frames, degrees.
"""
import math
from dataclasses import dataclass
from typing import Optional, Tuple

Vector = Tuple[float, float]


@dataclass(frozen=True)
class CourseCorrection:
    """A turn and a burn that leave the ship travelling straight at its target."""
    heading_degrees: float  # Absolute heading the nose must hold for the burn
    degrees_off_nose: float  # The same, relative to the nose now: negative left, positive right
    turn_frames: float  # Frames to swing the nose there
    burn_frames: float  # Frames of thrust once it is there
    final_speed: float  # Speed after the burn, never above the limit

    @property
    def total_frames(self) -> float:
        return self.turn_frames + self.burn_frames


def course_correction(
    position: Vector,
    velocity: Vector,
    heading: float,
    target: Vector,
    *,
    thrust: float,
    speed_limit: float,
    rotation_per_frame: float,
    target_velocity: Vector = (0.0, 0.0),
    approach_speed: Optional[float] = None,
    friction: float = 1.0
) -> Optional[CourseCorrection]:
    """Work out the turn and burn that aim the ship's motion at a target.

    After swinging to `heading_degrees` and burning for `burn_frames`, the ship
    is on a collision course: its motion relative to the target points straight
    at it. The correction is the smallest that does so. Speed already carrying
    the ship towards the target is kept, sideways drift is cancelled, and the
    ship is only sped up or slowed to bring its closing speed between
    `approach_speed` and what `speed_limit` allows.

    The burn never raises the speed above `speed_limit`; a ship already over
    it is brought back under. The ship keeps coasting while it turns and burns,
    drag bleeds its speed, and a moving target keeps moving; the answer allows
    for all three.

    Args:
        position: Ship position.
        velocity: Ship velocity per frame.
        heading: Nose heading in degrees.
        target: Target position.
        thrust: Acceleration per frame of thrust.
        speed_limit: The "too fast" speed the ship must not be left above.
        rotation_per_frame: Degrees the nose can swing per frame.
        target_velocity: Target velocity per frame.
        approach_speed: Closing speed to build if the ship has less. Defaults
            to half the speed limit.
        friction: Share of its velocity the ship keeps each frame (1.0 for no drag).

    Returns:
        The correction, or None when there is no engine, no speed to aim for,
        or the target is moving too fast to close on within the limit.
    """
    if thrust <= 0.0 or speed_limit <= 0.0 or rotation_per_frame <= 0.0 or not 0.0 < friction <= 1.0:
        return None
    wanted = speed_limit / 2 if approach_speed is None else approach_speed
    target_speed_sq = target_velocity[0] ** 2 + target_velocity[1] ** 2
    offset = (target[0] - position[0], target[1] - position[1])
    if math.hypot(*offset) < 1e-9:
        return CourseCorrection(heading % 360, 0.0, 0.0, 0.0, math.hypot(*velocity))

    def kept(frames: float) -> float:
        """Share of its speed a coasting ship still has after some frames of drag."""
        return friction ** frames

    def coasted(frames: float) -> float:
        """Distance covered per unit of starting speed while coasting for some frames."""
        if friction == 1.0:
            return frames
        return friction * (1.0 - kept(frames)) / (1.0 - friction)

    def burned(frames: float) -> float:
        """Distance covered per unit of thrust while burning for some frames."""
        if friction == 1.0:
            return 0.5 * frames * (frames + 1.0)
        return friction / (1.0 - friction) * (frames - coasted(frames))

    def frames_to_gain(speed: float) -> Optional[float]:
        """Frames of thrust that add this much speed against drag, or None if it never can."""
        if friction == 1.0:
            return speed / thrust
        short = 1.0 - speed * (1.0 - friction) / (thrust * friction)
        return math.log(short) / math.log(friction) if short > 0.0 else None

    burn_heading, turn_frames, burn_frames = heading, 0.0, 0.0
    final_speed = math.hypot(*velocity)
    # The turn and the burn both take time, during which the ship coasts, drag
    # bleeds its speed and the target moves on. Each of those changes the
    # answer, so settle on it by refining a few times.
    line = offset
    for _ in range(40):
        distance = math.hypot(*line)
        if distance < 1e-9:
            break
        toward = (line[0] / distance, line[1] / distance)
        # What is left of the ship's present motion once the manoeuvre is over
        fade = kept(turn_frames + burn_frames)
        carried = (velocity[0] * fade, velocity[1] * fade)
        drift_along = target_velocity[0] * toward[0] + target_velocity[1] * toward[1]
        # Fastest closing speed that keeps the ship's true speed within the limit
        headroom = drift_along ** 2 + speed_limit ** 2 - target_speed_sq
        fastest = math.sqrt(headroom) - drift_along if headroom > 0.0 else 0.0
        if fastest <= 1e-9:
            return None
        closing = ((carried[0] - target_velocity[0]) * toward[0]
                   + (carried[1] - target_velocity[1]) * toward[1])
        closing = max(min(wanted, fastest), min(closing, fastest))
        after = (closing * toward[0] + target_velocity[0], closing * toward[1] + target_velocity[1])
        change = (after[0] - carried[0], after[1] - carried[1])
        size = math.hypot(*change)
        final_speed = math.hypot(*after)
        if size < 1e-9:
            burn_heading, turn_frames, burn_frames = heading, 0.0, 0.0
            break
        needed = frames_to_gain(size)
        if needed is None:
            return None
        burn_heading = math.degrees(math.atan2(change[1], change[0]))
        turn_frames = abs((burn_heading - heading + 180) % 360 - 180) / rotation_per_frame
        burn_frames = needed
        # Where the ship ends up: coasting through the turn, then coasting and
        # accelerating through the burn, while the target carries on
        total = turn_frames + burn_frames
        glide = coasted(total)
        push = burned(burn_frames) * thrust / size
        line = (offset[0] + target_velocity[0] * total - velocity[0] * glide - change[0] * push,
                offset[1] + target_velocity[1] * total - velocity[1] * glide - change[1] * push)

    if burn_frames <= 0.0:
        return CourseCorrection(heading % 360, 0.0, 0.0, 0.0, final_speed)
    return CourseCorrection(
        burn_heading % 360, (burn_heading - heading + 180) % 360 - 180,
        turn_frames, burn_frames, final_speed)
