"""Flies the neural student with sampled controls and records what it needs to learn from the episode."""
import bisect
import math
import numpy as np
from experiments.harness import FPS, run_episode
from experiments.score import Weights
from hunter.rule_params import RULES
from hunter.senses import FEATURE_NAMES, HIT_POINT_CELLS, SENSE_SIZE

KILL_REWARD_TOTAL = 100.0       # shared across every enemy that existed in the episode
BOREDOM_GRACE = 1.0             # seconds since the hunter was last in a cell before being there again is boring
FOLLOW_DEGREES = 45.0           # the compass counts as followed when it is this close to the nose

_SEEN = FEATURE_NAMES.index('enemy0_present')
_ALIVE = FEATURE_NAMES.index('enemies_present')
_COMPASS = {part: FEATURE_NAMES.index(f'enemy_compass_{part}') for part in ('present', 'sin', 'cos', 'dist')}


def compass_following(senses):
    """(blind steps, steps of those heading within FOLLOW_DEGREES of the enemy compass). Blind: enemies are left
    but none is in sight."""
    senses = np.asarray(senses).reshape(-1, SENSE_SIZE)
    blind = (senses[:, _ALIVE] == 1) & (senses[:, _SEEN] == 0) & (senses[:, _COMPASS['present']] == 1)
    off = np.degrees(np.abs(np.arctan2(senses[:, _COMPASS['sin']], senses[:, _COMPASS['cos']])))
    return int(blind.sum()), int((blind & (off < FOLLOW_DEGREES)).sum())


