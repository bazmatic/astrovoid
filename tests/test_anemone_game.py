"""Anemones are spawned, updated, shot and drawn by the game like any other enemy."""
import math
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

import config
import creatures
import enemy_kinds
import level_rules
from creatures.traits.combat import flinch
from entities.anemone import AnemoneBody
from entities.command_recorder import CommandRecorder
from entities.projectile import Projectile
from entities.ship import Ship
from game_handlers.collision_handler import CollisionHandler
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from level_rules import EnemyCounts
from tests.creature_parts import encounter, world

POS = (400.0, 300.0)
TRAITS = dict(enemy_kinds.kind('anemone').traits)
FLING_SPEED = TRAITS['flingsShip']['speed']
HIT_POINTS = TRAITS['takesHits']['hitPoints']


def open_maze():
    return SimpleNamespace(cell_size_x=40.0, cell_size_y=40.0, walls=[], spatial_grid=None,
                           is_open=lambda pos, radius: True)


def anemone_at(pos=POS):
    return creatures.build('anemone', pos)


def counts(anemone):
    return EnemyCounts(total=0, static=0, patrol=0, aggressive=0, replay=0, flocker=0,
                       flighthouse=0, egg=0, anemone=anemone)


def spawn(anemone_count, positions):
    manager = EnemyRoster()
    SpawnManager(manager).spawn_all_enemies(1, positions, CommandRecorder(), counts(anemone_count), 0, 0)
    return manager


def level_with(handler, *anemones, crystals=None):
    """An Encounter over these anemones, whose kills go through a real collision handler."""
    stand_in = world(collision_handler=handler, scoring=handler.scoring, sound_manager=handler.sound_manager,
                     maze=open_maze(), powerup_crystals=crystals if crystals is not None else [])
    enc = encounter(*anemones, world_=stand_in)
    enc.ready()
    return enc


def shoot(enc):
    projectile = Projectile(POS, 0.0)
    projectile.source = 'player'
    return enc.shoot(projectile)


class TestSpawning:
    def test_spawns_the_requested_number(self):
        manager = spawn(2, [(100.0, 100.0), (200.0, 200.0), (300.0, 300.0)])
        assert len(manager.of_kind('anemone')) == 2
        assert all(isinstance(a.body, AnemoneBody) for a in manager.of_kind('anemone'))

    def test_spawns_only_as_many_as_fit(self):
        assert len(spawn(3, [(100.0, 100.0)]).of_kind('anemone')) == 1
        assert spawn(3, []).of_kind('anemone') == []

    def test_none_spawn_where_they_could_reach_the_players_start(self):
        manager = EnemyRoster()
        positions = [(100.0, 100.0), (150.0, 100.0), (400.0, 100.0), (500.0, 100.0)]
        SpawnManager(manager).spawn_all_enemies(
            1, positions, CommandRecorder(), counts(2), 0, 0, anemone_keep_clear=((90.0, 100.0), 200.0))
        assert [a.get_pos() for a in manager.of_kind('anemone')] == [(400.0, 100.0), (500.0, 100.0)]

    def test_fewer_spawn_when_too_few_places_are_clear_of_the_start(self):
        manager = EnemyRoster()
        SpawnManager(manager).spawn_all_enemies(
            1, [(100.0, 100.0), (400.0, 100.0)], CommandRecorder(), counts(2), 0, 0,
            anemone_keep_clear=((90.0, 100.0), 200.0))
        assert [a.get_pos() for a in manager.of_kind('anemone')] == [(400.0, 100.0)]

    def test_none_requested_none_spawned(self):
        assert spawn(0, [(100.0, 100.0)]).of_kind('anemone') == []


class TestEntityManager:
    def test_anemones_count_as_enemies(self):
        manager = EnemyRoster()
        alive, dead = anemone_at(), anemone_at((10.0, 10.0))
        manager.extend([alive, dead])
        dead.active = False
        assert list(manager.alive()) == [alive]
        assert set(manager.all()) == {alive, dead}
        assert POS in manager.positions()
        manager.clear()
        assert manager.of_kind('anemone') == []


class TestUpdating:
    def make(self, distance, *positions, shield=False):
        ship = Ship((POS[0] + distance, POS[1]))
        if shield:
            ship.activate_shield()
        else:
            ship.deactivate_shield()
        anemones = [anemone_at(pos) for pos in (positions or (POS,))]
        stand_in = world(ship=ship, maze=open_maze())
        return anemones, ship, stand_in.scoring, encounter(*anemones, world_=stand_in)

    def test_opposing_anemones_cancel_out(self):
        (left, right), ship, _, enc = self.make(0.0, (POS[0] - 60.0, POS[1]), (POS[0] + 60.0, POS[1]))
        enc.step(1.0)
        assert (ship.vx, ship.vy) == pytest.approx((0.0, 0.0))
        assert left.pull_fraction > 0 and right.pull_fraction > 0

    def test_fling_from_dead_centre_still_throws_the_ship_clear(self):
        [anemone], ship, _, enc = self.make(0.0)
        enc.step(1.0)
        assert math.hypot(ship.vx, ship.vy) == pytest.approx(FLING_SPEED)
        assert math.hypot(ship.x - POS[0], ship.y - POS[1]) > anemone.radius + ship.radius
        assert all(math.isfinite(v) for v in (ship.x, ship.y, ship.vx, ship.vy))

    def test_shield_stops_both_the_pull_and_the_sting(self):
        _, ship, scoring, enc = self.make(10.0, shield=True)
        enc.step(1.0)
        assert (ship.vx, ship.vy) == (0.0, 0.0)
        assert scoring.record_enemy_collision.call_count == 0

    def test_dead_anemones_are_skipped(self):
        [anemone], ship, scoring, enc = self.make(10.0)
        anemone.die()
        enc.step(1.0)
        assert (ship.vx, ship.vy) == (0.0, 0.0)
        assert scoring.record_enemy_collision.call_count == 0


