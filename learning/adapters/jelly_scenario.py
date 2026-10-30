"""Neural Jellies hunting plain drifting practice targets in the real cave arenas, under the game's own Encounter,
Jelly body and wall-bounce code. Stage 1: navigation to a moving target. A catch is body contact; the target then
respawns elsewhere and the episode runs on to the horizon, so the Jellies must catch repeatedly."""
from collections import Counter, deque
from dataclasses import replace
import hashlib
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from learning.environment import Snapshot, Transition
from learning.adapters.jelly import SPEC, CRITIC_SIZE, observe, critic, intention, teacher, enabled
from learning.adapters.crawler_scenario import TRAIN_LEVELS, HOLDOUT_LEVELS, SilentSound
from creatures.jelly_team import DECISION_FRAMES

STAGES = (1, 2)                # stage 2 (flanking) shares this scene; its shaping arrives with the stage-2 work
TARGET_COUNT = 1               # one plain target: every Jelly in the team hunts the same one
TARGET_START_DISTANCE = 250.   # px: targets start at least this far from every Jelly (else the farthest open cell)
RESPAWN_DISTANCE = 300.        # px: a caught target reappears at least this far from every Jelly
JELLY_SPACING = 60.            # px between Jelly starts
CATCH_REWARD = 10.             # to the Jelly that touches the target
TEAM_CATCH_SHARE = .25         # every other living Jelly gets this share of CATCH_REWARD for a teammate's catch
PROGRESS_REWARD = .002         # per pixel a Jelly closes on its target over a decision (about .03 at full speed)
STUCK_WINDOW = 60              # frames (one second) over which displacement is measured
STUCK_DISTANCE = 10.           # px: moving less than this over the window, accelerating throughout it, is stuck
STUCK_ACCEL = .1               # an intent's accel above this counts as accelerating
STUCK_PENALTY = .05            # per decision spent stuck (.5 per second)
MAX_TEAM = 8                   # the critic's member slots


