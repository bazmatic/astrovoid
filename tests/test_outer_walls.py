"""The maze's outer walls cannot be shot away, and no wall lets a shielded ship through."""
from unittest.mock import Mock

import config
from entities.ship import Ship
from maze.config import MazeComplexity
from maze.generator import Maze
from maze.wall_segment import WallSegment
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture

GRID = 10


def empty_maze():
    return Maze(1, MazeComplexity.EMPTY, GRID)


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
        assert all(w.active and w.hit_points == config.WALL_HIT_POINTS for w in maze.walls)

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