class TestBeingShot:
    def test_a_hit_uses_the_shot_and_makes_it_flinch(self):
        handler, anemone = CollisionHandler(Mock(), Mock(), CommandRecorder()), anemone_at()
        assert shoot(level_with(handler, anemone))
        assert anemone.active
        assert anemone.flinch_timer == TRAITS['flinchesWhenHit']['frames']
        assert handler.sound_manager.play_enemy_destroy.call_count == 0

    def test_a_flinch_does_not_cut_a_longer_one(self):
        handler, anemone = CollisionHandler(Mock(), Mock(), CommandRecorder()), anemone_at()
        enc = level_with(handler, anemone)
        flinch(anemone, 500, enc)
        shoot(enc)
        assert anemone.flinch_timer == 500

    def test_killed_and_credited_on_the_last_hit_only(self, monkeypatch):
        monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
        handler, anemone, crystals = CollisionHandler(Mock(), Mock(), CommandRecorder()), anemone_at(), []
        enc = level_with(handler, anemone, crystals=crystals)
        for _ in range(HIT_POINTS - 1):
            shoot(enc)
        assert anemone.active and crystals == []
        assert handler.scoring.record_enemy_destroyed.call_count == 0
        shoot(enc)
        assert not anemone.active
        assert handler.sound_manager.play_enemy_destroy.call_count == 1
        assert handler.scoring.record_enemy_destroyed.call_count == 1
        assert len(crystals) == 1

    def test_callers_that_pass_no_anemones_still_work(self):
        handler = CollisionHandler(Mock(), Mock(), CommandRecorder())
        assert handler.handle_projectile_enemy_collisions(
            Projectile(POS, 0.0), [], [], [], []) is False


class TestRealGame:
    @pytest.fixture
    def game(self, monkeypatch, tmp_path):
        pygame.init()
        screen = pygame.display.set_mode((320, 240))
        monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)  # No hunter, so no pilot requests
        from game import Game
        from profiles import ProfileManager
        manager = ProfileManager(tmp_path / 'profiles.json')  # Never the player's real save file
        monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
        game = Game(screen)
        return game

    def test_scheduled_level_has_an_anemone_that_updates_and_draws(self, game):
        game.level = 26  # Past the level files, so the schedule decides
        game.start_level()
        game.state = config.STATE_PLAYING
        assert len(game.roster.of_kind('anemone')) == level_rules.get_anemone_count(26) > 0
        game.player_has_moved = True
        for _ in range(5):
            game.update(1.0)
        game.draw_game()

    def test_level_one_has_none(self, game):
        game.level = 1
        game.start_level()
        assert game.roster.of_kind('anemone') == []


class TestRealGameWiring:
    """The game itself must drive the anemone: knowing how is not enough."""

    @pytest.fixture
    def game(self, monkeypatch, tmp_path):
        pygame.init()
        screen = pygame.display.set_mode((320, 240))
        monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)  # No hunter, so no pilot requests
        from game import Game
        from profiles import ProfileManager
        manager = ProfileManager(tmp_path / 'profiles.json')  # Never the player's real save file
        monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
        game = Game(screen)
        game.level = 7  # The first level with anemones
        game.start_level()
        game.state = config.STATE_PLAYING
        return game

    def clear_space(self, game):
        """Leave only the anemone, an empty maze and a still, unshielded ship beside it."""
        anemones = game.roster.of_kind('anemone')
        game.roster.clear()
        game.roster.extend(anemones)
        anemone = anemones[0]
        game.maze.walls = []
        game.maze.spatial_grid = None
        game.ship.deactivate_shield()
        game.ship.vx = game.ship.vy = 0.0
        return anemone

    @pytest.mark.parametrize('level', [7])
    def test_no_anemone_can_reach_the_player_at_the_start(self, game, level):
        # This level used to put one within reach of the start
        game.level = level
        game.start_level()
        assert game.roster.of_kind('anemone')
        for anemone in game.roster.of_kind('anemone'):
            gap = math.hypot(anemone.x - game.ship.x, anemone.y - game.ship.y)
            assert gap > anemone.reach_px > 0

    def test_range_is_known_before_the_player_first_moves(self, game):
        assert not game.player_has_moved
        reach = TRAITS['pullsShip']['reachCells'] * (game.maze.cell_size_x + game.maze.cell_size_y) / 2
        assert reach > 0 and game.roster.of_kind('anemone')[0].reach_px == pytest.approx(reach)

    def test_player_shots_hurt_it(self, game):
        anemone = self.clear_space(game)
        game.player_has_moved = True
        shot = Projectile(anemone.get_pos(), 0.0)
        shot.source = 'player'
        game.projectiles.append(shot)
        game.ship.x, game.ship.y = anemone.x + anemone.reach_px * 3, anemone.y
        game.update(1.0)
        assert anemone.hit_points == HIT_POINTS - 1
        assert anemone.flinch_timer > 0

    def test_the_hunter_is_shown_anemones(self, game):
        assert game.roster.of_kind('anemone')[0] in game.hunter_surroundings.enemies()
