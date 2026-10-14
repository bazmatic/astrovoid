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
                 turn_change_penalty=0.0, speed_penalty=0.0, powerup_reward=0.0, upgrade_bonus=0.0,
                 reversal_penalty=0.0, death_penalty=0.0):
        self.decision_frames = decision_frames
        self.wall_scale = wall_scale      # shaping: multiplies the wall-hit penalty in the reward only
        self.hit_scale = hit_scale        # likewise for the enemy-hit penalty
        self.still_penalty = still_penalty    # shaping: points lost per second spent slower than still_speed
        self.still_speed = still_speed        # as a fraction of the hunter's top speed
        self.turn_change_penalty = turn_change_penalty    # points lost each time a turn starts or reverses
        self.speed_penalty = speed_penalty    # shaping: points lost per second at standstill, scaled by the shortfall from top speed
        self.powerup_reward = powerup_reward    # shaping: points gained per powerup crystal the hunter collects
        self.death_penalty = death_penalty    # shaping: points lost when a mortal hunter is destroyed
        self.reversal_penalty = reversal_penalty    # shaping: extra points lost when the turn flips straight from left to right
        self.upgrade_bonus = upgrade_bonus    # shaping: points gained per second the hunter's guns are upgraded
        self.upgraded_frames = 0
        self._died = False
        self.senses, self.controls = [], []
        self.speed_sum, self.frames = 0.0, 0     # mean speed as a share of top speed, for the dashboard
        self._events = []                 # per step: kills, wall impulse, enemy hits, idle seconds, near-still seconds, top-speed shortfall seconds, powerups
        self._pending = False
        self._controller = None
        self._counter = None
        self._start_enemies = 0
        self._previous = (0, 0, 0, 0.0)
        self._previous_powerups = 0

    # --- called by the harness ---
    def begin(self, game, hunter, settings):
        self._start_enemies = len(list(game.entity_manager.get_all_active_enemies()))
        game.hunter_flight.on_observed(self._observed)

    def _observed(self, sense):
        if self._pending:
            self.senses.append(sense)

    def before_frame(self, game, hunter):
        self._controller = game.hunter_flight.controller
        if self._controller.frames % self.decision_frames == 0:
            self._pending = True
            self._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0])
        if self._events and math.hypot(hunter.vx, hunter.vy) < self.still_speed * hunter.max_speed:
            self._events[-1][4] += 1.0 / FPS
        if self._events:
            share = math.hypot(hunter.vx, hunter.vy) / hunter.max_speed
            self.speed_sum += min(share, 1.0)
            self.frames += 1
            if getattr(hunter, 'gun_upgrade_level', 0):
                self.upgraded_frames += 1
                self._events[-1][7] += 1.0 / FPS
            shortfall = 1.0 - share
            self._events[-1][5] += min(max(shortfall, 0.0), 1.0) / FPS

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
        self._events[-1][6] += counter.powerups - self._previous_powerups
        self._previous_powerups = counter.powerups
        if counter.died and not self._died:
            self._events[-1][8] = 1        # the step in which the hunter was destroyed
            self._died = True
        self._counter = counter

    # --- result ---
    def arrays(self):
        n = min(len(self.senses), len(self.controls), len(self._events))
        spawned = self._counter.spawned if self._counter is not None else 0
        total = max(self._start_enemies + spawned, 1)
        weights = Weights()
        events = np.asarray(self._events[:n], dtype=np.float64).reshape(n, 9)
        rewards = (KILL_REWARD_TOTAL / total * events[:, 0] - weights.quotient * self.wall_scale * events[:, 1]
                   - weights.hit * self.hit_scale * events[:, 2] - weights.idle / 60.0 * events[:, 3]
                   - self.still_penalty * events[:, 4] - self.speed_penalty * events[:, 5]
                   + self.powerup_reward * events[:, 6] + self.upgrade_bonus * events[:, 7]
                   - self.death_penalty * events[:, 8])
        controls = np.asarray(self.controls[:n], dtype=np.int8).reshape(n, 3)
        # Turn control: 0 left, 1 none, 2 right. A turn starts (from none) or reverses when it differs from the
        # previous decision's and is not 'none'; holding a turn, or stopping one, is free.
        previous = np.concatenate([[1], controls[:-1, 0]]) if n else controls[:, 0]
        changes = (controls[:, 0] != 1) & (controls[:, 0] != previous)
        rewards = rewards - self.turn_change_penalty * changes
        reversals = changes & (previous != 1)             # the turn flipped straight over, with no pause between
        rewards = rewards - self.reversal_penalty * reversals
        return (np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE), controls,
                rewards.astype(np.float32))


def fly_rollout(level, seed, spec, horizon=90.0, wall_scale=1.0, hit_scale=1.0,
                still_penalty=0.0, still_speed=0.15, random_start=False, turn_change_penalty=0.0,
                speed_penalty=0.0, powerup_reward=0.0, after_clear=0.0, upgrade_bonus=0.0, pursue_hunter=True, reversal_penalty=0.0,
                health=0, death_penalty=0.0):
    recorder = RolloutRecorder(spec.decision_frames, wall_scale, hit_scale, still_penalty, still_speed,
                               turn_change_penalty, speed_penalty, powerup_reward, upgrade_bonus, reversal_penalty, death_penalty)
    result = run_episode(level, seed, RULES, horizon, student=spec, recorder=recorder, random_start=random_start,
                         after_clear=after_clear, pursue_hunter=pursue_hunter, health=health)
    senses, controls, rewards = recorder.arrays()
    return {'senses': senses, 'controls': controls, 'rewards': rewards, 'result': result,
            'speed_fraction': recorder.speed_sum / recorder.frames if recorder.frames else 0.0,
            'upgraded_fraction': recorder.upgraded_frames / recorder.frames if recorder.frames else 0.0,
            'powerups': recorder._counter.powerups if recorder._counter is not None else 0,
            'died': result.end == 'died'}
