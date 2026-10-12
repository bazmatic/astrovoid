import numpy as np
import pytest
from hunter.model import NEUTRAL, PilotAction
from hunter.neural.controller import NeuralController
from hunter.neural.policy import random_policy
from hunter.senses import SENSE_SIZE


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, last_controls, now):
        self.calls.append((last_controls, now))
        return np.zeros(SENSE_SIZE, dtype=np.float32)


def test_it_decides_on_the_first_tick_then_every_n_frames():
    controller = NeuralController(random_policy(0), decision_frames=6)
    spy = Spy()
    for _ in range(13):
        controller.tick(spy)
    assert len(spy.calls) == 3                       # frames 0, 6 and 12
    assert spy.calls[1][1] == pytest.approx(6 / 60)  # simulated seconds, not the real clock


def test_controls_are_held_between_decisions_as_a_plain_action():
    controller = NeuralController(random_policy(1), decision_frames=4)
    spy = Spy()
    first = controller.tick(spy)
    held = [controller.tick(spy) for _ in range(3)]
    assert all(a is first for a in held)
    assert isinstance(first, PilotAction) and not first.track and not first.course
    assert first.burn_heading is None and first.burn_frames is None


def test_the_last_controls_are_passed_to_the_next_decision():
    controller = NeuralController(random_policy(2), decision_frames=1)
    spy = Spy()
    controller.tick(spy)
    controller.tick(spy)
    assert spy.calls[1][0] == controller.last_controls or spy.calls[1][0][0] in (0, 1, 2)
    assert spy.calls[0][0] == (1, 0, 0)               # nothing pressed yet


def test_not_running_returns_neutral_and_does_not_decide():
    controller = NeuralController(random_policy(3), decision_frames=2)
    spy = Spy()
    assert controller.tick(None, running=False) == NEUTRAL
    assert spy.calls == [] and controller.status == 'coasting'


def test_memory_is_reset_by_invalidate_and_a_fresh_controller_starts_clean():
    policy = random_policy(4)
    a = NeuralController(policy, decision_frames=1)
    spy = Spy()
    for _ in range(5):
        a.tick(spy)
    a.invalidate()
    b = NeuralController(policy, decision_frames=1)
    xs, ys = Spy(), Spy()
    first_a = a.tick(xs)
    first_b = b.tick(ys)
    assert first_a == first_b                          # same state, same senses: the same first decision


def test_greedy_play_is_deterministic():
    runs = []
    for _ in range(2):
        controller = NeuralController(random_policy(5), decision_frames=3)
        spy = Spy()
        runs.append([controller.tick(spy) for _ in range(30)])
    assert runs[0] == runs[1]


def test_without_a_policy_it_is_unavailable_and_coasts():
    controller = NeuralController(None, decision_frames=6)
    assert controller.unavailable and controller.tick(Spy()) == NEUTRAL
    assert controller.status == 'unavailable'


def test_close_stops_it():
    controller = NeuralController(random_policy(6), decision_frames=1)
    controller.close()
    assert controller.tick(Spy()) == NEUTRAL
