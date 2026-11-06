"""Living weed: plants grow from seeds on the rock, fruit pods that burst into drifting spores, and die of old age."""
import math
import random

import pygame

import config
from flora import Flora, Plant, Spore
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


def open_face(m, strong=False):
    """A long face of (strong, or breakable) rock away from the outer ring: its middle and the way out into water."""
    for wall in sorted(m.walls, key=lambda w: (w.start, w.end)):
        cell = wall.cell
        if (not wall.active or cell is None or on_perimeter(m, cell) or math.dist(wall.start, wall.end) < 10
                or (cell in m.strong_cells) != strong):
            continue
        middle = ((wall.start[0] + wall.end[0]) / 2, (wall.start[1] + wall.end[1]) / 2)
        length = math.dist(wall.start, wall.end)
        normal = (-(wall.end[1] - wall.start[1]) / length, (wall.end[0] - wall.start[0]) / length)
        for side in (1, -1):
            out = (normal[0] * side, normal[1] * side)
            if m.is_open((middle[0] + out[0] * 8, middle[1] + out[1] * 8), 3):
                return middle, out
    raise AssertionError('no open face')


def spore_heading_at(middle, out, distance=6.0, speed=1.0):
    return Spore(x=middle[0] + out[0] * distance, y=middle[1] + out[1] * distance,
                 vx=-out[0] * speed, vy=-out[1] * speed, age=0.0, life=1000.0)


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


def test_a_ripe_pod_bursts_into_spores():
    m = cave()
    flora = Flora.seeded(m, seed=3)
    plant = flora.plants[0]
    plant.age = plant.bursts[0] - 1.0
    flora.plants = [plant]
    flora.step(2.0)
    assert config.FLORA.sporesMin * plant.stalks <= len(flora.spores) <= config.FLORA.sporesMax * plant.stalks


def test_a_spore_that_touches_rock_becomes_a_seed():
    m = cave()
    flora = Flora(m, seed=3)
    flora.spores.append(spore_heading_at(*open_face(m)))
    for _ in range(60):
        flora.step(1.0)
    assert [p.stage for p in flora.plants] == ['seed'] and not flora.spores


def test_a_spore_does_not_root_beside_a_living_plant():
    m = cave()
    flora = Flora(m, seed=3)
    middle, out = open_face(m)
    neighbour = Plant.new((middle[0] + 0.5, middle[1] + 0.5), out, (0, 0), random.Random(1), config.FLORA)
    flora.plants.append(neighbour)
    flora.spores.append(spore_heading_at(middle, out))
    for _ in range(60):
        flora.step(1.0)
    assert flora.plants == [neighbour] and not flora.spores


def test_spore_does_not_root_on_a_strong_wall():
    m = strong_wall_maze()
    flora = Flora(m, seed=3)
    flora.spores.append(spore_heading_at(*open_face(m, strong=True)))
    for _ in range(60):
        flora.step(1.0)
    assert not flora.plants and not flora.spores


def test_spore_does_not_pass_through_rock_on_a_long_frame():
    m = cave()
    flora = Flora(m, seed=3)
    middle, out = open_face(m)
    flora.spores.append(spore_heading_at(middle, out, speed=20.0))
    flora.step(5.0)
    assert len(flora.plants) == 1 and math.dist(flora.plants[0].base, middle) < 3


def test_a_spore_that_finds_no_rock_fades_away():
    m = strong_wall_maze()
    flora = Flora(m, seed=3)
    flora.spores.append(Spore(x=m.exit.x, y=m.exit.y, vx=0.0, vy=0.0, age=0.0, life=config.FLORA.sporeFrames))
    flora.step(config.FLORA.sporeFrames / 2)
    assert flora.spores
    flora.step(config.FLORA.sporeFrames / 2 + 1)
    assert not flora.spores and not flora.plants


def test_spore_outside_the_maze_is_gone():
    m = cave()
    flora = Flora(m, seed=3)
    right = m.offset_x + m.grid_width * m.cell_size_x
    flora.spores.append(Spore(x=right + 50, y=m.offset_y + 50, vx=0.0, vy=0.0, age=0.0, life=1000.0))
    flora.step(1.0)
    assert not flora.spores


def test_the_eater_can_find_and_remove_a_spore():
    flora = Flora(cave(), seed=3)
    spore = Spore(x=300.0, y=300.0, vx=0.0, vy=0.0, age=0.0, life=1000.0)
    flora.spores.append(spore)
    assert flora.spores_near((305, 300), 10) == [spore]
    assert flora.spores_near((340, 300), 10) == []
    flora.remove(spore)
    assert flora.spores == []


def test_the_eater_can_find_and_remove_a_plant():
    flora = Flora.seeded(cave(), seed=3)
    plant = flora.plants[0]
    assert plant in flora.plants_near(plant.base, 1)
    flora.remove(plant)
    assert plant not in flora.plants


def test_weed_neither_dies_out_nor_overgrows():
    flora = Flora.seeded(cave(), seed=11)
    start = len(flora.plants)
    counts = []
    for _ in range(0, 5 * 60 * config.FPS, 2):
        flora.step(2.0)
        counts.append(len(flora.plants))
    assert min(counts[len(counts) // 2:]) >= start * 0.4
    assert max(counts) <= start * 2.5
