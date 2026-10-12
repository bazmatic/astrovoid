"""Flies the neural student with sampled controls and records what it needs to learn from the episode."""
import numpy as np
from experiments.harness import run_episode
from experiments.score import Weights
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE

KILL_REWARD_TOTAL = 100.0       # shared across every enemy that existed in the episode


class RolloutRecorder:
    """Per decision step: the senses, the controls the policy chose, and the events that followed."""

    def __init__(self, decision_frames):
        self.decision_frames = decision_frames
        self.senses, self.controls = [], []
        self._events = []                 # per step: kills, wall hits, enemy hits, idle seconds
        self._pending = False
        self._controller = None
        self._counter = None
        self._start_enemies = 0
        self._previous = (0, 0, 0, 0.0)

    # --- called by the harness ---
    def begin(self, game, hunter, settings):
        self._start_enemies = len(list(game.entity_manager.get_all_active_enemies()))
        original = game._neural_senses

        def spy(last_controls, now):
            sense = original(last_controls, now)
            if self._pending:
                self.senses.append(sense)
            return sense
        game._neural_senses = spy

    def before_frame(self, game, hunter):
        self._controller = game.hunter_controller
        if self._controller.frames % self.decision_frames == 0:
            self._pending = True
            self._events.append([0, 0, 0, 0.0])

    def add_frame(self, rotation, engine, trigger):
        pass

    def after_frame(self):
        if self._pending:
            self.controls.append(self._controller.last_controls)
            self._pending = False

    def counted(self, counter, elapsed):
        current = (counter.kills, counter.wall_hits, counter.hits_taken, counter.idle_seconds)
        for i, (now, before) in enumerate(zip(current, self._previous)):
            self._events[-1][i] += now - before
        self._previous = current
        self._counter = counter

    # --- result ---
    def arrays(self):
        n = min(len(self.senses), len(self.controls), len(self._events))
        spawned = self._counter.spawned if self._counter is not None else 0
        total = max(self._start_enemies + spawned, 1)
        weights = Weights()
        events = np.asarray(self._events[:n], dtype=np.float64).reshape(n, 4)
        rewards = (KILL_REWARD_TOTAL / total * events[:, 0] - weights.wall * events[:, 1]
                   - weights.hit * events[:, 2] - weights.idle / 60.0 * events[:, 3])
        return (np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE),
                np.asarray(self.controls[:n], dtype=np.int8).reshape(n, 3),
                rewards.astype(np.float32))


def fly_rollout(level, seed, spec, horizon=90.0):
    recorder = RolloutRecorder(spec.decision_frames)
    result = run_episode(level, seed, RULES, horizon, student=spec, recorder=recorder)
    senses, controls, rewards = recorder.arrays()
    return {'senses': senses, 'controls': controls, 'rewards': rewards, 'result': result}
