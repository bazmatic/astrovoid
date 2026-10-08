"""The maze's outer walls wear down but cannot be shot away, and no wall lets a shielded ship through."""
from unittest.mock import Mock

import pygame

import config
from entities.ship import Ship
from maze.config import MazeComplexity
from maze.generator import Maze
from maze.wall_segment import WallSegment
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture

GRID = 10
RIM = (0, 4)  # A block in the outer ring


def empty_maze():
    return Maze(1, MazeComplexity.EMPTY, GRID)


def rim_face(maze):
    return [w for w in maze.walls if w.cell == RIM][0]


def render(maze):
    pygame.init()
    screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    maze.wall_renderer.draw(
        screen, maze.walls, animate=False, blocks=maze.block_fills, wounds=maze.block_wounds,
        unbreakable=maze.unbreakable_blocks
    )
    return screen


def brightness(surface, rect):
    return sum(pygame.transform.average_color(surface, rect)[:3])


def bite_sizes(maze):
    """Mouth width by depth of every bite broken out of the maze's blocks."""
    render(maze)
    return [bite.half * bite.depth for rect in maze.block_wounds for bite in maze.wall_renderer._bites(rect)]


def shoot_away(maze, wall):
    for _ in range(config.WALL_HIT_POINTS * 3):
        maze.damage_wall(wall)


