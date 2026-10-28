"""Actual ship and creature physics in seeded team encounters, with a frozen neural opponent."""
from collections import Counter
from dataclasses import replace
import hashlib
import math
import random
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from learning.environment import Snapshot, Transition
from learning.adapters.wallcrawler import SPEC, CRITIC_SIZE, observe, critic, intention, DECISION_FRAMES

TRAIN_LEVELS = (11, 13, 14, 16, 17, 19, 21, 22, 27)
HOLDOUT_LEVELS = (15, 20, 23)
DEFAULT_OPPONENT = Path(__file__).resolve().parents[2] / 'assets/neural/hunter.npz'


class SilentSound:
    def __getattr__(self, name):
        return lambda *a, **kw: None


class PlayerView:
    """Supply the old senses' bookkeeping while all movement belongs to the actual player Ship."""
    def __init__(self, ship):
        self.ship = ship
        self.health = 3
        self.fire_remaining = 0.0
        self.fire_interval = 0.25
        self.burst_remaining = 0
        self._hit = None
    def __getattr__(self, name):
        return getattr(self.ship, name)


class FrozenPlayer:
    def __init__(self, path=DEFAULT_OPPONENT):
        from hunter.neural.policy import NeuralPolicy
        from hunter.senses import Senses
        from hunter.model import HunterSettings
        self.policy = NeuralPolicy.load(path)
        self.digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.senses = Senses(HunterSettings())
        self.state = self.policy.initial_state()
        self.controls = (1, False, False)
        self.frames = 0

    def frame(self, world):
        from game_handlers.fire_rate_calculator import calculate_fire_cooldown
        ship = world.ship
        view = self.view
        if self.frames % DECISION_FRAMES == 0:
            senses = self.senses.observe(view, world.maze, world.roster.alive(), world.projectiles,
                                         [], None, self.controls, self.frames/60)
            self.controls, self.state = self.policy.act(senses, self.state, greedy=True)
        turn, thrust, fire = self.controls
        ship.angle = (ship.angle+(turn-1)*ship.current_rotation_speed) % 360
        if thrust:
            ship.apply_thrust()
        view.fire_remaining = max(0, view.fire_remaining-1/60)
        if fire and view.fire_remaining <= 0:
            world.projectiles.extend(ship.fire() or [])
            view.fire_interval = calculate_fire_cooldown(ship)/1000
            view.fire_remaining = view.fire_interval
        ship.update(1)
        ship.check_wall_collision(world.maze.walls, world.maze.spatial_grid)
        self.frames += 1


