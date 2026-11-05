"""The inchworm playtest starts with attached, moving creatures."""
import pytest

import config
import level_config
from creatures.encounter import Encounter
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from maze.config import MazeComplexity
from maze.generator import Maze
from tests.creature_parts import world
from tests.test_crawler_tunnel import route
from tests.test_level_arc import game  # shared isolated Game fixture


@pytest.mark.parametrize('screen_size', [(960, 640), (1352, 878), (1920, 1080)])
def test_playtest_inchworms_spawn_on_platforms_and_walk(monkeypatch, screen_size):
    monkeypatch.setattr(config, 'SCREEN_WIDTH', screen_size[0])
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', screen_size[1])
    layout = level_config.get_level_layout(33)
    assert layout is not None
    assert {k: v for k, v in layout.counts().items() if v} == {'inchworm': 4}
    assert route(layout, layout.walls | layout.strong_walls) is not None
    maze = Maze(20, MazeComplexity.EMPTY, 33, layout=layout, seed=133, curved=True)
    roster = EnemyRoster()
    SpawnManager(roster).spawn_from_layout(layout, maze, 33, None)
    enc = Encounter(roster, world(maze=maze))
    positions = [c.get_pos() for c in roster.alive()]
    enc.step(1.)
    assert all(c.worm_state == 'walking' and c.worm_front_grip for c in roster.alive())
    furthest = [0.]*len(positions)
    for _ in range(11):                 # they cross their platform, then turn back at its end: judge the way out
        enc.step(30.)
        furthest = [max(f, c.x-pos[0]) for f, c, pos in zip(furthest, roster.alive(), positions)]
    assert all(f > 20. for f in furthest)


def test_inchworm_playtest_runs_in_real_game_loop(game):
    game.level = 33
    game.start_level()
    game.state = config.STATE_PLAYING
    game.player_has_moved = True
    game.ship.game_started = True
    worms = list(game.roster.of_kind('inchworm'))
    assert len(worms) == 4
    positions = [c.get_pos() for c in worms]
    for _ in range(360):
        game.update(1.)
    assert all(c.active and c.x > pos[0]+10 for c, pos in zip(worms, positions))


def test_the_inchworm_level_crawls_with_worms_that_all_hold_on(game):
    game.level = 34
    game.start_level()
    game.state = config.STATE_PLAYING
    game.player_has_moved = True
    game.ship.game_started = True
    worms = list(game.roster.of_kind('inchworm'))
    assert len(worms) == 8 and len(list(game.roster.of_kind('wallcrawler'))) == 4
    for _ in range(360):
        game.update(1.)
    assert all(c.active and c.worm_resets == 0 for c in worms)        # every perch has room for its arch


def test_the_inchworm_levels_rock_passages_let_the_ship_through_without_blasting(monkeypatch):
    import math
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    layout = level_config.get_level_layout(34)
    maze = Maze(24, MazeComplexity.EMPTY, 34, layout=layout, seed=134, curved=True)
    position = lambda cell: maze.position_calculator.grid_center_to_screen(*cell)
    def clear_edge(a, b):
        a, b = position(a), position(b)
        steps = math.ceil(math.dist(a, b)/4)
        return all(maze.is_open((a[0]+(b[0]-a[0])*i/steps, a[1]+(b[1]-a[1])*i/steps), config.SHIP_SIZE+1)
                   for i in range(steps+1))
    assert route(layout, layout.walls | layout.strong_walls, clear_edge) is not None
    assert route(layout, layout.strong_walls) < route(layout, layout.walls | layout.strong_walls)   # blasting is a shortcut
