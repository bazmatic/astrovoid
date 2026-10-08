"""Shots knock chips off wall blocks, and a destroyed block bursts into rubble."""
import pygame

import config
from maze.config import MazeComplexity
from maze.generator import Maze

GRID = 10


def maze_with(*cells):
    """An empty maze with wall blocks added at the given grid cells."""
    maze = Maze(1, MazeComplexity.EMPTY, GRID)
    for x, y in cells:
        maze.grid[y][x] = 1
    maze.rebuild_walls()
    return maze


def face(maze, cell):
    return [w for w in maze.walls if w.cell == cell][0]


def impact_on(wall):
    return ((wall.start[0] + wall.end[0]) / 2, (wall.start[1] + wall.end[1]) / 2)


def painted_near(maze, point, reach=40):
    pygame.init()
    screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    maze.wall_debris.draw(screen)
    area = pygame.Rect(0, 0, 2 * reach, 2 * reach)
    area.center = (int(point[0]), int(point[1]))
    return pygame.mask.from_surface(screen.subsurface(area), 1).count()


def run_out(maze):
    for _ in range(600):
        maze.wall_debris.update(1.0)


class TestHit:
    def test_a_hit_knocks_chips_off_at_the_impact(self):
        maze = maze_with((4, 4))
        wall = face(maze, (4, 4))
        impact = impact_on(wall)
        maze.damage_wall(wall, impact)
        chips = maze.wall_debris.chips
        assert chips
        assert all(abs(chip.x - impact[0]) < 6 and abs(chip.y - impact[1]) < 6 for chip in chips)

    def test_chips_fly_apart(self):
        maze = maze_with((4, 4))
        wall = face(maze, (4, 4))
        maze.damage_wall(wall, impact_on(wall))
        before = [(chip.x, chip.y) for chip in maze.wall_debris.chips]
        maze.wall_debris.update(1.0)
        assert [(chip.x, chip.y) for chip in maze.wall_debris.chips] != before

    def test_the_struck_block_flashes(self):
        maze = maze_with((4, 4))
        wall = face(maze, (4, 4))
        maze.damage_wall(wall, impact_on(wall))
        assert [flash.rect for flash in maze.wall_debris.flashes] == [pygame.Rect(maze.converter.cell_rect(4, 4))]

    def test_a_hit_shows_on_screen(self):
        maze = maze_with((4, 4))
        wall = face(maze, (4, 4))
        impact = impact_on(wall)
        assert painted_near(maze, impact) == 0
        maze.damage_wall(wall, impact)
        assert painted_near(maze, impact) > 0

    def test_the_effect_fades_away(self):
        maze = maze_with((4, 4))
        wall = face(maze, (4, 4))
        impact = impact_on(wall)
        maze.damage_wall(wall, impact)
        run_out(maze)
        assert not maze.wall_debris.chips and not maze.wall_debris.flashes
        assert painted_near(maze, impact) == 0

    def test_a_wall_that_cannot_be_damaged_sheds_nothing(self):
        maze = maze_with()
        wall = face(maze, (0, 4))
        maze.damage_wall(wall, impact_on(wall))
        assert not maze.wall_debris.chips and not maze.wall_debris.flashes

    def test_damage_without_an_impact_point_still_works(self):
        maze = maze_with((4, 4))
        assert maze.damage_wall(face(maze, (4, 4))) is False
        assert maze.blocks[(4, 4)] == config.WALL_HIT_POINTS - 1


class TestDestruction:
    def test_a_destroyed_block_bursts_into_more_rubble_than_a_hit(self):
        maze = maze_with((4, 4), (6, 6))
        wall = face(maze, (6, 6))
        maze.damage_wall(wall, impact_on(wall))
        from_a_hit = len(maze.wall_debris.chips)
        run_out(maze)
        for _ in range(config.WALL_HIT_POINTS - 1):
            maze.damage_wall(face(maze, (4, 4)))
        run_out(maze)
        wall = face(maze, (4, 4))
        assert maze.damage_wall(wall, impact_on(wall)) is True
        assert len(maze.wall_debris.chips) > 2 * from_a_hit

    def test_rubble_comes_from_all_over_the_block(self):
        maze = maze_with((4, 4))
        left, top, width, height = maze.converter.cell_rect(4, 4)
        for _ in range(config.WALL_HIT_POINTS - 1):
            maze.damage_wall(face(maze, (4, 4)))
        run_out(maze)
        wall = face(maze, (4, 4))
        maze.damage_wall(wall, impact_on(wall))
        chips = maze.wall_debris.chips
        assert all(left <= chip.x <= left + width and top <= chip.y <= top + height for chip in chips)
        assert max(chip.x for chip in chips) - min(chip.x for chip in chips) > width / 2
        assert max(chip.y for chip in chips) - min(chip.y for chip in chips) > height / 2

    def test_a_destroyed_block_does_not_flash(self):
        maze = maze_with((4, 4))
        for _ in range(config.WALL_HIT_POINTS - 1):
            maze.damage_wall(face(maze, (4, 4)))
        run_out(maze)
        maze.damage_wall(face(maze, (4, 4)), impact_on(face(maze, (4, 4))))
        assert not maze.wall_debris.flashes
