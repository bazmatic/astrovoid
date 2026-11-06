"""A battle between sides of creatures in a hand-built arena, nobody flying: Flockers vs Wallcrawlers. The rules only:
no drawing, no menus.

The match file (levels/fun/flockers_vs_wallcrawlers.json) names the sides. Each side has the creatures it starts with
(how many of each kind, at random in its `start` third of the arena: left, middle or right), the kinds the layout
places that are its own (`placed`), and the sides it `fights`. Fighting is one way: a side's creatures look for the
sides it fights (its world's additional targets), and its shots and bites hurt only them; anything else they pass by.
A side that is not a `contender` does not count to the win: the battle is won by the last contender with anything
alive, and drawn when none is left or the time runs out. The file also holds the arena (its layout, gates included),
the level whose strength the creatures have, and the seconds before it is called a draw. A side's `launch_interval`
sets how often its launchers (a Flighthouse) launch.

Each side runs in an Encounter of its own.
"""
import json
import random
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import config
import enemy_kinds
from creatures.encounter import Encounter
from entities.command_recorder import CommandRecorder
from game_handlers.collision_handler import CollisionHandler
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from level_layout import parse_layout
from maze import Maze
from physics.obstacle_world import ObstacleWorld
from scoring.system import ScoringSystem

MATCH_PATH = 'levels/fun/flockers_vs_wallcrawlers.json'
THIRDS = ('left', 'middle', 'right')


@dataclass(frozen=True)
class BattleResult:
    winner: Optional[str]       # a side's name, or None for a draw
    reason: str                 # 'destroyed', 'draw' or 'timeout'


def load_match(path=MATCH_PATH):
    """The match file's settings and arena; raises ValueError if it cannot be played."""
    from utils.resource_path import resource_path
    try:
        with open(resource_path(path)) as f:
            data = json.load(f)
        layout = parse_layout(data['layout'], int(data['maze']['grid_size']))
        sides = {name: _side(name, raw, data['sides']) for name, raw in data['sides'].items()}
        if sum(side.contender for side in sides.values()) < 2:
            raise ValueError('a battle needs two contender sides')
        return SimpleNamespace(seed=int(data.get('seed', 0)), level=int(data['level']), sides=sides,
                               layout=layout, timeout_seconds=float(data['timeout_seconds']))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f'{path}: {exc}') from exc


def _side(name, raw, sides):
    fights = tuple(raw.get('fights', ()))
    unknown = [other for other in fights if other not in sides or other == name]
    if unknown:
        raise ValueError(f'side {name!r} fights {unknown[0]!r}, which is not another side')
    if raw.get('start', 'left') not in THIRDS:
        raise ValueError(f'side {name!r} starts at {raw["start"]!r}, not one of {THIRDS}')
    interval = raw.get('launch_interval')
    return SimpleNamespace(creatures={kind: int(n) for kind, n in raw.get('creatures', {}).items()},
                           placed=tuple(raw.get('placed', ())), start=raw.get('start', 'left'), fights=fights,
                           contender=bool(raw.get('contender', True)),
                           launch_interval=float(interval) if interval is not None else None,
                           colour=tuple(raw.get('colour', (255, 255, 255))))


class _TeamWorld:
    """What one side's Encounter acts on: no ship and no hunter, the sides it fights as its targets, and its shots."""

    def __init__(self, battle, side, policies):
        self._battle, self._side = battle, side
        self.ship = self.hunter = None
        self.maze, self.scoring = battle.maze, battle.scoring
        self.sound_manager, self.command_recorder = battle.sound_manager, battle.recorder
        self.collision_handler = battle.collisions
        self.powerup_crystals = []
        self.projectiles = []
        self.flocker_policy, self.wallcrawler_policy = policies

    @property
    def additional_targets(self):
        return self._battle.targets(self._side)

    def jev_beacon_allowed(self):
        return False