class CrawlerEnvironment:
    spec = SPEC
    from learning.adapters import wallcrawler as adapter

    def __init__(self, opponent=DEFAULT_OPPONENT, horizon=60.0, muted=False, arenas=None, scripted=False):
        self.opponent_path, self.horizon, self.muted = str(opponent), horizon, muted
        self.arenas = arenas
        self.scripted = scripted
        self.world = None
        self.render_frames = None

    def reset(self, seed, level=11, team_size=2):
        import pygame
        import config
        import creatures
        import level_config
        from creatures.encounter import Encounter
        from creatures.wallcrawler_team import get_team
        from entities.ship import Ship
        from entities.command_recorder import CommandRecorder
        from game_handlers.enemy_roster import EnemyRoster
        from game_handlers.collision_handler import CollisionHandler
        from scoring.system import ScoringSystem
        from policies.ammo import UnlimitedAmmo
        from maze.generator import Maze
        from physics.obstacle_world import ObstacleWorld
        if not 2 <= team_size <= 6:
            raise ValueError('team size must be 2..6')
        self.close()
        random.seed(seed)
        rng = random.Random(seed)
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1352, 878))
        self._screen_settings = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1352, 878
        arena = self.arenas.get(str(level)) if self.arenas else level_config.load_level_config(level)
        from level_layout import parse_layout
        from maze.config import MazeComplexity
        grid_size = arena['maze']['grid_size']
        complexity = MazeComplexity[arena['maze']['complexity'].upper()]
        layout = parse_layout(arena['layout'], grid_size) if 'layout' in arena else None
        if layout is not None:
            layout = replace(layout, enemies=(), beacon=None)
        maze = Maze(level, complexity, grid_size,
                    layout=layout, seed=seed, curved=True)
        obstacles = ObstacleWorld(maze, layout.gates) if layout is not None and layout.gates else None
        maze.gate_segments = obstacles.segments() if obstacles else []
        positions = [maze.position_calculator.grid_center_to_screen(c, r)
                     for r in range(1, maze.grid_height-1) for c in range(1, maze.grid_width-1)
                     if not maze.grid[r][c]]
        rng.shuffle(positions)
        positions = [p for p in positions if maze.is_open(p, 11)]
        if len(positions) < team_size+1:
            raise ValueError('arena has insufficient clear starts')
        ship = Ship(positions.pop())
        ship.sound_manager = SilentSound()
        ship.ammo_policy = UnlimitedAmmo()
        ship.game_started = True
        ship.shield_active = False
        ship.shield_initial_timer = 0
        ship.angle = rng.uniform(0, 360)
        scoring = ScoringSystem()
        scoring.power_drain_enabled = False
        handler = CollisionHandler(SilentSound(), scoring, CommandRecorder())
        # Training never generates pickups or changes a real profile.
        handler.drop_pickup = lambda *a, **k: None
        self.world = SimpleNamespace(ship=ship, hunter=None, maze=maze, projectiles=[],
                                     roster=EnemyRoster(), scoring=scoring, sound_manager=SilentSound(),
                                     command_recorder=handler.command_recorder, collision_handler=handler,
                                     powerup_crystals=[], jev_beacon_allowed=lambda: False, combat_ruleset='legacy')
        chosen = []
        for i in range(team_size):
            valid = [p for p in positions if math.dist(p, ship.get_pos()) >= 180
                     and all(math.dist(p, q) >= 45 for q in chosen)]
            if not valid:
                raise ValueError('arena has insufficient separated crawler starts')
            # Prefer starts near a surface, while preserving seeded variation.
            from creatures.traits.wallcrawl import contact
            pool = valid[:min(80, len(valid))]
            pool.sort(key=lambda p: contact(maze, p)[3])
            pos = rng.choice(pool[:min(12, len(pool))])
            positions.remove(pos); chosen.append(pos)
            c = creatures.build('wallcrawler', pos, level)
            c.agent_id = i
            self.world.roster.add(c)
        self.enc = Encounter(self.world.roster, self.world)
        self.enc.ready()
        self.team = get_team(self.enc)
        self.team.external = True
        self.team._next_id = team_size
        self.player = FrozenPlayer(self.opponent_path)
        self.player.view = PlayerView(ship)
        self.frames = self.hits = self.shots = 0
        self.contributions = Counter()
        self._accepted = set()
        self.world.collision_handler.on_player_projectile_hit = self._hit
        self.obstacles = obstacles
        self.agent_ids = tuple(range(team_size))
        self.level, self.seed, self.team_size = level, seed, team_size
        self.action_trace = []
        return self.snapshot()

    def _hit(self, shot):
        owner = getattr(shot, 'actor_id', None)
        if owner in self.agent_ids and shot not in self._accepted:
            self._accepted.add(shot)
            self.hits += 1
            self.contributions[owner] += 1
            self.player.view._hit = (shot.vx, shot.vy)

    def snapshot(self):
        batch = {c.agent_id: observe(self.team, c, self.muted) for c in self.team.members()}
        self._sites = {i: v[2] for i, v in batch.items()}
        return Snapshot({i: v[0] for i, v in batch.items()}, {i: v[1] for i, v in batch.items()}, critic(self.team))

    def step(self, actions):
        if self.frames >= self.horizon*60 or not self.world.roster.alive():
            raise RuntimeError('step after episode ended')
        before_hits, before_shots = self.hits, self.shots
        if not self.scripted:
            self.team.commit({i: intention(a) for i, a in actions.items()}, self._sites)
        self.action_trace.append({str(i): list(a) for i, a in actions.items()})
        for _ in range(DECISION_FRAMES):
            self.player.frame(self.world)
            self.enc.step(1)
            self.world.roster.update_dying(1)
            if self.obstacles:
                self.obstacles.step(1/60, [self.world.ship]+self.world.roster.alive())
                self.world.maze.gate_segments = self.obstacles.segments()
            live = []
            for shot in self.world.projectiles:
                shot.update(1)
                if not shot.active:
                    continue
                if shot.check_wall_collision(self.world.maze.walls, self.world.maze.spatial_grid):
                    shot.active = False
                elif self.obstacles and self.obstacles.bullet_hit(shot):
                    shot.active = False
                elif shot.is_enemy:
                    if self.world.collision_handler.handle_projectile_ship_collision(shot, self.world.ship, self.world.scoring):
                        shot.active = False
                else:
                    self.enc.shoot(shot)
                if shot.active:
                    live.append(shot)
            self.world.projectiles = live
            self.frames += 1
            if self.render_frames is not None:
                self.render_frames(self)
            if not self.world.roster.alive() or self.frames >= self.horizon*60:
                break
        self.shots = sum(c.shots_fired for c in self.world.roster.all())
        self.team.advance()
        reward = self.hits-before_hits-0.01*(self.shots-before_shots)
        return Transition(self.snapshot(), reward, not bool(self.world.roster.alive()),
                          self.frames >= self.horizon*60,
                          {'hits': self.hits, 'shots': self.shots, 'seconds': self.frames/60,
                           'alive': len(self.world.roster.alive()), 'contributions': dict(self.contributions)})

    def close(self):
        if hasattr(self,'_screen_settings'):
            import config
            config.SCREEN_WIDTH,config.SCREEN_HEIGHT = self._screen_settings
            del self._screen_settings
        if self.world is not None:
            self.enc.close()
            self.world = None