class JellyEnvironment:
    spec = SPEC
    adapter = sys.modules[__name__]   # the collector asks the adapter for enabled() and teacher_action()

    def __init__(self, horizon=60.0, arenas=None, scripted=False):
        self.horizon, self.arenas, self.scripted = horizon, arenas, scripted
        self.world = None
        self.render_frames = None

    def reset(self, seed, level=11, team_size=1, stage=1):
        import pygame
        import config
        import creatures
        import level_config
        from creatures.encounter import Encounter
        from creatures.jelly_team import get_jelly_team
        from entities.command_recorder import CommandRecorder
        from game_handlers.enemy_roster import EnemyRoster
        from game_handlers.collision_handler import CollisionHandler
        from scoring.system import ScoringSystem
        from maze.generator import Maze
        from physics.obstacle_world import ObstacleWorld
        from level_layout import parse_layout
        from maze.config import MazeComplexity
        if stage not in STAGES:
            raise ValueError(f'unknown jelly stage: {stage}')
        if type(team_size) is not int or not 1 <= team_size <= MAX_TEAM:
            raise ValueError(f'team size must be 1..{MAX_TEAM}')
        self.close()
        random.seed(seed)
        self.rng = rng = random.Random(seed)
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1352, 878))
        self._screen_settings = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1352, 878
        arena = self.arenas.get(str(level)) if self.arenas else level_config.load_level_config(level)
        grid_size = arena['maze']['grid_size']
        complexity = MazeComplexity[arena['maze']['complexity'].upper()]
        layout = parse_layout(arena['layout'], grid_size) if 'layout' in arena else None
        if layout is not None:
            layout = replace(layout, enemies=(), beacon=None)
        maze = Maze(level, complexity, grid_size, layout=layout, seed=seed, curved=True)
        obstacles = ObstacleWorld(maze, layout.gates) if layout is not None and layout.gates else None
        maze.gate_segments = obstacles.segments() if obstacles else []
        from learning.adapters.practice_targets import TARGET_RADIUS
        cells = [maze.position_calculator.grid_center_to_screen(c, r)
                 for r in range(1, maze.grid_height-1) for c in range(1, maze.grid_width-1) if not maze.grid[r][c]]
        rng.shuffle(cells)
        self.cells = [p for p in cells if maze.is_open(p, TARGET_RADIUS+2)]
        starts = [p for p in self.cells if maze.is_open(p, 11)]
        scoring = ScoringSystem()
        scoring.power_drain_enabled = False
        handler = CollisionHandler(SilentSound(), scoring, CommandRecorder())
        handler.drop_pickup = lambda *a, **k: None   # training never generates pickups
        self.world = SimpleNamespace(ship=None, hunter=None, maze=maze, projectiles=[], roster=EnemyRoster(),
                                     scoring=scoring, sound_manager=SilentSound(),
                                     command_recorder=handler.command_recorder, collision_handler=handler,
                                     powerup_crystals=[], jev_beacon_allowed=lambda: False, combat_ruleset='legacy',
                                     additional_targets=[], jelly_policy=None,
                                     _hunter_sees_player=lambda: False)
        chosen = []
        for i in range(team_size):
            pos = next((p for p in starts if all(math.dist(p, q) >= JELLY_SPACING for q in chosen)), None)
            if pos is None:
                raise ValueError('arena has insufficient separated jelly starts')
            chosen.append(pos)
            c = creatures.build('neural_jelly', pos, level)
            c.agent_id = i
            self.world.roster.add(c)
        self.enc = Encounter(self.world.roster, self.world)
        self.enc.ready()
        self.team = get_jelly_team(self.enc)
        self.team.external = not self.scripted   # scripted: no policy, so the trait chases like the scripted Jelly
        self.team._next_id = team_size
        from learning.adapters.practice_targets import PracticeTarget
        for _ in range(TARGET_COUNT):
            target = PracticeTarget(self.free_cell(TARGET_START_DISTANCE), 0., 0., firing_enabled=False)
            self.launch(target)
            self.world.additional_targets.append(target)
        self.obstacles = obstacles
        self.level, self.seed, self.team_size, self.stage = level, seed, team_size, stage
        self.agent_ids = tuple(range(team_size))
        self.frames = 0
        self.agent_catches = Counter()
        self.agent_returns = Counter()
        self.agent_stuck_frames = Counter()
        self.generation = Counter()   # how many times each target has respawned
        self.trails = {c.agent_id: deque([c.get_pos()], maxlen=STUCK_WINDOW//DECISION_FRAMES+1)
                       for c in self.team.members()}
        self.pushes = {c.agent_id: deque(maxlen=STUCK_WINDOW//DECISION_FRAMES) for c in self.team.members()}
        self.action_trace = []
        return self.snapshot()

    def free_cell(self, distance):
        """A random open cell at least `distance` from every living Jelly, else the one farthest from them."""
        jellies = [c.get_pos() for c in self.team.members()]
        def clearance(p):
            return min((math.dist(p, q) for q in jellies), default=float('inf'))
        for p in self.rng.sample(self.cells, len(self.cells)):
            if clearance(p) >= distance:
                return p
        return max(self.cells, key=clearance)

    def launch(self, target):
        from learning.adapters.practice_targets import TARGET_SPEED_MIN, TARGET_SPEED_MAX
        heading, speed = self.rng.uniform(0, 2*math.pi), self.rng.uniform(TARGET_SPEED_MIN, TARGET_SPEED_MAX)
        target.vx, target.vy = math.cos(heading)*speed, math.sin(heading)*speed

    def respawn(self, target):
        target.x, target.y = self.free_cell(RESPAWN_DISTANCE)
        self.launch(target)
        self.generation[id(target)] += 1

    def pursuit(self, c):
        """The Jelly's current target, its respawn generation and the distance to it."""
        t = self.enc.target_entity_for(c)
        if t is None:
            return None
        return id(t), self.generation[id(t)], math.dist(c.get_pos(), t.get_pos())

    def snapshot(self):
        batch = {c.agent_id: observe(self.team, c) for c in self.team.members()}
        return Snapshot({i: v[0] for i, v in batch.items()}, {i: v[1] for i, v in batch.items()}, critic(self.team),
                        {i: critic(self.team, i) for i in batch})

    def ended(self):
        return self.frames >= self.horizon*60 or not self.team.members()

    def catch(self, rewards):
        """Body contact with a target is a catch: the toucher takes CATCH_REWARD, each other living Jelly a share."""
        caught = 0
        for target in self.world.additional_targets:
            if not target.active:
                continue
            members = self.team.members()
            toucher = next((c for c in members
                            if math.dist(c.get_pos(), target.get_pos()) <= c.radius + target.radius), None)
            if toucher is None:
                continue
            caught += 1
            self.agent_catches[toucher.agent_id] += 1
            for c in members:
                rewards[c.agent_id] += CATCH_REWARD if c is toucher else TEAM_CATCH_SHARE*CATCH_REWARD
            self.respawn(target)
        return caught

    def step(self, actions):
        if self.ended():
            raise RuntimeError('step after episode ended')
        members = self.team.members()
        if self.scripted:
            accelerating = {c.agent_id: True for c in members}   # the scripted Drift always pushes
        else:
            intents = {i: intention(a) for i, a in actions.items()}
            self.team.commit(intents)
            accelerating = {i: intent.accel > STUCK_ACCEL for i, intent in intents.items()}
        self.action_trace.append({str(i): [float(v) for v in a] for i, a in actions.items()})
        before = {c.agent_id: self.pursuit(c) for c in members}
        rewards = {i: 0. for i in self.agent_ids}
        frames = 0
        for _ in range(DECISION_FRAMES):
            for target in self.world.additional_targets:
                target.step(self.world.maze)
            self.enc.step(1)
            self.world.roster.update_dying(1)
            if self.obstacles:
                self.obstacles.step(1/60, self.world.roster.alive())
                self.world.maze.gate_segments = self.obstacles.segments()
            self.catch(rewards)
            self.frames += 1
            frames += 1
            if self.render_frames is not None:
                self.render_frames(self)
            if self.ended():
                break
        for c in self.team.members():
            i = c.agent_id
            now, then = self.pursuit(c), before.get(i)
            if now is not None and then is not None and now[:2] == then[:2]:
                rewards[i] += PROGRESS_REWARD*(then[2]-now[2])
            trail, pushes = self.trails[i], self.pushes[i]
            trail.append(c.get_pos())
            pushes.append(accelerating.get(i, False))
            if (len(pushes) == pushes.maxlen and all(pushes)
                    and math.dist(trail[0], trail[-1]) < STUCK_DISTANCE):
                rewards[i] -= STUCK_PENALTY
                self.agent_stuck_frames[i] += frames
        self.agent_returns.update(rewards)
        terminated = not self.team.members()
        truncated = self.frames >= self.horizon*60 and not terminated
        return Transition(self.snapshot(), sum(rewards.values()), terminated, truncated, self.events(),
                          agent_rewards=rewards)

    def events(self):
        return {'catches': sum(self.agent_catches.values()), 'agent_catches': dict(self.agent_catches),
                'seconds': self.frames/60, 'stuck_seconds': sum(self.agent_stuck_frames.values())/60,
                'agent_stuck_seconds': {i: f/60 for i, f in self.agent_stuck_frames.items()},
                'alive': len(self.team.members()), 'stage': self.stage,
                'agent_returns': {i: self.agent_returns[i] for i in self.agent_ids}}

    def close(self):
        if hasattr(self, '_screen_settings'):
            import config
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT = self._screen_settings
            del self._screen_settings
        if self.world is not None:
            self.enc.close()
            self.world = None


def teacher_action(env, agent_id, sampled):
    """The scripted Jelly's heading and accel labels (learning.adapters.jelly.teacher) for imitation bootstrap."""
    c = next(c for c in env.team.members() if c.agent_id == agent_id)
    return teacher(c, env.enc)


def environment(horizon=60.0, arenas=None, scripted=False, **ignored):
    """The trainer also passes `opponent` and `muted`; Jellies have no frozen opponent and no message channel."""
    return JellyEnvironment(horizon=horizon, arenas=arenas, scripted=scripted)


# Scenario policy belongs to this adapter, not to the optimiser or run manager.
INITIAL_STAGE = 1
IMITATION_HEADS = ('heading', 'accel')
REWARDS = {'catch': CATCH_REWARD, 'team_catch_share': TEAM_CATCH_SHARE, 'progress_per_pixel': PROGRESS_REWARD,
           'stuck_per_decision': -STUCK_PENALTY}


def metadata(args):
    import dataclasses
    import config
    import enemy_kinds
    import level_config
    from creatures.jelly_team import MAX_SPEED, ACCEL_RATE, TURN_RATE
    from learning.adapters.practice_targets import TARGET_RADIUS, TARGET_SPEED_MIN, TARGET_SPEED_MAX
    opponent = Path(getattr(args, 'opponent', '') or '')
    return dict(task=SPEC.task, scenario_version=1, policy_spec=SPEC.metadata(), observation_version=SPEC.version,
                rewards=dict(REWARDS), reward_scope='individual', critic_context='focal_agent_first_v1',
                catch={'rule': 'body_contact', 'target_respawns': True, 'respawn_distance': RESPAWN_DISTANCE,
                       'team_share': TEAM_CATCH_SHARE},
                stuck={'window_frames': STUCK_WINDOW, 'distance_pixels': STUCK_DISTANCE,
                       'accelerating_above': STUCK_ACCEL, 'accelerating_throughout_window': True, 'scripted_counts_as_accelerating': True},
                practice_targets={'count': TARGET_COUNT, 'radius': TARGET_RADIUS, 'firing': False,
                                  'speed_range': [TARGET_SPEED_MIN, TARGET_SPEED_MAX],
                                  'start_distance': TARGET_START_DISTANCE},
                jelly={'max_speed': MAX_SPEED, 'accel_rate': ACCEL_RATE, 'turn_rate_radians': TURN_RATE,
                       'spacing': JELLY_SPACING, 'creature': dataclasses.asdict(enemy_kinds.kind('neural_jelly'))},
                promotion={'1': 'training_catches_per_minute_and_stuck_fraction_beat_scripted_holdout_baseline'},
                physics={name: dataclasses.asdict(getattr(config.SETTINGS, name)) for name in ('maze', 'obstacles')},
                arenas={str(n): level_config.load_level_config(n) for n in TRAIN_LEVELS+HOLDOUT_LEVELS},
                opponent_sha256=hashlib.sha256(opponent.read_bytes()).hexdigest() if opponent.is_file() else None,
                decision_frames=DECISION_FRAMES, horizon=args.horizon,
                train_levels=list(TRAIN_LEVELS), holdout_levels=list(HOLDOUT_LEVELS))


def training_cases(iteration, count, stage, bootstrap=False):
    cases = []
    for i in range(count):
        index = iteration*count+i
        cases.append(dict(level=TRAIN_LEVELS[index % len(TRAIN_LEVELS)],
                          seed=100+i if bootstrap else 300+index % 100, team_size=1, stage=stage))
    return cases


def validation_cases():
    return [dict(level=n, seed=s, team_size=1, stage=1) for n, s in ((13, 800), (17, 801))]


def evaluation_cases(stage=1):
    return [dict(level=n, seed=s, team_size=1, stage=stage) for n in HOLDOUT_LEVELS for s in (1000, 1001)]


def metrics(rows):
    seconds = sum(r['seconds'] for r in rows)
    jelly_seconds = sum(r['seconds']*r['team_size'] for r in rows)
    catches = sum(r['catches'] for r in rows)
    stuck = sum(r['stuck_seconds'] for r in rows)
    returns = [r.get('return', sum(r.get('agent_returns', {}).values())) for r in rows]
    return dict(episodes=len(rows), catches=catches, seconds=seconds, stuck_seconds=stuck,
                catches_per_minute=catches*60/max(seconds, 1e-9),
                stuck_fraction=stuck/max(jelly_seconds, 1e-9),
                catch_probability=sum(r['catches'] > 0 for r in rows)/max(1, len(rows)),
                mean_episode_return=float(np.mean(returns)) if returns else 0.)


def selection_score(summary):
    """Catch rate, discounted by the share of Jelly time spent stuck. Validation runs on the real cave arenas."""
    return summary['catches_per_minute']*(1-summary['stuck_fraction'])


_baselines = {}


def scripted_baseline(stage=1, horizon=60.0):
    """The scripted Jelly (Chase + Drift, no policy) on the held-out arenas; computed once per process."""
    key = (stage, horizon)
    if key not in _baselines:
        env = JellyEnvironment(horizon=horizon, scripted=True)
        rows = []
        try:
            for case in evaluation_cases(stage):
                case = dict(case)
                env.reset(case.pop('seed'), **case)
                while True:
                    result = env.step({})
                    if result.terminated or result.truncated:
                        break
                rows.append(dict(result.events, **case))
        finally:
            env.close()
        _baselines[key] = metrics(rows)
    return _baselines[key]


def promote(stage, summary, baseline=None):
    """Stage 1 -> 2 once catches per minute beat the scripted Jelly's held-out rate and the stuck share is lower."""
    if stage != 1 or not summary.get('episodes'):
        return stage
    baseline = baseline or scripted_baseline(stage)
    if (summary['catches_per_minute'] > baseline['catches_per_minute']
            and summary['stuck_fraction'] < baseline['stuck_fraction']):
        return 2
    return stage


def compare(a, b):
    values = np.array([x['catches']-y['catches'] for x, y in zip(a['episodes'], b['episodes'])], float)
    stuck = np.array([x['stuck_seconds']-y['stuck_seconds'] for x, y in zip(a['episodes'], b['episodes'])], float)
    if not len(values):
        return dict(mean_extra_catches=0., lower_95=0., upper_95=0., mean_extra_stuck_seconds=0.)
    samples = np.random.default_rng(0).choice(values, (2000, len(values)), replace=True).mean(axis=1)
    return dict(mean_extra_catches=float(values.mean()), lower_95=float(np.quantile(samples, .025)),
                upper_95=float(np.quantile(samples, .975)), mean_extra_stuck_seconds=float(stuck.mean()))
