"""Strong walls: blocks a hand-made layout places that no shot can ever destroy, drawn as metal plate."""
import pygame
import pytest

import config
from editor.model import PALETTE, EditorModel
from level_layout import LayoutError, parse_layout, plank_cells
from maze.config import MazeComplexity
from maze.generator import Maze
from rendering.wall_renderer import WallRenderer

GRID = 9
STRONG = (5, 3)
ROCK = (3, 3)


def data(**changes):
    base = {'walls': [list(ROCK)], 'strong_walls': [list(STRONG)], 'start': [1, 1], 'exit': [7, 7]}
    base.update(changes)
    return base


def maze():
    return Maze(1, MazeComplexity.EMPTY, GRID, layout=parse_layout(data(), GRID))


def faces(m, cell):
    return [w for w in m.walls if w.cell == cell]


def render(m):
    pygame.init()
    screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    screen.fill((0, 0, 0))
    m.draw(screen)
    return screen


def inner(m, cell):
    """The middle of a block's screen area, clear of anything drawn along its edges."""
    left, top, width, height = m.converter.cell_rect(*cell)
    return pygame.Rect(left, top, width, height).inflate(-width // 2, -height // 2)


class TestTheLayout:
    def test_strong_walls_are_walls_in_the_grid(self):
        layout = parse_layout(data(), GRID)
        assert layout.strong_walls == frozenset({STRONG}) and layout.walls == frozenset({ROCK})
        grid = layout.grid()
        assert grid[STRONG[1]][STRONG[0]] == 1 and grid[ROCK[1]][ROCK[0]] == 1

    def test_strong_walls_round_trip_through_json(self):
        layout = parse_layout(data(), GRID)
        assert layout.to_json()['strong_walls'] == [list(STRONG)]
        assert parse_layout(layout.to_json(), GRID) == layout

    def test_a_layout_without_strong_walls_leaves_them_out_of_its_json(self):
        layout = parse_layout(data(strong_walls=[]), GRID)
        assert layout.strong_walls == frozenset() and 'strong_walls' not in layout.to_json()

    def test_a_cell_cannot_be_both_kinds_of_wall(self):
        with pytest.raises(LayoutError):
            parse_layout(data(strong_walls=[list(ROCK)]), GRID)

    @pytest.mark.parametrize('changes', [
        {'start': list(STRONG)},
        {'exit': list(STRONG)},
        {'beacon': list(STRONG)},
        {'enemies': [{'type': 'static', 'cell': list(STRONG)}]},
        {'gates': [{'cell': list(STRONG)}]},
        {'gates': [{'cell': [5, 4], 'angle': 90}]},             # its plank runs up into the strong wall
    ])
    def test_nothing_may_be_placed_on_a_strong_wall(self, changes):
        with pytest.raises(LayoutError):
            parse_layout(data(**changes), GRID)


class TestShootingAStrongWall:
    def test_its_faces_are_indestructible(self):
        m = maze()
        assert faces(m, STRONG) and not any(w.destructible for w in faces(m, STRONG))
        assert all(w.destructible for w in faces(m, ROCK))

    def test_no_number_of_shots_wears_it_down_or_marks_it(self):
        m = maze()
        wall = faces(m, STRONG)[0]
        for _ in range(config.WALL_HIT_POINTS * 3):
            assert m.damage_wall(wall, wall.start) is False
        assert m.blocks[STRONG] == config.WALL_HIT_POINTS
        assert STRONG not in m.wounds and m.grid[STRONG[1]][STRONG[0]] == 1
        assert all(w.active for w in faces(m, STRONG))

    def test_a_shot_strikes_sparks_but_no_rock(self):
        m = maze()
        wall = faces(m, STRONG)[0]
        m.damage_wall(wall, wall.start)
        assert m.wall_debris.chips
        assert all(chip.color == m.wall_debris.SPARK_COLOR for chip in m.wall_debris.chips)
        assert not m.wall_debris.flashes

    def test_the_rock_beside_it_still_breaks(self):
        m = maze()
        for _ in range(config.WALL_HIT_POINTS):
            m.damage_wall(faces(m, ROCK)[0])
        assert ROCK not in m.blocks


class TestHowItLooks:
    def test_a_strong_wall_is_drawn_as_metal_not_rock(self):
        m = maze()
        screen = render(m)
        steel = pygame.transform.average_color(screen, inner(m, STRONG))[:3]
        rock = pygame.transform.average_color(screen, inner(m, ROCK))[:3]
        distance = lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))
        assert distance(steel, WallRenderer.STEEL_COLOR) < distance(rock, WallRenderer.STEEL_COLOR)
        assert distance(steel, rock) > 30 ** 2

    def test_no_weed_grows_on_a_strong_wall(self):
        m = maze()
        render(m)
        left, top, width, height = m.converter.cell_rect(*STRONG)
        area = pygame.Rect(left, top, width, height).inflate(4, 4)
        assert not any(area.collidepoint(weed.base) for weed in m.wall_renderer.weeds)


class TestTheEditor:
    def model(self):
        return EditorModel(3, parse_layout(data(), GRID), maze_for=lambda level, layout: Maze(
            level, MazeComplexity.EMPTY, layout.grid_size, layout=layout))

    def at(self, m, cell, item):
        m.cursor = cell
        m.palette_index = PALETTE.index(item)

    def test_the_palette_offers_a_strong_wall_after_the_wall(self):
        assert PALETTE[:2] == ('wall', 'strong_wall')
        from rendering.level_editor import CHIPS, LABELS
        assert LABELS['strong_wall'] == 'Strong wall' and 'strong_wall' in CHIPS

    def test_a_strong_wall_loads_is_placed_and_removed(self):
        m = self.model()
        assert m.contents(STRONG) == 'strong_wall'
        self.at(m, (2, 5), 'strong_wall')
        assert m.place() and m.contents((2, 5)) == 'strong_wall'
        assert m.remove() and m.contents((2, 5)) is None

    def test_each_kind_of_wall_replaces_the_other(self):
        m = self.model()
        self.at(m, ROCK, 'strong_wall')
        assert m.place() and m.contents(ROCK) == 'strong_wall'
        self.at(m, ROCK, 'wall')
        assert m.place() and m.contents(ROCK) == 'wall'

    def test_nothing_else_goes_on_a_strong_wall(self):
        m = self.model()
        for item in ('static', 'start', 'beacon', 'gate'):
            self.at(m, STRONG, item)
            assert not m.place()

    def test_a_strong_wall_keeps_a_gate_from_turning_into_it(self):
        m = self.model()
        self.at(m, (4, 5), 'gate')
        assert m.place()
        under = sorted(plank_cells(m.gates[(4, 5)]) - {(4, 5)})[0]
        self.at(m, under, 'strong_wall')
        assert not m.place() and m.contents(under) is None

    def test_the_saved_layout_keeps_the_strong_walls(self):
        m = self.model()
        self.at(m, (2, 5), 'strong_wall')
        m.place()
        layout = m.to_layout()
        assert layout.strong_walls == frozenset({STRONG, (2, 5)}) and layout.walls == frozenset({ROCK})
