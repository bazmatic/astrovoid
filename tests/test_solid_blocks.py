"""Wall blocks are solid rock: filled in, walled only where they face open space, and destroyed whole."""
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
    maze.wall_renderer.draw(screen, maze.walls, animate=False, blocks=maze.block_fills)
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