class RolloutRecorder:
    """Per decision step: the senses, the controls the policy chose, and the events that followed."""

    def __init__(self, decision_frames, wall_scale=1.0, hit_scale=1.0, still_penalty=0.0, still_speed=0.15,
                 turn_change_penalty=0.0, speed_penalty=0.0, powerup_reward=0.0, upgrade_bonus=0.0,
                 reversal_penalty=0.0, death_penalty=0.0, rules_bounty=0.0, compass_reward=0.0,
                 boredom_penalty=0.0, boredom_window=10.0, shot_price=0.0):
        self.decision_frames = decision_frames
        self.boredom_penalty = boredom_penalty    # shaping: points lost per second blind in a recently visited cell
        self.boredom_window = boredom_window      # seconds before a visited cell counts as new again
        self._cells = []                          # per step: the maze cell the hunter was in
        self.shot_price = shot_price              # shaping: points lost per shot fired with no enemy in sight
        self._shots = []                          # per step: shots the hunter fired
        self._shots_before = 0
        self.compass_reward = compass_reward    # shaping: points per maze width the compass route shortens, while blind
        self.compass_step_cap = 0.05    # a larger change in one step is the nearest enemy changing, not the hunter moving
        self.compass_hit_cap = 0.05     # ...except a drop of up to one hit on a wall block on the compass route
        self.wall_scale = wall_scale      # shaping: multiplies the wall-hit penalty in the reward only
        self.hit_scale = hit_scale        # likewise for the enemy-hit penalty
        self.still_penalty = still_penalty    # shaping: points lost per second spent slower than still_speed
        self.still_speed = still_speed        # as a fraction of the hunter's top speed
        self.turn_change_penalty = turn_change_penalty    # points lost each time a turn starts or reverses
        self.speed_penalty = speed_penalty    # shaping: points lost per second at standstill, scaled by the shortfall from top speed
        self.powerup_reward = powerup_reward    # shaping: points gained per powerup crystal the hunter collects
        self.death_penalty = death_penalty    # shaping: points lost when a mortal hunter is destroyed
        self.reversal_penalty = reversal_penalty    # shaping: extra points lost when the turn flips straight from left to right
        self.rules_bounty = rules_bounty    # shaping: points gained when the last Rules hunter is destroyed
        self._rules_paid = False
        self.upgrade_bonus = upgrade_bonus    # shaping: points gained per second the hunter's guns are upgraded
        self.upgraded_frames = 0
        self._died = False
        self.senses, self.controls = [], []
        self.speed_sum, self.frames = 0.0, 0     # mean speed as a share of top speed, for the dashboard
        self._events = []                 # per step: kills, wall impulse, enemy hits, idle seconds, near-still seconds, top-speed shortfall seconds, powerups, upgraded seconds, death, rules bounty
        self._pending = False
        self._controller = None
        self._counter = None
        self._start_enemies = 0
        self._previous = (0, 0, 0, 0.0)
        self._previous_powerups = 0

    # --- called by the harness ---
    def begin(self, game, hunter, settings):
        self._start_enemies = len(game.roster.alive())
        width = game.maze.grid_width * game.maze.cell_size_x
        self.compass_step_cap = 1.5 * hunter.max_speed * self.decision_frames / max(width, 1.0)
        cell = (game.maze.cell_size_x + game.maze.cell_size_y) / 2
        self.compass_hit_cap = 1.1 * HIT_POINT_CELLS * cell / max(width, 1.0)
        game.hunter_flight.on_observed(self._observed)

    def _observed(self, sense):
        if self._pending:
            self.senses.append(sense)

    def before_frame(self, game, hunter):
        self._controller = game.hunter_flight.controller
        if self._controller.frames % self.decision_frames == 0:
            self._pending = True
            self._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
            self._shots.append(0)
            maze = getattr(game, 'maze', None)
            if maze is not None:
                self._cells.append((int((hunter.x - maze.offset_x) // maze.cell_size_x),
                                    int((hunter.y - maze.offset_y) // maze.cell_size_y)))
        if self._shots:
            fired = getattr(hunter, 'shots_fired', 0)
            self._shots[-1] += fired - self._shots_before
            self._shots_before = fired
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
        if getattr(counter, 'rules_beaten', False) and not self._rules_paid:
            self._events[-1][9] = 1        # the step in which the last Rules hunter was destroyed
            self._rules_paid = True
        self._counter = counter

    # --- result ---
    def arrays(self):
        n = min(len(self.senses), len(self.controls), len(self._events))
        spawned = self._counter.spawned if self._counter is not None else 0
        total = max(self._start_enemies + spawned, 1)
        weights = Weights()
        events = np.asarray(self._events[:n], dtype=np.float64).reshape(n, 10)
        rewards = (KILL_REWARD_TOTAL / total * events[:, 0] - weights.quotient * self.wall_scale * events[:, 1]
                   - weights.hit * self.hit_scale * events[:, 2] - weights.idle / 60.0 * events[:, 3]
                   - self.still_penalty * events[:, 4] - self.speed_penalty * events[:, 5]
                   + self.powerup_reward * events[:, 6] + self.upgrade_bonus * events[:, 7]
                   - self.death_penalty * events[:, 8] + self.rules_bounty * events[:, 9])
        controls = np.asarray(self.controls[:n], dtype=np.int8).reshape(n, 3)
        # Turn control: 0 left, 1 none, 2 right. A turn starts (from none) or reverses when it differs from the
        # previous decision's and is not 'none'; holding a turn, or stopping one, is free.
        previous = np.concatenate([[1], controls[:-1, 0]]) if n else controls[:, 0]
        changes = (controls[:, 0] != 1) & (controls[:, 0] != previous)
        rewards = rewards - self.turn_change_penalty * changes
        reversals = changes & (previous != 1)             # the turn flipped straight over, with no pause between
        rewards = rewards - self.reversal_penalty * reversals
        senses = np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE)
        if self.compass_reward and n > 1:
            rewards = rewards + self.compass_reward * self._compass_progress(senses)
        if self.shot_price:
            rewards = rewards - self.shot_price * self.unaimed_shots(senses)
        if self.boredom_penalty:
            rewards = rewards - self.boredom_penalty * self.decision_frames / FPS * self._bored(senses, self._cells[:n])
        return senses, controls, rewards.astype(np.float32)

    def _bored(self, senses, cells):
        """Per step, whether the hunter is blind (enemies left, none in sight) in a cell it was last in between
        BOREDOM_GRACE and boredom_window seconds ago: spinning on the spot, dithering or looping."""
        step = self.decision_frames / FPS
        grace, window = round(BOREDOM_GRACE / step), round(self.boredom_window / step)
        visits, bored = {}, np.zeros(len(cells), dtype=bool)
        for i, cell in enumerate(cells):
            seen = visits.setdefault(cell, [])
            k = bisect.bisect_right(seen, i - grace)            # visits at least `grace` steps ago
            bored[i] = k > 0 and seen[k - 1] >= i - window
            seen.append(i)
        n = min(len(senses), len(cells))
        blind = np.zeros(len(cells), dtype=bool)
        blind[:n] = (senses[:n, _ALIVE] == 1) & (senses[:n, _SEEN] == 0)
        return bored & blind

    def unaimed_shots(self, senses):
        """Per step, the shots fired with no enemy in sight (at walls, or nothing)."""
        n = len(senses)
        shots = np.zeros(n)
        counted = np.asarray(self._shots[:n], dtype=np.float64)
        shots[:len(counted)] = counted
        return np.where(senses[:, _SEEN] == 0, shots, 0.0)

    def bored_steps(self, senses, cells):
        """(blind steps, bored steps of those) for the dashboard."""
        senses = np.asarray(senses).reshape(-1, SENSE_SIZE)
        blind = (senses[:, _ALIVE] == 1) & (senses[:, _SEEN] == 0)
        return int(blind.sum()), int(self._bored(senses, list(cells)[:len(senses)]).sum())

    def _compass_progress(self, senses):
        """Per step, how far (in maze widths) the compass route to the nearest enemy shortened by the next step,
        counted only while no enemy is in sight and when the change is one the hunter's own flight could make."""
        on = senses[:, _COMPASS['present']] == 1
        dist = senses[:, _COMPASS['dist']].astype(np.float64)
        progress = np.zeros(len(senses))
        delta = dist[:-1] - dist[1:]
        valid = (on[:-1] & on[1:] & (senses[:-1, _SEEN] == 0) & (delta >= -self.compass_step_cap)
                 & (delta <= max(self.compass_step_cap, self.compass_hit_cap)))
        progress[:-1] = np.where(valid, delta, 0.0)
        return progress


def fly_rollout(level, seed, spec, horizon=90.0, wall_scale=1.0, hit_scale=1.0,
                still_penalty=0.0, still_speed=0.15, random_start=False, turn_change_penalty=0.0,
                speed_penalty=0.0, powerup_reward=0.0, after_clear=0.0, upgrade_bonus=0.0, pursue_hunter=True, reversal_penalty=0.0,
                health=0, death_penalty=0.0, rules_bounty=0.0, compass_reward=0.0, boredom_penalty=0.0,
                boredom_window=10.0, shot_price=0.0):
    recorder = RolloutRecorder(spec.decision_frames, wall_scale, hit_scale, still_penalty, still_speed,
                               turn_change_penalty, speed_penalty, powerup_reward, upgrade_bonus, reversal_penalty, death_penalty,
                               rules_bounty, compass_reward, boredom_penalty, boredom_window, shot_price)
    result = run_episode(level, seed, RULES, horizon, student=spec, recorder=recorder, random_start=random_start,
                         after_clear=after_clear, pursue_hunter=pursue_hunter, health=health)
    senses, controls, rewards = recorder.arrays()
    blind, following = compass_following(senses)
    unseen, bored = recorder.bored_steps(senses, recorder._cells)
    return {'blind_steps': blind, 'following_steps': following, 'unseen_steps': unseen, 'bored_steps': bored,
            'unaimed_shots': int(recorder.unaimed_shots(senses).sum()),
            'senses': senses, 'controls': controls, 'rewards': rewards, 'result': result,
            'speed_fraction': recorder.speed_sum / recorder.frames if recorder.frames else 0.0,
            'upgraded_fraction': recorder.upgraded_frames / recorder.frames if recorder.frames else 0.0,
            'powerups': recorder._counter.powerups if recorder._counter is not None else 0,
            'died': result.end == 'died',
            'rules_arena': result.rules_hunters > 0, 'rules_beaten': result.rules_beaten}
