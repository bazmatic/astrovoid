"""CPU gate for a source tree: python stage6_gate.py ROOT ROUND [--frames N]."""
import argparse
import dataclasses
import json
import os
import random
import statistics
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('root')
p.add_argument('round', type=int)
p.add_argument('--frames', type=int, default=600)
a = p.parse_args()
os.chdir(a.root)
sys.path.insert(0, a.root)
os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
import numpy as np
import pygame
import config
from game import Game
from experiments.harness import SyncWorker
from hunter.rule_params import RULES
from hunter import duel as duel_module
from hunter.neural.loader import load_neural_policy
from maze.config import MazeComplexity
from maze.generator import Maze
from utils.resource_path import resource_path
from scoring.system import ScoringSystem

now = [1000.0]
clock = lambda: now[0]
import creatures.traits.piloted as piloted
piloted.monotonic = clock
config.SETTINGS.game.hunterPilot = 'rules'
pygame.init()
screen = pygame.display.set_mode((1352, 878))
g = Game(screen)
g._rules_worker_factory = lambda: SyncWorker(RULES, clock)
summon = g._summon_hunter

def emit(kind, scenario, value, **details):
    print('BENCH ' + json.dumps(dict(round=a.round, tree=os.path.basename(a.root), kind=kind,
                                    scenario=scenario, ms=value, **details)), flush=True)

try:
    for mode in ('none', 'rules'):
        for level in (1, 8, 21, 24, 25, 40):
            random.seed(1)
            np.random.seed(1)
            now[0] = 1000.0
            g.level, g.state = level, config.STATE_PLAYING
            g.start_level()
            g.player_has_moved = True
            g.ship.game_started = True
            g.ship.is_shield_active = lambda: True
            def potential(*args, **kwargs):
                result = ScoringSystem.calculate_current_potential_score(g.scoring, *args, **kwargs)
                result.update(potential_score=1000, score_percentage=1)
                return result
            g.scoring.calculate_current_potential_score = potential
            g.maze.check_exit_reached = lambda *x, **kw: False
            if mode == 'rules':
                g.hunter_worker = SyncWorker(RULES, clock)
                summon(g.ship.get_pos())
                g.hunter_flight.controller.clock = clock
            g._summon_hunter = lambda near: None
            samples = []
            for frame in range(60 + a.frames):
                now[0] += 1 / config.FPS
                before = time.process_time()
                g.update(1)
                g.draw_game()
                if frame >= 60:
                    samples.append((time.process_time() - before) * 1000)
            emit('frame', f'{mode}/{level}', statistics.mean(samples), enemies=len(g.roster.all()))
            g._close_hunter()
            g._close_enemy_hunters()
    random.seed(1)
    maze = Maze(13, complexity=MazeComplexity.COMPLEX, grid_size=26)
    original = duel_module.duel_spawns
    duel_module.duel_spawns = lambda maze, player, sight: original(maze, player, sight, random.Random(1))
    arena = duel_module.build_duel(maze, g.ship, SyncWorker(RULES, clock), load_neural_policy(), 20, 120, 6)
    arena.sides[0].flight.controller.clock = clock
    before = time.process_time()
    for _ in range(a.frames):
        now[0] += 1 / config.FPS
        arena.update(1)
    emit('duel', 'rules-neural', (time.process_time() - before) * 1000 / a.frames,
         elapsed=arena.elapsed, result=dataclasses.asdict(arena.result) if arena.result else None)
    arena.close()
finally:
    g._close_hunter()
    g._close_enemy_hunters()
    pygame.quit()

from experiments.harness import run_episode, reset
from experiments.student import StudentSpec
for mode in ('rules', 'neural'):
    before = time.process_time()
    spec = StudentSpec(weights=resource_path('assets/neural/hunter.npz'), decision_frames=6) if mode == 'neural' else None
    result = run_episode(14, 1, horizon=5, student=spec)
    emit('lab', mode, (time.process_time() - before) * 1000, result=dataclasses.asdict(result))
    reset()
