"""Living weed in the game: off unless switched on, grown in every cave the player sees, never in training."""
import math
import random

import pygame

import config
import level_config
from experiments import harness
from flora import Flora, Plant, Spore
from maze.generator import Maze
from physics.obstacle_world import ObstacleWorld
from rendering.flora_renderer import draw_flora
from tests.test_fun_menu import to_fun
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture


def test_flora_is_off_by_default(game):
    game.start_level()
    assert game.maze.flora is None


def test_a_level_has_living_weed_when_switched_on(game):
    game.grows_flora = True
    game.start_level()
    assert game.maze.flora is not None and game.maze.flora.plants


def test_weed_grows_while_the_level_plays(game):
    game.grows_flora = True
    game.start_level()
    game.state = config.STATE_PLAYING
    plant = game.maze.flora.plants[0]
    age = plant.age
    game.update(1.0)   # the flora grows from the start, before the player moves
    assert plant.age > age


def test_new_level_gets_fresh_flora(game):
    game.grows_flora = True
    game.start_level()
    first = game.maze.flora
    game.start_level()
    assert game.maze.flora is not first and game.maze.flora.maze is game.maze


def test_the_battle_always_has_weed_that_grows(game):
    assert not game.grows_flora   # off everywhere else
    to_fun(game)
    key(game, pygame.K_DOWN)
    key(game, pygame.K_RETURN)
    plant = game.maze.flora.plants[0]
    age = plant.age
    game.update(1.0)
    assert plant.age > age
    game.draw()
    game.end_duel()


def test_training_switches_weed_off(monkeypatch):
    monkeypatch.setattr(config.FLORA, 'enabled', True)
    seen = []
    try:
        harness.run_episode(13, 0, horizon=0.1, trace=lambda seconds, g, hunter: seen.append(g.maze.flora))
    finally:
        harness.reset()
    assert seen and all(flora is None for flora in seen)


def test_painted_weed_is_skipped_only_with_flora(game):
    game.start_level()
    maze, screen = game.maze, pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    drawn = []
    maze.wall_renderer._draw_weeds = lambda *args: drawn.append(True)
    maze.draw(screen)
    assert drawn
    drawn.clear()
    maze.flora = Flora(maze, seed=1)
    maze.draw(screen)
    assert not drawn


def test_drawing_a_grown_plant_puts_green_by_the_rock():
    screen = pygame.Surface((80, 80))
    plant = Plant.new((40.0, 70.0), (0.0, -1.0), (0, 0), random.Random(1), config.FLORA)
    plant.age = plant.grow_end   # fully grown, before its first pod
    flora = type('Cave', (), {'plants': [plant], 'spores': []})()
    draw_flora(screen, flora, time_seconds=0.0)
    greens = [screen.get_at((x, y)) for x in range(30, 51) for y in range(55, 71)]
    assert any(c.g > 100 and c.g > c.r and c.g > c.b * 0.8 for c in greens)


def gated_cave(level=17):
    """A level's real cave with its gates, built the way Game.start_level builds it."""
    layout = level_config.get_level_layout(level)
    maze = Maze(level, complexity=level_config.get_maze_complexity(level),
                grid_size=level_config.get_maze_grid_size(level), layout=layout, seed=level_config.get_level_seed(level))
    maze.gate_segments = ObstacleWorld(maze, layout.gates).segments()
    maze.flora = Flora.seeded(maze, seed=1)
    return maze


def test_a_spore_crossing_a_gate_is_gone_and_roots_nothing():
    maze = gated_cave()
    gate = next(segment for segment in maze.gate_segments if segment.active)
    middle = ((gate.start[0] + gate.end[0]) / 2, (gate.start[1] + gate.end[1]) / 2)
    length = math.dist(gate.start, gate.end)
    normal = (-(gate.end[1] - gate.start[1]) / length, (gate.end[0] - gate.start[0]) / length)
    flora = maze.flora
    flora.plants = []
    flora.spores = [Spore(x=middle[0] + normal[0] * 3, y=middle[1] + normal[1] * 3,
                          vx=-normal[0] * 4, vy=-normal[1] * 4, age=0.0, life=1000.0)]
    flora.step(2.0)
    assert not flora.spores and not flora.plants
