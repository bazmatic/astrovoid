"""Wall blocks are solid rock: filled in, walled only where they face open space, and destroyed whole."""
import math

import pygame
import pytest

import config
from maze.config import MazeComplexity
from maze.generator import Maze
from rendering.wall_renderer import WallRenderer

GRID = 10


def maze_with(*cells):
    """An empty maze with wall blocks added at the given grid cells."""
    maze = Maze(1, MazeComplexity.EMPTY, GRID)
    for x, y in cells:
        maze.grid[y][x] = 1
    maze.rebuild_walls()
    return maze


def faces(maze, cell):
    return [w for w in maze.walls if w.cell == cell]


def destroy(maze, cell):
    for _ in range(config.WALL_HIT_POINTS):
        maze.damage_wall(faces(maze, cell)[0])


def render(maze):
    pygame.init()
    screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    maze.wall_renderer.draw(screen, maze.walls, animate=False, blocks=maze.block_fills, wounds=maze.block_wounds)
    return screen


def cell_centre(maze, cell):
    left, top, width, height = maze.converter.cell_rect(*cell)
    return (left + width // 2, top + height // 2)


class TestFaces:
    def test_a_lone_block_has_four_faces(self):
        maze = maze_with((4, 4))
        assert len(faces(maze, (4, 4))) == 4

    def test_blocks_side_by_side_have_no_wall_between_them(self):
        maze = maze_with((4, 4), (5, 4))
        assert len(faces(maze, (4, 4))) == 3
        assert len(faces(maze, (5, 4))) == 3
        left, top, width, height = maze.converter.cell_rect(5, 4)
        shared = {(left, top), (left, top + height)}
        for wall in maze.walls:
            ends = {(round(wall.start[0]), round(wall.start[1])), (round(wall.end[0]), round(wall.end[1]))}
            assert ends != shared

    def test_a_buried_block_has_no_faces(self):
        maze = maze_with(*[(x, y) for x in (3, 4, 5) for y in (3, 4, 5)])
        assert faces(maze, (4, 4)) == []
        assert (4, 4) in maze.blocks

    def test_every_wall_is_a_face_of_a_block(self):
        maze = Maze(5, MazeComplexity.NORMAL, GRID)
        assert maze.walls
        assert all(wall.cell in maze.blocks for wall in maze.walls)


class TestDestruction:
    def test_a_hit_on_any_face_wears_down_the_whole_block(self):
        maze = maze_with((4, 4))
        top, right, bottom, left = faces(maze, (4, 4))
        assert maze.damage_wall(top) is False
        assert maze.damage_wall(bottom) is False
        assert maze.blocks[(4, 4)] == config.WALL_HIT_POINTS - 2
        assert {w.hit_points for w in (top, right, bottom, left)} == {config.WALL_HIT_POINTS - 2}

    def test_a_block_goes_all_at_once(self):
        maze = maze_with((4, 4))
        block_faces = faces(maze, (4, 4))
        hits = [maze.damage_wall(block_faces[i % 4]) for i in range(config.WALL_HIT_POINTS)]
        assert hits == [False] * (config.WALL_HIT_POINTS - 1) + [True]
        assert (4, 4) not in maze.blocks
        assert maze.grid[4][4] == 0
        assert faces(maze, (4, 4)) == []
        assert not any(w.active for w in block_faces)
        centre = cell_centre(maze, (4, 4))
        assert not [w for w in maze.spatial_grid.get_nearby_walls(centre, maze.cell_size) if w.cell == (4, 4)]

    def test_destroying_a_block_exposes_its_neighbours_face(self):
        maze = maze_with((4, 4), (5, 4))
        generation = maze.wall_generation
        destroy(maze, (4, 4))
        assert len(faces(maze, (5, 4))) == 4
        assert maze.wall_generation == generation + 1
        # The new face stops things: it is in the collision index
        left, top, width, height = maze.converter.cell_rect(5, 4)
        nearby = maze.spatial_grid.get_walls_along_path((left - 20, top + height / 2), (left + 20, top + height / 2), 1)
        assert any(w.cell == (5, 4) and round(w.start[0]) == left == round(w.end[0]) for w in nearby)

    def test_an_exposed_face_carries_its_blocks_damage(self):
        maze = maze_with((4, 4), (5, 4))
        maze.damage_wall(faces(maze, (5, 4))[0])
        destroy(maze, (4, 4))
        assert {w.hit_points for w in faces(maze, (5, 4))} == {config.WALL_HIT_POINTS - 1}

    def test_the_outer_ring_stays_indestructible_once_exposed(self):
        maze = maze_with((1, 4))
        destroy(maze, (1, 4))
        rim = faces(maze, (0, 4))
        assert rim and not any(w.destructible for w in rim)
        for wall in rim:
            for _ in range(config.WALL_HIT_POINTS * 2):
                assert maze.damage_wall(wall) is False
        assert (0, 4) in maze.blocks

    def test_nothing_spawns_inside_a_block(self):
        maze = maze_with(*[(x, y) for x in range(3, 8) for y in range(3, 8)])
        for x, y in maze.get_valid_spawn_positions(40, min_distance=5):
            cell = (int((x - maze.offset_x) // maze.cell_size_x), int((y - maze.offset_y) // maze.cell_size_y))
            assert cell not in maze.blocks


class TestFill:
    def test_a_block_is_filled_with_rock(self):
        maze = maze_with((4, 4))
        screen = render(maze)
        left, top, width, height = maze.converter.cell_rect(4, 4)
        mask = pygame.mask.from_surface(screen, 1)
        assert all(mask.get_at((x, y)) for x in range(left, left + width) for y in range(top, top + height))

    def test_open_space_stays_empty(self):
        maze = maze_with((4, 4))
        screen = render(maze)
        for cell in ((3, 4), (5, 4), (4, 3), (4, 5)):
            assert screen.get_at(cell_centre(maze, cell))[3] == 0

    def test_a_hit_block_looks_cracked(self):
        maze = maze_with((4, 4))
        left, top, width, height = maze.converter.cell_rect(4, 4)
        inside = pygame.Rect(left, top, width, height).inflate(-20, -20)
        before = pygame.image.tostring(render(maze).subsurface(inside), "RGBA")
        maze.damage_wall(faces(maze, (4, 4))[0])
        assert pygame.image.tostring(render(maze).subsurface(inside), "RGBA") != before

    def test_a_block_darkens_with_every_hit(self):
        maze = maze_with((4, 4))
        left, top, width, height = maze.converter.cell_rect(4, 4)
        inside = pygame.Rect(left, top, width, height).inflate(-20, -20)
        brightness = []
        for _ in range(config.WALL_HIT_POINTS):
            brightness.append(sum(pygame.transform.average_color(render(maze), inside)[:3]))
            maze.damage_wall(faces(maze, (4, 4))[0])
        for lighter, darker in zip(brightness, brightness[1:]):
            assert darker < lighter * 0.95

    def test_bites_never_eat_into_a_neighbouring_block(self):
        cells = [(4, 4), (5, 3), (3, 5), (5, 5), (3, 3)]
        maze = maze_with(*cells)
        for _ in range(config.WALL_HIT_POINTS - 1):
            maze.damage_wall(faces(maze, (4, 4))[0])
        mask = pygame.mask.from_surface(render(maze), 1)
        for cell in cells:
            left, top, width, height = maze.converter.cell_rect(*cell)
            assert all(mask.get_at((x, y)) for x in range(left, left + width) for y in range(top, top + height))

    def test_a_destroyed_block_leaves_nothing_behind(self):
        maze = maze_with((4, 4))
        render(maze)
        destroy(maze, (4, 4))
        screen = render(maze)
        left, top, width, height = maze.converter.cell_rect(4, 4)
        margin = int(WallRenderer.MAX_REACH) + 3
        area = pygame.Rect(left, top, width, height).inflate(2 * margin, 2 * margin)
        assert pygame.mask.from_surface(screen.subsurface(area), 1).count() == 0

    def test_patched_repaint_matches_a_fresh_one(self):
        """Repainting just the changed area must leave no seams or leftovers."""
        cells = [(x, y) for x in range(3, 7) for y in range(3, 6)] + [(7, 6)]
        maze = maze_with(*cells)
        render(maze)
        maze.damage_wall(faces(maze, (3, 3))[0])
        destroy(maze, (6, 4))
        destroy(maze, (5, 4))
        maze.damage_wall(faces(maze, (4, 4))[0])
        patched = render(maze)
        assert maze.wall_renderer.repaint_count > 1

        maze.wall_renderer = WallRenderer()
        assert pygame.image.tostring(patched, "RGBA") == pygame.image.tostring(render(maze), "RGBA")


def shoot(maze, cell, side, along):
    """Hit one face of a block part of the way along it. Returns where the shot landed."""
    left, top, width, height = maze.converter.cell_rect(*cell)
    impact = {
        'top': (left + width * along, top),
        'bottom': (left + width * along, top + height),
        'left': (left, top + height * along),
        'right': (left + width, top + height * along),
    }[side]
    wall = min(faces(maze, cell), key=lambda w: abs((w.start[0] + w.end[0]) / 2 - {
        'top': left + width / 2, 'bottom': left + width / 2, 'left': left, 'right': left + width,
    }[side]) + abs((w.start[1] + w.end[1]) / 2 - {
        'top': top, 'bottom': top + height, 'left': top + height / 2, 'right': top + height / 2,
    }[side]))
    maze.damage_wall(wall, impact)
    return impact


def brightness(color):
    return sum(color[:3])


class TestWounds:
    """Damage shows where the shots landed, not just anywhere on the block."""

    CELL = (4, 4)

    def setup_method(self):
        self.maze = maze_with(self.CELL)
        self.rect = pygame.Rect(self.maze.converter.cell_rect(*self.CELL))
        self.intact = brightness(pygame.transform.average_color(render(self.maze), self.rect))

    def hollow_near(self, point, reach=None):
        """Pixels of the block near a point that have been broken out to near blackness."""
        reach = reach or min(self.rect.size) * 0.45
        screen = render(self.maze)
        return sum(
            1
            for x in range(self.rect.left, self.rect.right) for y in range(self.rect.top, self.rect.bottom)
            if (x - point[0]) ** 2 + (y - point[1]) ** 2 <= reach ** 2
            and brightness(screen.get_at((x, y))) < self.intact * 0.3
        )

    def crack_pixels(self):
        screen = render(self.maze)
        core = self.rect.inflate(-18, -18)
        return [
            (x, y) for x in range(core.left, core.right) for y in range(core.top, core.bottom)
            if tuple(screen.get_at((x, y))[:3]) == WallRenderer.CRACK_COLOR
        ]

    def test_the_maze_remembers_where_a_block_was_hit(self):
        impact = shoot(self.maze, self.CELL, 'top', 0.3)
        assert self.maze.block_wounds[tuple(self.rect)] == ((round(impact[0]), round(impact[1])),)

    def test_a_shot_breaks_a_chunk_out_where_it_landed(self):
        impact = shoot(self.maze, self.CELL, 'top', 0.3)
        assert self.hollow_near(impact) > 0.01 * self.rect.width * self.rect.height

    def test_the_rest_of_the_block_keeps_its_edge(self):
        shoot(self.maze, self.CELL, 'top', 0.3)
        for elsewhere in (self.rect.midbottom, self.rect.midleft, self.rect.midright, self.rect.bottomright):
            assert self.hollow_near(elsewhere, reach=min(self.rect.size) * 0.3) == 0

    def test_a_second_shot_in_the_same_place_deepens_the_wound(self):
        impact = shoot(self.maze, self.CELL, 'top', 0.5)
        once = self.hollow_near(impact)
        shoot(self.maze, self.CELL, 'top', 0.52)
        assert self.hollow_near(impact) > once * 1.3
        assert self.hollow_near(self.rect.midbottom, reach=min(self.rect.size) * 0.3) == 0

    def test_shots_in_different_places_leave_separate_wounds(self):
        first = shoot(self.maze, self.CELL, 'top', 0.3)
        second = shoot(self.maze, self.CELL, 'bottom', 0.7)
        assert self.hollow_near(first, reach=min(self.rect.size) * 0.3) > 0
        assert self.hollow_near(second, reach=min(self.rect.size) * 0.3) > 0

    def test_a_shot_at_a_corner_wounds_the_face_it_struck(self):
        """Not the neighbouring side, which may be buried in more rock."""
        maze = maze_with((4, 4), (4, 3))
        impact = shoot(maze, (4, 4), 'left', 0.0)
        mask = pygame.mask.from_surface(render(maze), 1)
        left, top, width, height = maze.converter.cell_rect(4, 3)
        assert all(mask.get_at((x, y)) for x in range(left, left + width) for y in range(top, top + height))
        assert impact[1] == pytest.approx(top + height)

    def test_cracks_run_from_the_wound(self):
        impact = shoot(self.maze, self.CELL, 'left', 0.5)
        cracks = self.crack_pixels()
        assert cracks
        nearest = min(math.hypot(x - impact[0], y - impact[1]) for x, y in cracks)
        assert nearest < min(self.rect.size) * 0.45
        # Nothing has cracked on the far side of the block
        assert all(x < self.rect.centerx + self.rect.width * 0.2 for x, _ in cracks)

    def test_rock_that_was_never_struck_does_not_crack(self):
        assert self.crack_pixels() == []

    def test_light_catches_the_floor_of_a_bite_in_the_top_but_not_the_bottom(self):
        """Light falls from the top left, so only broken faces turned that way are pale."""
        def pale_near(point):
            screen = render(self.maze)
            reach = min(self.rect.size) * 0.45
            return sum(
                1
                for x in range(self.rect.left, self.rect.right) for y in range(self.rect.top + 4, self.rect.bottom - 4)
                if (x - point[0]) ** 2 + (y - point[1]) ** 2 <= reach ** 2
                and brightness(screen.get_at((x, y))) > self.intact * 1.6
            )
        top = shoot(self.maze, self.CELL, 'top', 0.5)
        bottom = shoot(self.maze, self.CELL, 'bottom', 0.5)
        assert pale_near(top) > 1.5 * pale_near(bottom)
