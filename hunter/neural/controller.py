"""Runs the neural policy inside the game loop: decides every few frames, holds the controls between."""
import config
from hunter.model import NEUTRAL
from hunter.neural.controls import to_action

START_CONTROLS = (1, False, False)   # no turn, coast, trigger off


class NeuralController:
    kind = 'neural'

    def __init__(self, policy, decision_frames, greedy=True, rng=None):
        self.policy, self.decision_frames = policy, max(1, int(decision_frames))
        self.greedy, self.rng = greedy, rng
        self.unavailable = policy is None
        self.closed = False
        self.action = NEUTRAL
        self.status = 'unavailable' if self.unavailable else 'waiting'
        self.frames = 0
        self.last_controls = (1, 0, 0)
        self._state = None if policy is None else policy.initial_state()

    def invalidate(self):
        """Forget the memory and start over (a new level, or a restart)."""
        self.frames = 0
        self.action = NEUTRAL
        self.last_controls = (1, 0, 0)
        if self.policy is not None:
            self._state = self.policy.initial_state()

    def close(self):
        if not self.closed:
            self.invalidate()
            self.closed = True
            self.status = 'coasting'

    def tick(self, senses_factory, running=True):
        if self.closed or self.unavailable:
            return NEUTRAL
        if not running:
            self.status = 'coasting'
            return NEUTRAL
        if self.frames % self.decision_frames == 0:
            senses = senses_factory(self.last_controls, self.frames / config.FPS)
            controls, self._state = self.policy.act(senses, self._state, self.greedy, self.rng)
            self.last_controls = (controls[0], 1 if controls[1] else 0, 1 if controls[2] else 0)
            self.action = to_action(controls)
        self.frames += 1
        self.status = 'active'
        return self.action