def environment(**kwargs):
    return CrawlerEnvironment(**kwargs)

# Scenario policy belongs to this adapter, not to the optimiser or run manager.
INITIAL_STAGE = 2
IMITATION_HEADS = ('move', 'aim', 'fire')


def metadata(args):
    import dataclasses
    import config
    import enemy_kinds
    import level_config
    from creatures.traits.wallcrawl import LAUNCH_FRAMES
    return dict(task=SPEC.task, scenario_version=4, policy_spec=SPEC.metadata(),
                opponent_sha256=hashlib.sha256(Path(args.opponent).read_bytes()).hexdigest(),
                creatures={'wallcrawler': dataclasses.asdict(enemy_kinds.kind('wallcrawler'))},
                player=dataclasses.asdict(config.SETTINGS.ship),
                physics={name:dataclasses.asdict(getattr(config.SETTINGS,name))
                         for name in ('projectile','momentum','maze','obstacles')},
                arenas={str(n):level_config.load_level_config(n) for n in TRAIN_LEVELS+HOLDOUT_LEVELS},
                decision_frames=DECISION_FRAMES, radio_range=300, landing_range=300,
                landing_half_angle_degrees=45, flight_turn_degrees_per_second=180, ballistic_flight=True,
                magnetic_alignment=True, planned_launch_spin=True, launch_frames=LAUNCH_FRAMES,
                rewards={'team_hit':1.,'shot':-.01}, horizon=args.horizon,
                train_levels=list(TRAIN_LEVELS),holdout_levels=list(HOLDOUT_LEVELS),observation_version=SPEC.version)


def training_cases(iteration, count, stage, bootstrap=False):
    return [dict(level=TRAIN_LEVELS[(iteration*count+i)%len(TRAIN_LEVELS)],
                 seed=(100+i if bootstrap else 300+(iteration*count+i)%100),
                 team_size=stage) for i in range(count)]


def validation_cases():
    return [dict(level=13,seed=800,team_size=4),dict(level=17,seed=801,team_size=4)]


def evaluation_cases():
    return [dict(level=n,seed=s,team_size=k) for n in HOLDOUT_LEVELS for s in (1000,1001) for k in (2,4,6)]


def promote(stage, summary):
    return min(6,stage+2) if summary['hit_probability']>=.5 and summary['hits']/max(1,summary['episodes'])>=1 else stage


def selection_score(summary):
    return summary['hits_per_minute']


def metrics(rows):
    seconds=sum(r['seconds'] for r in rows)
    hits,shots=sum(r['hits'] for r in rows),sum(r['shots'] for r in rows)
    return dict(hits_per_minute=hits*60/max(seconds,1e-9),
                hit_probability=sum(r['hits']>0 for r in rows)/max(1,len(rows)),accuracy=hits/max(1,shots),
                survival=float(np.mean([r['alive']/r['team_size'] for r in rows])),
                hits_per_crawler=float(np.mean([r['hits']/r['team_size'] for r in rows])),
                hits=hits,shots=shots,episodes=len(rows))


def compare(a,b):
    values=np.array([x['hits']-y['hits'] for x,y in zip(a['episodes'],b['episodes'])],float)
    samples=np.random.default_rng(0).choice(values,(2000,len(values)),replace=True).mean(axis=1)
    return dict(mean_extra_hits=float(values.mean()),lower_95=float(np.quantile(samples,.025)),
                upper_95=float(np.quantile(samples,.975)))
