"""Thresholds in the hunter tests that depend on how strong the hunter's engine is."""
REFERENCE_THRUST = 0.0375  # The engine these tests' absolute numbers were first written for


def scaled_seconds(seconds, thrust_force):
    """A burn that changes the speed as much as `seconds` did at the reference engine.

    A stronger engine makes the same change of speed in proportionally less time.
    """
    return seconds * REFERENCE_THRUST / thrust_force
