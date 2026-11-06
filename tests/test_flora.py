"""Living weed: plants grow from seeds on the rock, fruit pods that burst into drifting spores, and die of old age."""
import math
import random

import pygame

import config
from flora import Flora, Plant
from level_layout import parse_layout
from maze.config import MazeComplexity
from maze.generator import Maze
from utils import circle_line_collision

STRONG = (5, 3)


def cave():
    return Maze(1, complexity=MazeComplexity.COMPLEX, grid_size=18, seed=125, curved=True)


def strong_wall_maze():
    layout = {'walls': [[3, 3]], 'strong_walls': [list(STRONG)], 'start': [1, 1], 'exit': [7, 7]}
    return Maze(1, MazeComplexity.EMPTY, 9, layout=parse_layout(layout, 9))


def on_perimeter(m, cell):
    return m.converter.on_perimeter(m.grid, *cell)


def destroy_block(m, cell):
    while cell in m.blocks:
        m.damage_wall(next(w for w in m.walls if w.active and w.cell == cell), damage=config.WALL_HIT_POINTS)


def on_its_rock(m, plant):
    return any(w.active and w.cell == plant.cell and circle_line_collision(plant.base, 3, w.start, w.end)
               for w in m.spatial_grid.get_nearby_walls(plant.base, 3))


def new_plant(seed):
    return Plant.new((0.0, 0.0), (0.0, -1.0), (1, 1), random.Random(seed), config.FLORA)


def test_a_seed_grows_fruits_withers_and_dies():
    plant = new_plant(1)
    stages = []
    while not plant.dead:
        plant.advance(1.0)
        if not plant.dead and (not stages or stages[-1] != plant.stage):
            stages.append(plant.stage)
    assert stages == ['seed', 'growing', 'fruiting', 'withering']


def test_every_fruiting_bursts_each_stalk_once():
    plant = new_plant(2)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(1.0)
    assert bursts == plant.fruitings * plant.stalks


def test_a_long_step_still_bursts_every_pod():
    plant = new_plant(3)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(500.0)
    assert bursts == plant.fruitings * plant.stalks


def test_a_new_cave_starts_with_plants_at_every_stage():
    flora = Flora.seeded(cave(), seed=7)
    assert len(flora.plants) > 20
    assert {p.stage for p in flora.plants} == {'seed', 'growing', 'fruiting', 'withering'}


def test_plants_grow_out_of_rock_into_open_water():
    m = cave()
    for plant in Flora.seeded(m, seed=7).plants:
        assert on_its_rock(m, plant)
        tip = (plant.base[0] + plant.direction[0] * 4, plant.base[1] + plant.direction[1] * 4)
        assert m.is_open(tip, 1)


def test_nothing_grows_on_a_strong_wall():
    m = strong_wall_maze()
    area = pygame.Rect(m.converter.cell_rect(*STRONG)).inflate(4, 4)
    plants = Flora.seeded(m, seed=1).plants
    assert plants and not any(area.collidepoint(p.base) for p in plants)


def test_nothing_grows_beside_the_ship_start():
    m = cave()
    assert all(math.dist(p.base, m.start_pos) >= config.FLORA.startClear for p in Flora.seeded(m, seed=7).plants)


def test_plant_goes_with_its_wall():
    m = cave()
    flora = Flora.seeded(m, seed=7)
    plant = next(p for p in flora.plants if not on_perimeter(m, p.cell))
    destroy_block(m, plant.cell)
    flora.step(1.0)
    assert plant not in flora.plants


def test_plant_goes_when_its_rock_reforms_away():
    m = cave()
    flora = Flora.seeded(m, seed=7)
    for plant in list(flora.plants)[:6]:
        x, y = plant.cell
        neighbours = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        for cell in neighbours:
            if cell in m.blocks and not on_perimeter(m, cell):
                destroy_block(m, cell)
                break
    flora.step(1.0)
    assert all(on_its_rock(m, p) for p in flora.plants)


def test_the_same_seed_grows_the_same_flora():
    m = cave()
    first, second = Flora.seeded(m, seed=7), Flora.seeded(m, seed=7)
    assert [p.base for p in first.plants] == [p.base for p in second.plants]
