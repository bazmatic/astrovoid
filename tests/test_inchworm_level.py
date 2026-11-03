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
    enc.step(330.)
    assert all(c.x > pos[0] for c, pos in zip(roster.alive(), positions))


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
