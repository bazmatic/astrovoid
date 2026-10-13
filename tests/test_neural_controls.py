import pytest
from hunter.model import PilotAction
from hunter.neural.controls import TURN_LEFT, TURN_NONE, TURN_RIGHT, step_labels, to_action

RATE = 5.0


def frames(*rows):
    return [tuple(r) for r in rows]


def test_to_action_is_a_plain_basic_action():
    a = to_action((TURN_LEFT, True, False))
    assert a == PilotAction(-1, True, False)
    assert not (a.track or a.course or a.worked_burn) and a.burn_heading is None and a.burn_frames is None
    assert to_action((TURN_RIGHT, False, True)) == PilotAction(1, False, True)
    assert to_action((TURN_NONE, False, False)).turn == 0


def test_a_held_left_turn_is_left_and_a_held_right_turn_is_right():
    assert step_labels(frames((-5, 0, 0), (-5, 0, 0), (-5, 0, 0)), RATE)[0] == TURN_LEFT
    assert step_labels(frames((5, 0, 0), (5, 0, 0), (5, 0, 0)), RATE)[0] == TURN_RIGHT


def test_a_nose_that_barely_moved_is_no_turn():
    assert step_labels(frames((0.1, 0, 0), (-0.1, 0, 0), (0, 0, 0)), RATE)[0] == TURN_NONE


def test_a_snapped_final_frame_still_counts_as_the_turn_that_led_to_it():
    # track mode: two full-rate frames then a small trim onto the solution
    assert step_labels(frames((-5, 0, 0), (-5, 0, 0), (-1, 0, 0)), RATE)[0] == TURN_LEFT


def test_opposite_turns_that_cancel_are_no_turn():
    assert step_labels(frames((-5, 0, 0), (5, 0, 0)), RATE)[0] == TURN_NONE


def test_thrust_is_on_when_the_engine_fired_in_at_least_half_the_frames():
    assert step_labels(frames((0, 1, 0), (0, 1, 0), (0, 0, 0), (0, 0, 0)), RATE)[1] is True    # exactly half
    assert step_labels(frames((0, 1, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)), RATE)[1] is False
    assert step_labels(frames((0, 0, 0), (0, 0, 0)), RATE)[1] is False


def test_the_trigger_is_on_if_it_was_held_or_a_shot_left_in_any_frame():
    assert step_labels(frames((0, 0, 0), (0, 0, 0), (0, 0, 1)), RATE)[2] is True
    assert step_labels(frames((0, 0, 0), (0, 0, 0)), RATE)[2] is False


def test_an_empty_step_is_all_off_not_an_error():
    assert step_labels([], RATE) == (TURN_NONE, False, False)
