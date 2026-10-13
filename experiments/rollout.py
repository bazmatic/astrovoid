"""Flies the neural student with sampled controls and records what it needs to learn from the episode."""
import math
import numpy as np
from experiments.harness import FPS, run_episode
from experiments.score import Weights
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE

KILL_REWARD_TOTAL = 100.0       # shared across every enemy that existed in the episode


class RolloutRecorder:
    """Per decision step: the senses, the controls the policy chose, and the events that followed."""

    def __init__(self, decision_frames, wall_scale=1.0, hit_scale=1.0, still_penalty=0.0, still_speed=0.15,
                 turn_change_penalty=0.0):
        self.decision_frames = decision_frames
        self.wall_scale = wall_scale      # shaping: multiplies the wall-hit penalty in the reward only
        self.hit_scale = hit_scale        # likewise for the enemy-hit penalty
        self.still_penalty = still_penalty    # shaping: points lost per second spent slower than still_speed
        self.still_speed = still_speed        # as a fraction of the hunter's top speed
        self.turn_change_penalty = turn_change_penalty    # points lost each time a turn starts or reverses
        self.senses, self.controls = [], []
        self._events = []                 # per step: kills, wall impulse, enemy hits, idle seconds, near-still seconds
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
            self._events.append([0, 0, 0, 0.0, 0.0])
        if self._events and math.hypot(hunter.vx, hunter.vy) < self.still_speed * hunter.max_speed:
            self._events[-1][4] += 1.0 / FPS

    def add_frame(self, rotation, engine, trigger):
        pass

    def after_frame(self):
        if self._pending:
            self.controls.append(self._controller.last_controls)
            self._pending = False

    def counted(self, counter, elapsed):
        current = (counter.kills, counter.wall_impulse, counter.hits_taken, counter.idle_seconds)
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
        events = np.asarray(self._events[:n], dtype=np.float64).reshape(n, 5)
        rewards = (KILL_REWARD_TOTAL / total * events[:, 0] - weights.quotient * self.wall_scale * events[:, 1]
                   - weights.hit * self.hit_scale * events[:, 2] - weights.idle / 60.0 * events[:, 3]
                   - self.still_penalty * events[:, 4])
        controls = np.asarray(self.controls[:n], dtype=np.int8).reshape(n, 3)
        # Turn control: 0 left, 1 none, 2 right. A turn starts (from none) or reverses when it differs from the
        # previous decision's and is not 'none'; holding a turn, or stopping one, is free.
        previous = np.concatenate([[1], controls[:-1, 0]]) if n else controls[:, 0]
        changes = (controls[:, 0] != 1) & (controls[:, 0] != previous)
        rewards = rewards - self.turn_change_penalty * changes
        return (np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE), controls,
                rewards.astype(np.float32))


def fly_rollout(level, seed, spec, horizon=90.0, wall_scale=1.0, hit_scale=1.0,
                still_penalty=0.0, still_speed=0.15, random_start=False, turn_change_penalty=0.0):
    recorder = RolloutRecorder(spec.decision_frames, wall_scale, hit_scale, still_penalty, still_speed,
                               turn_change_penalty)
    result = run_episode(level, seed, RULES, horizon, student=spec, recorder=recorder, random_start=random_start)
    senses, controls, rewards = recorder.arrays()
    return {'senses': senses, 'controls': controls, 'rewards': rewards, 'result': result}
