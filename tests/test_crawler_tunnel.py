"""Silkgrave's gauntlet remains long, traversable and exclusively inhabited by crawlers."""
from collections import deque
import math
import pytest

import config
import level_config
from maze.config import MazeComplexity
from maze.generator import Maze
from policies.exit import ExitState


def route(layout, blocked, clear_edge=lambda a,b: True):
    queue = deque([(layout.start, 0)])
    seen = {layout.start}
    while queue:
        cell, distance = queue.popleft()
        if cell == layout.exit:
            return distance
        x,y = cell
        for other in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if (0 < other[0] < layout.grid_size-1 and 0 < other[1] < layout.grid_size-1
                    and other not in blocked and other not in seen and clear_edge(cell,other)):
                seen.add(other)
                queue.append((other,distance+1))
    return None


def test_silkgrave_is_a_long_crawler_only_gauntlet_even_after_blasting_rock():
    data = level_config.load_level_config(32)
    layout = level_config.get_level_layout(32)
    assert layout is not None
    assert {kind for kind,cell in layout.enemies} == {'wallcrawler'}
    assert len(layout.enemies) == data['enemies']['wallcrawler'] == 20
    assert data['hunter'] is False and layout.beacon is None and not layout.gates
    assert data['ammo_policy']['type'] == 'unlimited'
    assert level_config.get_level_exit_policy(32).is_open(ExitState(0,{'wallcrawler':20}))
    assert route(layout,layout.walls|layout.strong_walls) >= 125
    assert route(layout,layout.strong_walls) >= 125


def test_silkgrave_curved_tunnels_have_a_ship_clearance_route_and_clear_spawns(monkeypatch):
    monkeypatch.setattr(config,'SCREEN_WIDTH',1352)
    monkeypatch.setattr(config,'SCREEN_HEIGHT',878)
    layout = level_config.get_level_layout(32)
    maze = Maze(32,MazeComplexity.EMPTY,32,layout=layout,seed=132,curved=True)
    position = lambda cell: maze.position_calculator.grid_center_to_screen(*cell)
    for _,cell in layout.enemies:
        assert maze.is_open(position(cell),11)
    def clear_edge(a,b):
        a,b = position(a),position(b)
        steps = math.ceil(math.dist(a,b)/4)
        return all(maze.is_open((a[0]+(b[0]-a[0])*i/steps,
                                 a[1]+(b[1]-a[1])*i/steps),config.SHIP_SIZE+1)
                   for i in range(steps+1))
    assert route(layout,layout.walls|layout.strong_walls,clear_edge) is not None


@pytest.mark.parametrize('screen_size', [(960,640),(1352,878),(1920,1080)])
def test_silkgrave_crawlers_are_attached_before_the_first_frame(monkeypatch,screen_size):
    from game_handlers.spawn_manager import SpawnManager
    from game_handlers.enemy_roster import EnemyRoster
    from creatures.encounter import Encounter
    from tests.creature_parts import world
    monkeypatch.setattr(config,'SCREEN_WIDTH',screen_size[0])
    monkeypatch.setattr(config,'SCREEN_HEIGHT',screen_size[1])
    layout = level_config.get_level_layout(32)
    maze = Maze(32,MazeComplexity.EMPTY,32,layout=layout,seed=132,curved=True)
    roster = EnemyRoster()
    SpawnManager(roster).spawn_from_layout(layout,maze,32,None)
    enc = Encounter(roster,world(maze=maze,roster=roster))
    enc.ready()
    floating = [c.get_pos() for c in roster.alive() if c.wall_state != 'attached']
    assert not floating, f'{len(floating)} crawlers begin floating'
