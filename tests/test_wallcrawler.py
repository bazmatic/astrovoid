"""The wall gun's grip, knock-off window and return, through the real creature/combat paths."""
import math
from unittest.mock import Mock

import pygame
import pytest

import config
import creatures
import enemy_kinds
import level_config
from creatures.traits.wallcrawl import clear, contact
from editor.model import PALETTE
from entities.explosion import Blast
from entities.projectile import Projectile
from game_handlers.collision_handler import CollisionHandler
from game_handlers.spawn_manager import SpawnManager
from game_handlers.enemy_roster import EnemyRoster
from maze.wall_segment import WallSegment
from scoring.system import ScoringSystem
from tests.creature_parts import encounter, open_maze, target, world
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture


def scene(pos=(500, 312), walls=None):
    crawler = creatures.build('wallcrawler', pos)
    maze = open_maze(walls if walls is not None else [WallSegment((250, 300), (1000, 300), 4)])
    stand_in = world(maze=maze, ship=target((600, 500)))
    enc = encounter(crawler, world_=stand_in)
    enc.ready()
    return crawler, enc


def ready_gun(c):
    c.gun_cooldown = 0


def test_attached_gun_walks_with_its_feet_on_the_wall_and_fires():
    c, enc = scene()
    before = c.get_pos()
    ready_gun(c)
    enc.step(1)
    assert c.wall_state == 'attached'
    assert c.y == pytest.approx(312) and c.x != before[0]
    assert c.walk_phase > 0
    for _ in range(30):
        enc.step(1)
        if enc.world.projectiles:
            break
    assert enc.world.projectiles


@pytest.mark.parametrize('pos', [(600, 200), (1200, 500)])
def test_it_does_not_fire_through_its_wall_or_beyond_gun_range(pos):
    c, enc = scene()
    enc.world.ship = target(pos)
    ready_gun(c)
    enc.step(1)
    assert enc.world.projectiles == []


def test_gate_blocks_the_attached_guns_sight():
    c, enc = scene()
    enc.maze.gate_segments = [WallSegment((300, 400), (900, 400), 4)]
    ready_gun(c)
    enc.step(1)
    assert enc.world.projectiles == []


def test_bullet_dislodges_into_open_space_and_stops_firing_immediately():
    c, enc = scene(walls=[WallSegment((250,300),(1000,300),4),WallSegment((250,600),(1000,600),4)])
    c.controls.fire = True
    shot = Projectile(c.get_pos(), 270, source='player')  # incoming towards the wall
    enc.apply_hit(c, shot)
    assert c.active and c.hit_points == 3
    assert c.wall_state == 'stunned' and not c.controls.fire
    assert c.vy >= 2.8
    ready_gun(c)
    for _ in range(35):
        enc.step(1)
        assert c.wall_state == 'stunned' and not c.just_fired
    assert c.y > 312 and enc.world.projectiles == []
    for _ in range(150):
        enc.step(1)
        if c.wall_state == 'attached':
            break
        assert not c.just_fired
    assert c.wall_state == 'attached'
    for _ in range(30):
        enc.step(1)
        if enc.world.projectiles:
            break
    assert enc.world.projectiles  # only after attachment and turning towards the target


@pytest.mark.parametrize('damage', [0, 1])
def test_blast_dislodges_even_without_damage_and_keeps_normal_damage_accounting(damage):
    c, enc = scene()
    scoring = ScoringSystem()
    handler = CollisionHandler(Mock(), scoring, Mock())
    handler.handle_blast(Blast((c.x, c.y + 20), 100, damage=damage, wall_hits=0),
                         None, None, [c], enc.shoot)
    assert c.wall_state == 'stunned' and c.active
    assert c.hit_points == 4 - damage
    ready_gun(c)
    enc.step(1)
    assert not c.just_fired and c.y > 312


def test_second_airborne_hit_restarts_the_stunned_window():
    c, enc = scene()
    enc.apply_hit(c, Projectile(c.get_pos(), 0))
    enc.step(20)
    enc.apply_hit(c, Projectile(c.get_pos(), 0))
    assert c.wall_stun == 36 and c.hit_points == 2


def test_returns_to_nearest_wall_rather_than_original_wall():
    walls = [WallSegment((250, 300), (1000, 300), 4), WallSegment((250, 600), (1000, 600), 4)]
    c, enc = scene(walls=walls)
    c.x, c.y, c.wall_state = 500, 530, 'returning'
    ready_gun(c)
    for _ in range(100):
        enc.step(1)
    assert c.wall_state == 'attached' and c.y == pytest.approx(588)
    assert c.wall_normal == (0, -1)


