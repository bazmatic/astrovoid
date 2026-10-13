"""A duel between two pilots' hunters in an empty maze. The rules only: no drawing, no menus."""
import math
import time
from dataclasses import dataclass, replace
from typing import Optional

import config
from entities.hunter_ship import HunterShip
from hunter.controller import HunterController
from hunter.fire_control import find_firing_solution
from hunter.neural.controller import NeuralController
from hunter.perception import HunterPerception
from hunter.senses import Senses
from hunter.settings_for import hunter_settings_for
from hunter.spawn import nearest_hunter_spawn, resolve_hunter_spawn
from hunter.visibility import local_segments, visible_point
from utils.math_utils import get_angle_to_point

# The Vibes hunter's look: the rules hunter keeps the standard green, so the two are told apart at a glance.
VIBES_COLORS = {'COLOR': (255, 90, 200), 'FILL': (90, 25, 80), 'NOSE_COLOR': (255, 215, 240),
                'COCKPIT_COLOR': (60, 10, 50), 'ENGINE_COLOR': (160, 60, 120), 'ENGINE_LIT_COLOR': (255, 170, 230)}


@dataclass(frozen=True)
class DuelResult:
    winner: Optional[str]       # a side's name, or None for a draw
    reason: str                 # 'destroyed', 'draw' or 'timeout'


@dataclass
class Combatant:
    name: str
    hunter: HunterShip
    controller: object
    perception: object = None


class DuelArena:
    """Two hunters, each shown the other as an enemy, until one is destroyed or the time runs out."""

    def __init__(self, maze, combatants, timeout_seconds, clock=time.monotonic):
        if len(combatants) != 2:
            raise ValueError('a duel needs exactly two combatants')
        self.maze, self.sides, self.clock = maze, list(combatants), clock
        self.timeout_seconds = timeout_seconds
        self.elapsed = 0.0
        self.result = None
        self.shots = {side.name: [] for side in self.sides}
        for side in self.sides:
            neural = getattr(side.controller, 'kind', None) == 'neural'
            side.perception = Senses(side.hunter.settings) if neural else HunterPerception(side.hunter.settings)

    def _other(self, side):
        return self.sides[1] if side is self.sides[0] else self.sides[0]

    def update(self, dt):
        """Advance one frame (dt in frame units, 1.0 = 1/60 s). Does nothing once the duel has ended."""
        if self.result is not None:
            return
        self.elapsed += dt / config.FPS
        now = self.clock()
        for side in self.sides:
            self._fly(side, dt, now)
        first, second = self.sides
        if first.hunter.active and second.hunter.active:
            first.hunter.check_circle_collision(second.hunter.get_pos(), second.hunter.radius, second.hunter)
        self._move_shots(dt)
        self._judge()

    def _fly(self, side, dt, now):
        hunter, other = side.hunter, self._other(side)
        if not hunter.active:
            side.controller.close()
            return
        threats = self.shots[other.name]            # only the opponent's bullets are a danger to this pilot
        if getattr(side.controller, 'kind', None) == 'neural':
            action = side.controller.tick(lambda last_controls, t: side.perception.observe(
                hunter, self.maze, [other.hunter], threats, [], None, last_controls, t))
        else:
            action = side.controller.tick(lambda t, generation: side.perception.observe(
                hunter, self.maze, None, [other.hunter], threats, side.controller.action, t, generation))
        solution = None
        if action.track or action.fire or hunter.burst_remaining:
            solution = find_firing_solution(hunter, [other.hunter], self.maze, hunter.settings)
        shots = hunter.step(dt, action, solution)
        if shots:
            for shot in shots:
                shot.is_enemy = True                 # the pilots read a bullet's allegiance from this flag
            self.shots[side.name].extend(shots)
        hunter.check_wall_collision(self.maze.walls, self.maze.spatial_grid)

    def _move_shots(self, dt):
        for side in self.sides:
            victim = self._other(side).hunter
            alive = []
            for shot in self.shots[side.name]:
                shot.update(dt)
                if shot.active:
                    shot.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
                if shot.active and victim.active and shot.check_circle_collision(victim.get_pos(), victim.radius):
                    shot.active = False
                    victim.take_damage()
                if shot.active:
                    alive.append(shot)
            self.shots[side.name] = alive

    def _judge(self):
        down = [side for side in self.sides if not side.hunter.active]
        if len(down) == 2:
            self.result = DuelResult(None, 'draw')
        elif down:
            self.result = DuelResult(self._other(down[0]).name, 'destroyed')
        elif self.elapsed >= self.timeout_seconds:
            self.result = DuelResult(None, 'timeout')

    def close(self):
        for side in self.sides:
            side.controller.close()


def duel_spawns(maze, player, sight):
    """Two safe cells as far apart as they can be and still see each other: pilots only fight what they can see.

    The first is the safe cell nearest the top-left corner. The second is the farthest safe cell with a clear line of
    sight to it and within `sight` pixels (a rocky maze can hide the opposite corner).
    """
    first = nearest_hunter_spawn((0, 0), maze, player)
    walls = local_segments(first, [(w.start, w.end) for w in maze.walls if w.active], sight)
    cells = [(col, row) for row in range(maze.grid_height) for col in range(maze.grid_width)
             if not maze.grid[row][col]]
    centre = maze.position_calculator.grid_center_to_screen
    for cell in sorted(cells, key=lambda c: -math.dist(first, centre(*c))):
        if math.dist(first, centre(*cell)) > 0.9 * sight or not visible_point(first, centre(*cell), walls, sight):
            continue
        try:
            second = resolve_hunter_spawn({'spawn_cell': list(cell)}, maze, player)
        except ValueError:
            continue
        if math.dist(first, second) <= sight and visible_point(first, second, walls, sight):
            return first, second
    raise ValueError('the maze has no two clear spots that can see each other')


def build_duel(maze, player, rules_worker, policy, health, timeout_seconds, decision_frames):
    """The rules pilot's hunter against the neural pilot's, facing each other from opposite corners."""
    rules_settings = replace(hunter_settings_for('rules'), indestructible=False, health=health)
    vibes_settings = replace(hunter_settings_for('neural'), indestructible=False, health=health)
    sight = min(rules_settings.sensor_range(maze), vibes_settings.sensor_range(maze))
    rules_at, vibes_at = duel_spawns(maze, player, sight)
    rules, vibes = HunterShip(rules_at, rules_settings), HunterShip(vibes_at, vibes_settings)
    for name, value in VIBES_COLORS.items():
        setattr(vibes, name, value)                  # on this ship only: the class, and normal hunters, keep their look
    rules.angle = get_angle_to_point(rules_at, vibes_at)
    vibes.angle = get_angle_to_point(vibes_at, rules_at)
    return DuelArena(maze, [
        Combatant('rules', rules, HunterController(rules_worker, rules_settings)),
        Combatant('vibes', vibes, NeuralController(policy, decision_frames)),
    ], timeout_seconds)
