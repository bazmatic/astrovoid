"""The student's basic controls, and how recorded per-frame behaviour is turned into them."""
from hunter.model import PilotAction

TURN_LEFT, TURN_NONE, TURN_RIGHT = 0, 1, 2


def to_action(controls):
    """A plain PilotAction for (turn_index, thrust, fire): no tracking, course or burn."""
    turn, thrust, fire = controls
    return PilotAction(turn - 1, bool(thrust), bool(fire))


def step_labels(frames, rate):
    """(turn_index, thrust, fire) for a step, from what the ship did in each of its frames.

    `frames` holds (rotation_degrees, engine_fired, trigger) per frame; `rate` is the ship's
    rotation per frame at full turn, in degrees. Turn is left or right if the nose rotated
    at least half a frame's worth that way over the step, else none. Thrust is on if the
    engine fired in at least half the frames. The trigger is on if it was held (or a shot
    left) in any frame.
    """
    if not frames:
        return TURN_NONE, False, False
    net = sum(f[0] for f in frames)
    if abs(net) >= 0.5 * rate:
        turn = TURN_RIGHT if net > 0 else TURN_LEFT
    else:
        turn = TURN_NONE
    thrust = sum(1 for f in frames if f[1]) * 2 >= len(frames)
    fire = any(f[2] for f in frames)
    return turn, thrust, fire