class TestIndestructibleWalls:
    def test_a_wall_is_destructible_unless_told_otherwise(self):
        wall = WallSegment((0, 0), (10, 0), 1)
        assert wall.damage() is True
        assert not wall.active

    def test_an_indestructible_wall_takes_no_damage(self):
        wall = WallSegment((0, 0), (10, 0), 1, destructible=False)
        assert wall.damage() is False
        assert wall.active
        assert wall.hit_points == 1

    def test_every_perimeter_wall_survives_any_number_of_hits(self):
        maze = empty_maze()
        before = len(maze.walls)
        assert before  # An empty maze is nothing but its perimeter.
        for wall in list(maze.walls):
            shoot_away(maze, wall)
        assert len(maze.walls) == before
        assert all(w.active for w in maze.walls)
        assert all(maze.grid[y][x] == 1 for x, y in maze.blocks)

    def test_a_shot_wears_an_outer_block_down(self):
        maze = empty_maze()
        wall = rim_face(maze)
        assert maze.damage_wall(wall) is False
        assert maze.blocks[RIM] == wall.hit_points == config.WALL_HIT_POINTS - 1
        assert len(maze.wounds[RIM]) == 1

    def test_an_outer_block_is_never_worn_right_through(self):
        maze = empty_maze()
        wall = rim_face(maze)
        shoot_away(maze, wall)
        assert maze.blocks[RIM] == wall.hit_points == 1
        nearby = maze.spatial_grid.get_nearby_walls(wall.start, maze.cell_size)
        assert wall in nearby

    def test_an_outer_block_stops_breaking_up_once_it_is_worn_down(self):
        maze = empty_maze()
        shoot_away(maze, rim_face(maze))
        assert len(maze.wounds[RIM]) == config.WALL_HIT_POINTS - 1

    def test_a_worn_outer_block_looks_damaged(self):
        maze = empty_maze()
        fresh = pygame.image.tostring(render(maze), "RGBA")
        maze.damage_wall(rim_face(maze))
        assert pygame.image.tostring(render(maze), "RGBA") != fresh

    def test_a_hit_outer_block_is_stained_around_the_wound_rather_than_darkened_whole(self):
        maze = empty_maze()
        left, top, width, height = maze.converter.cell_rect(*RIM)
        far = pygame.Rect(left, top, width // 3, height)  # The outer side: the wound is on the inner face
        # Just inside the inner face, to one side of the bite in its middle
        reach = min(width, height) * 0.18
        near = pygame.Rect(left + width - reach, top + height * 0.12, reach - 6, height * 0.15)
        fresh = render(maze).copy()
        maze.damage_wall(rim_face(maze))
        worn = render(maze)
        assert pygame.image.tostring(worn.subsurface(far), "RGBA") == pygame.image.tostring(fresh.subsurface(far), "RGBA")
        assert brightness(worn, near) < 0.98 * brightness(fresh, near)

    def test_the_face_of_a_hit_outer_block_is_not_darkened_from_end_to_end(self):
        maze = empty_maze()
        left, top, width, height = maze.converter.cell_rect(*RIM)
        # The ridge standing proud of the inner face, well away from the wound in its middle
        ridge = pygame.Rect(left + width, top + height * 0.08, config.WALL_THICKNESS // 2, height * 0.2)
        fresh = render(maze).copy()
        maze.damage_wall(rim_face(maze))
        assert brightness(render(maze), ridge) > 0.95 * brightness(fresh, ridge)

    def test_bites_out_of_the_outer_wall_come_in_very_different_sizes(self):
        maze = empty_maze()
        for cell in list(maze.blocks):
            for wall in [w for w in maze.walls if w.cell == cell][:1]:
                maze.damage_wall(wall)
        assert len(bite_sizes(maze)) > 20
        assert max(bite_sizes(maze)) > 5 * min(bite_sizes(maze))

    def test_bites_out_of_inner_blocks_stay_much_of_a_size(self):
        maze = empty_maze()
        cells = [(x, y) for x in range(2, 8, 2) for y in range(2, 8, 2)]
        for x, y in cells:
            maze.grid[y][x] = 1
        maze.rebuild_walls()
        for cell in cells:
            maze.damage_wall([w for w in maze.walls if w.cell == cell][0])
        assert len(bite_sizes(maze)) == len(cells)
        assert max(bite_sizes(maze)) < 3 * min(bite_sizes(maze))

    def test_inner_walls_can_still_be_shot_away(self):
        maze = Maze(5, MazeComplexity.NORMAL, GRID)
        inner = [w for w in maze.walls if w.destructible]
        assert inner
        shoot_away(maze, inner[0])
        assert not inner[0].active
        assert inner[0] not in maze.walls


class TestShieldAndWalls:
    def test_a_shielded_ship_bounces_off_a_wall(self):
        ship = Ship((100.0, 100.0))
        ship.activate_shield()
        ship.prev_x, ship.prev_y = 100.0, 100.0
        ship.x, ship.vx = 140.0, 40.0
        wall = WallSegment((120, 0), (120, 200), 3)
        assert ship.check_wall_collision([wall])
        assert ship.x < 120
        assert ship.vx < 0

    def test_a_shielded_bounce_does_not_hurt_the_ship(self):
        ship = Ship((100.0, 100.0))
        ship.activate_shield()
        ship.on_wall_collision()
        assert not ship.damaged
        ship.deactivate_shield()
        ship.on_wall_collision()
        assert ship.damaged

    def _play(self, game):
        game.start_level()
        game.state = config.STATE_PLAYING
        game.game_frozen = game.game_over_active = False
        game.input_handler = Mock(key_mappings={})
        game.input_handler.process_controller_input.return_value = []
        game.input_handler.is_controller_shield_pressed.return_value = False
        game.input_handler.is_controller_fire_pressed.return_value = False
        maze = game.maze
        game.ship.x, game.ship.y = maze.position_calculator.grid_center_to_screen(1, GRID // 2)
        return maze.offset_x + maze.cell_size_x  # Inner face of the left outer wall.

    def _fly_left(self, game, frames=60):
        for _ in range(frames):
            game.ship.vx = -6.0
            game.update(1)

    def test_the_shield_does_not_carry_the_ship_out_of_the_maze(self, game):
        inner_face = self._play(game)
        assert game.ship.is_shield_active()
        self._fly_left(game)
        assert game.ship.is_shield_active()
        assert game.ship.x > inner_face
        assert game.scoring.wall_collisions == 0

    def test_an_unshielded_wall_hit_still_counts(self, game):
        inner_face = self._play(game)
        game.ship.shield_initial_timer = 0
        game.ship.deactivate_shield()
        self._fly_left(game)
        assert game.ship.x > inner_face
        assert game.scoring.wall_collisions > 0