class TeamBattle:
    def __init__(self, match, sound_manager, policies=(None, None), rng=None):
        """`policies` is the (flocker, wallcrawler) brains; None flies those on their scripted controls."""
        rng = rng or random.Random()
        self.sides = match.sides
        self.timeout_seconds = match.timeout_seconds
        self.elapsed = 0.0
        self.result = None
        self.maze = Maze(match.level, grid_size=match.layout.grid_size, layout=match.layout, seed=match.seed)
        self.maze.exit.active = False            # nobody is flying out: do not draw the exit portal
        self.obstacles = ObstacleWorld(self.maze, match.layout.gates) if match.layout.gates else None
        self.maze.gate_segments = self.obstacles.segments() if self.obstacles else []
        self.sound_manager = sound_manager
        self.scoring = ScoringSystem()          # the creature code reports to one; it is thrown away with the battle
        self.recorder = CommandRecorder()
        self.collisions = CollisionHandler(sound_manager, self.scoring, self.recorder)
        self.rosters, self.worlds, self.encounters = {}, {}, {}
        for name in self.sides:
            self.rosters[name] = EnemyRoster()
            self.worlds[name] = _TeamWorld(self, name, policies)
            self.encounters[name] = Encounter(self.rosters[name], self.worlds[name])
        self._spawn(match, rng)
        for encounter in self.encounters.values():
            encounter.ready()

    def _spawn(self, match, rng):
        """Each side at random open cells in its own third, with the layout's creatures of the kinds it places."""
        placed_cells = {cell for _, cell in match.layout.enemies}
        third = self.maze.grid_width / 3
        open_cells = [(col, row) for row in range(self.maze.grid_height) for col in range(self.maze.grid_width)
                      if not self.maze.grid[row][col] and (col, row) not in placed_cells]
        rng.shuffle(open_cells)
        for name, side in self.sides.items():
            zone = [cell for cell in open_cells if THIRDS[min(2, int(cell[0] // third))] == side.start]
            enemies = [(kind, cell) for kind, cell in match.layout.enemies if kind in side.placed]
            for kind, count in side.creatures.items():
                enemies += [(kind, zone.pop()) for _ in range(min(count, len(zone)))]
            SpawnManager(self.rosters[name]).spawn_from_layout(SimpleNamespace(enemies=enemies), self.maze,
                                                                 match.level, self.recorder)
            if side.launch_interval is not None:
                for creature in self.rosters[name].all():
                    creature.launch_interval = side.launch_interval

    def contenders(self):
        return [name for name, side in self.sides.items() if side.contender]

    def targets(self, name):
        """The live creatures of the sides this side fights."""
        return [c for other in self.sides[name].fights for c in self.alive(other)]

    def alive(self, name):
        return self.rosters[name].alive()

    def shots(self, name):
        return self.worlds[name].projectiles

    def update(self, dt):
        """Advance one frame; after the result, only the death animations continue."""
        for roster in self.rosters.values():
            roster.update_dying(dt)
        if self.result is not None:
            return
        self.elapsed += dt / config.FPS
        for encounter in self.encounters.values():
            encounter.step(dt)
        if self.obstacles:
            self._step_gates(dt)
        self._move_shots(dt)
        self._judge()

    def _step_gates(self, dt):
        """Let the gates swing and push back on whatever flies into them; anchored creatures jam them."""
        creatures = [c for roster in self.rosters.values() for c in roster.alive()]
        anchored = [c for c in creatures if enemy_kinds.kind(c.type).anchored]
        movers = [c for c in creatures if c not in anchored and hasattr(c, 'vx') and hasattr(c, 'vy')]
        self.obstacles.step(dt, movers, anchored)
        self.maze.gate_segments = self.obstacles.segments()

    def _move_shots(self, dt):
        for name, side in self.sides.items():
            alive = []
            for shot in self.shots(name):
                shot.update(dt)
                if shot.active:
                    shot.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
                if shot.active and self.obstacles:
                    self.obstacles.bullet_hit(shot, dt)
                if shot.active and any(self._hits(self.encounters[other], shot) for other in side.fights):
                    shot.active = False
                if shot.active:
                    alive.append(shot)
            self.shots(name)[:] = alive

    @staticmethod
    def _hits(encounter, shot):
        """Whether a shot struck one of the encounter's creatures. The creature code only lets friendly shots hit."""
        was_enemy, shot.is_enemy = shot.is_enemy, False
        try:
            return encounter.shoot(shot)
        finally:
            shot.is_enemy = was_enemy

    def _judge(self):
        standing = [name for name in self.contenders() if self.alive(name)]
        if not standing:
            self.result = BattleResult(None, 'draw')
        elif len(standing) == 1:
            self.result = BattleResult(standing[0], 'destroyed')
        elif self.elapsed >= self.timeout_seconds:
            self.result = BattleResult(None, 'timeout')

    def close(self):
        for encounter in self.encounters.values():
            encounter.close()
