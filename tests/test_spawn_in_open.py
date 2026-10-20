"""Enemies never appear inside walls: not at level start, and not when hatched or split off mid-level."""
import random

import config
from entities.command_recorder import CommandRecorder
from entities.egg import Egg
from entities.mother_boss import MotherBoss
from game_handlers.collision_handler import CollisionHandler
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from level_rules import EnemyCounts
from maze.config import MazeComplexity
from maze.generator import Maze

GRID = 10


def walled_maze():
    """An empty maze with a solid wall of blocks down column 5, rows 1-8."""
    maze = Maze(1, MazeComplexity.EMPTY, GRID)
    for y in range(1, GRID - 1):
        maze.grid[y][5] = 1
    maze.rebuild_walls()
    return maze


def beside_wall(maze):
    """A point in the open cell just left of the wall, 20px from it: anything spawned nearby could land in it."""
    x, y = maze.position_calculator.grid_center_to_screen(4, 5)
    return (x + maze.cell_size_x / 2 - 20, y)


def test_is_open_rejects_blocks_walls_and_outside():
    maze = walled_maze()
    assert not maze.is_open(maze.position_calculator.grid_center_to_screen(5, 5), 1)
    assert not maze.is_open(beside_wall(maze), 25)
    assert maze.is_open(beside_wall(maze), 1)
    assert not maze.is_open((maze.offset_x - 50, maze.offset_y - 50), 1)


def test_hatched_babies_are_never_inside_a_wall():
    maze = walled_maze()
    random.seed(1)
    babies = []
    for _ in range(200):
        Egg(beside_wall(maze)).pop(CommandRecorder(), babies, maze)
    assert babies
    assert all(maze.is_open(baby.get_pos(), config.BABY_SIZE) for baby in babies)


def test_boss_children_are_never_inside_a_wall():
    maze = walled_maze()
    handler = CollisionHandler(None, None, CommandRecorder())
    random.seed(2)
    children = []
    for _ in range(200):
        handler._spawn_split_boss_children(beside_wall(maze), (1.0, 0.0), children, [], False, maze)
    assert all(maze.is_open(child.get_pos(), config.BABY_SIZE) for child in children)


def test_laid_eggs_have_room_to_grow():
    maze = walled_maze()
    random.seed(3)
    eggs = []
    for _ in range(100):
        boss = MotherBoss(maze.position_calculator.grid_center_to_screen(2, 5), CommandRecorder())
        boss.egg_lay_cooldown = 0
        boss.lay_egg(eggs, maze)
    assert all(maze.is_open(egg.get_pos(), config.EGG_MAX_SIZE) for egg in eggs)


def test_big_enemies_take_the_positions_with_room_for_them():
    maze = walled_maze()
    cramped = beside_wall(maze)
    roomy = maze.position_calculator.grid_center_to_screen(2, 5)
    boss_radius = config.REPLAY_ENEMY_SIZE * config.MOTHER_BOSS_SIZE_MULTIPLIER
    assert maze.is_open(roomy, boss_radius) and not maze.is_open(cramped, boss_radius)
    roster = EnemyRoster()
    counts = EnemyCounts(total=0, static=0, patrol=0, aggressive=0, replay=0, flocker=0, flighthouse=0, egg=0)
    SpawnManager(roster).spawn_all_enemies(
        1, [cramped, roomy], CommandRecorder(), counts, 0, 1, maze=maze)
    assert roster.of_kind('mother_boss')[0].get_pos() == roomy
