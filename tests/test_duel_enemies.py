import math
import random
from dataclasses import replace
from unittest.mock import Mock

import pygame
import pytest

from entities.hunter_ship import HunterShip
from entities.projectile import Projectile
from game_handlers.combat_targets import nearest_friendly
from hunter.duel_enemies import KEEP_CLEAR_OF_HUNTERS, DuelEnemies, _Target
from hunter.model import HunterSettings
from maze.config import MazeComplexity
from maze.generator import Maze

SETTINGS = replace(HunterSettings(), indestructible=False, health=5)


@pytest.fixture
def world():
    pygame.init()
    pygame.display.set_mode((320, 240))
    random.seed(13)
    maze = Maze(13, complexity=MazeComplexity.COMPLEX, grid_size=26)
    a = HunterShip(maze.position_calculator.grid_center_to_screen(3, 3), SETTINGS)
    b = HunterShip(maze.position_calculator.grid_center_to_screen(20, 18), SETTINGS)
    enemies = DuelEnemies(maze, Mock())
    return maze, a, b, enemies


def test_a_random_handful_of_ordinary_enemies_spawns_well_clear_of_both_hunters(world):
    maze, a, b, enemies = world
    enemies.spawn([a.get_pos(), b.get_pos()], rng=random.Random(1))
    manager = enemies.roster
    assert 3 <= len(manager.of_kind('static', 'patrol', 'aggressive')) + len(manager.of_kind('flocker')) <= 7
    assert not (manager.of_kind('replay') or manager.of_kind('split_boss') or manager.of_kind('mother_boss') or manager.of_kind('egg')
                or manager.of_kind('anemone') or manager.of_kind('flighthouse'))
    for foe in enemies.active():
        assert min(math.dist(foe.get_pos(), a.get_pos()), math.dist(foe.get_pos(), b.get_pos())) >= KEEP_CLEAR_OF_HUNTERS


def test_a_hunters_shot_kills_an_enemy(world):
    maze, a, b, enemies = world
    enemies.spawn([a.get_pos(), b.get_pos()], rng=random.Random(2))
    foe = enemies.active()[0]
    for _ in range(10):
        shot = Projectile(foe.get_pos(), 0.0, source='hunter')
        shot.is_enemy = True                                  # as the arena flags a hunter's shots
        if not foe.active:
            break
        assert enemies.shot_hits(shot)
    assert not foe.active and shot.is_enemy is True           # dead, and the flag is put back


def test_an_enemy_touching_a_hunter_hurts_it(world):
    maze, a, b, enemies = world
    enemies.spawn([a.get_pos(), b.get_pos()], rng=random.Random(3))
    foe = enemies.active()[0]
    a.x, a.y = foe.x, foe.y
    enemies.update(0.0, [a, b])
    assert a.health < SETTINGS.health and b.health == SETTINGS.health


def test_an_enemy_bullet_hurts_the_hunter_it_reaches_and_is_spent(world):
    maze, a, b, enemies = world
    bullet = Projectile(a.get_pos(), 0.0, is_enemy=True)
    enemies.bullets.append(bullet)
    enemies.move_bullets(0.0, [a, b])
    assert a.health == SETTINGS.health - 1 and enemies.bullets == []


def test_enemies_go_after_whichever_hunter_is_nearer(world):
    maze, a, b, enemies = world
    enemies.spawn([a.get_pos(), b.get_pos()], rng=random.Random(4))
    foe = enemies.active()[0]
    a.x, a.y = foe.x + 400, foe.y
    b.x, b.y = foe.x + 50, foe.y
    assert nearest_friendly(foe, _Target(a), b) is b
    a.x, a.y = foe.x + 30, foe.y
    assert nearest_friendly(foe, _Target(a), b) is not b          # now the first hunter is the nearer one


def test_creatures_in_the_duel_move_and_aim_at_the_nearer_hunter(world):
    maze, a, b, enemies = world
    enemies.spawn([a.get_pos(), b.get_pos()], rng=random.Random(5))
    crab = enemies.roster.of_kind('patrol')[0]
    start = crab.get_pos()
    b.x, b.y = crab.x + 40, crab.y
    for _ in range(30):
        enemies.update(1.0, [a, b])
    assert crab.get_pos() != start
    assert enemies.encounter.target_for(crab) == b.get_pos()