def test_destroyed_wall_releases_it_without_inventing_launch_momentum():
    walls = [WallSegment((250, 300), (1000, 300), 4), WallSegment((250, 600), (1000, 600), 4)]
    c, enc = scene(walls=walls)
    walls[0].active = False
    ready_gun(c)
    enc.step(1)
    assert c.wall_state == 'returning' and not c.just_fired
    for _ in range(150):
        enc.step(1)
    assert c.wall_state == 'returning' and c.y == pytest.approx(312)
    assert c.vx == c.vy == 0


def test_no_walls_means_no_attachment_or_firing():
    c, enc = scene(walls=[])
    ready_gun(c)
    enc.step(100)
    assert c.wall_state == 'returning' and enc.world.projectiles == []


def test_a_fourth_hit_kills_it_using_the_standard_kill_path():
    c, enc = scene()
    shot = Projectile(c.get_pos(), 0, source='player')
    for _ in range(4):
        enc.apply_hit(c, shot)
    assert not c.active and c.is_dying
    enc.world.collision_handler.record_kill.assert_called_once_with(shot, c)


def test_it_can_be_placed_in_the_editor_and_campaign_and_generated_levels():
    assert 'wallcrawler' in PALETTE and 'wallcrawler' in enemy_kinds.kinds()
    assert level_config.get_level_wallcrawler_count(7) == 0
    assert level_config.get_level_wallcrawler_count(8) == 0
    assert level_config.get_level_wallcrawler_count(9) == 0
    assert level_config.get_level_wallcrawler_count(11) == 1
    assert level_config.get_level_wallcrawler_count(14) == 2
    assert level_config.get_level_wallcrawler_count(21) == 4
    assert level_config.get_level_wallcrawler_count(40) > 0
    from level_rules import EnemyCounts
    roster = EnemyRoster()
    manager = SpawnManager(roster)
    counts = EnemyCounts(0, 0, 0, 0, 0, 0, 0, 0)
    manager.spawn_all_enemies(40, [(500, 400), (700, 400)], None, counts, 0, 0, wallcrawler_count=2)
    assert len(roster.of_kind('wallcrawler')) == 2


@pytest.mark.parametrize('curved', [False, True])
def test_it_walks_on_real_rock_and_steel_without_entering_them(monkeypatch, curved):
    import random
    from level_layout import Layout
    from maze.config import MazeComplexity
    from maze.generator import Maze

    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    layout = Layout(12, frozenset({(5, y) for y in range(3, 8)}), (1, 1), (10, 10),
                    strong_walls=frozenset({(7, y) for y in range(3, 8)}))
    random.seed(41)
    maze = Maze(8, MazeComplexity.EMPTY, 12, layout=layout, seed=41, curved=curved)
    for cell in [(4, 5), (8, 5)]:
        c, enc = scene(maze.position_calculator.grid_center_to_screen(*cell))
        enc.world.maze = maze
        for _ in range(300):
            enc.step(1)
            assert clear(maze, c.get_pos(), c.radius)
        assert c.wall_state == 'attached' and c.walk_phase > 0
        assert contact(maze, c.get_pos())[3] == pytest.approx(c.radius + 2, abs=0.1)


def test_body_draws_attached_airborne_and_dying():
    c, enc = scene()
    screen = pygame.Surface((1352, 878))
    for state in ['attached', 'stunned', 'returning']:
        c.wall_state = state
        c.draw(screen)
    c.die()
    c.update_death(1)
    c.draw_death(screen)


@pytest.mark.parametrize('level', [11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 27])
def test_campaign_starts_the_expected_crawlers_and_they_find_a_wall(game, monkeypatch, level):
    from tests.test_layout_play import real_level_config
    from tests.test_rules_hunter import SilentWorker

    real_level_config(monkeypatch)
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    game._rules_worker_factory = SilentWorker
    game.level = level
    game.start_level()
    crawlers = game.roster.of_kind('wallcrawler')
    assert len(crawlers) == level_config.get_level_wallcrawler_count(level) > 0
    for _ in range(240):
        for c in crawlers:
            game.encounter.step_creature(c, 1)
            assert clear(game.maze, c.get_pos(), c.radius)
    assert any(c.wall_state == 'attached' and c.walk_phase > 0 for c in crawlers)
    assert all(c.wall_state in ('attached','returning','stunned') for c in crawlers)
    game.encounter.close()
