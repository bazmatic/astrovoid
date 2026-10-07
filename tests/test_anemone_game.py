"""Anemones are spawned, updated, shot and drawn by the game like any other enemy."""
import math
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

import config
import level_rules
from entities.anemone import Anemone
from entities.command_recorder import CommandRecorder
from entities.projectile import Projectile
from entities.ship import Ship
from game_handlers.collision_handler import CollisionHandler
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.entity_manager import EntityManager
from game_handlers.spawn_manager import SpawnManager
from level_rules import EnemyCounts

POS = (400.0, 300.0)


def open_maze():
    return SimpleNamespace(cell_size_x=40.0, cell_size_y=40.0, walls=[], spatial_grid=None)


def counts(anemone):
    return EnemyCounts(total=0, static=0, patrol=0, aggressive=0, replay=0, flocker=0,
                       flighthouse=0, egg=0, anemone=anemone)


def spawn(anemone_count, positions):
    manager = EntityManager()
    SpawnManager(manager).spawn_all_enemies(1, positions, CommandRecorder(), counts(anemone_count), 0, 0)
    return manager


def shoot(handler, anemone, crystals=None):
    projectile = Projectile(POS, 0.0)
    projectile.source = 'player'
    return handler.handle_projectile_enemy_collisions(
        projectile, [], [], [], [], [], [], [], [], crystals if crystals is not None else [],
        anemones=[anemone])


class TestSpawning:
    def test_spawns_the_requested_number(self):
        manager = spawn(2, [(100.0, 100.0), (200.0, 200.0), (300.0, 300.0)])
        assert len(manager.anemones) == 2
        assert all(isinstance(a, Anemone) for a in manager.anemones)

    def test_spawns_only_as_many_as_fit(self):
        assert len(spawn(3, [(100.0, 100.0)]).anemones) == 1
        assert spawn(3, []).anemones == []

    def test_none_spawn_where_they_could_reach_the_players_start(self):
        manager = EntityManager()
        positions = [(100.0, 100.0), (150.0, 100.0), (400.0, 100.0), (500.0, 100.0)]
        SpawnManager(manager).spawn_all_enemies(
            1, positions, CommandRecorder(), counts(2), 0, 0, anemone_keep_clear=((90.0, 100.0), 200.0))
        assert [a.get_pos() for a in manager.anemones] == [(400.0, 100.0), (500.0, 100.0)]

    def test_fewer_spawn_when_too_few_places_are_clear_of_the_start(self):
        manager = EntityManager()
        SpawnManager(manager).spawn_all_enemies(
            1, [(100.0, 100.0), (400.0, 100.0)], CommandRecorder(), counts(2), 0, 0,
            anemone_keep_clear=((90.0, 100.0), 200.0))
        assert [a.get_pos() for a in manager.anemones] == [(400.0, 100.0)]

    def test_none_requested_none_spawned(self):
        assert spawn(0, [(100.0, 100.0)]).anemones == []


class TestEntityManager:
    def test_anemones_count_as_enemies(self):
        manager = EntityManager()
        alive, dead = Anemone(POS), Anemone((10.0, 10.0))
        manager.anemones.extend([alive, dead])
        dead.active = False
        assert list(manager.get_all_active_enemies()) == [alive]
        assert set(manager.get_all_enemies()) == {alive, dead}
        assert POS in manager.get_all_enemy_positions()
        manager.clear_all()
        assert manager.anemones == []


class TestUpdating:
    def make(self, distance):
        anemone = Anemone(POS)
        ship = Ship((POS[0] + distance, POS[1]))
        ship.deactivate_shield()
        return anemone, ship, Mock()

    def test_ship_in_reach_is_pulled(self):
        anemone, ship, scoring = self.make(80.0)
        EnemyUpdater().update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert ship.vx < 0
        assert scoring.record_enemy_collision.call_count == 0

    def test_several_anemones_together_still_pull_less_than_thrust(self):
        # Three stacked on one side would otherwise pull 2.4 times as hard as the engine pushes
        anemones = [Anemone((POS[0], POS[1] + offset)) for offset in (-3.0, 0.0, 3.0)]
        ship, scoring = Ship((POS[0] + 23.0, POS[1])), Mock()
        ship.deactivate_shield()
        for anemone in anemones:
            anemone.stun(0)
        ship.x = POS[0] + 40.0  # Clear of all three hulls, deep in all three fields
        EnemyUpdater().update_anemones(anemones, 1.0, open_maze(), ship, scoring)
        pull = math.hypot(ship.vx, ship.vy)
        assert pull == pytest.approx(config.ANEMONE_PULL_THRUST_FRACTION * config.SHIP_THRUST_FORCE)
        assert pull < config.SHIP_THRUST_FORCE
        assert all(anemone.pull_fraction > 0 for anemone in anemones)

    def test_opposing_anemones_cancel_out(self):
        left, right = Anemone((POS[0] - 60.0, POS[1])), Anemone((POS[0] + 60.0, POS[1]))
        ship, scoring = Ship(POS), Mock()
        ship.deactivate_shield()
        EnemyUpdater().update_anemones([left, right], 1.0, open_maze(), ship, scoring)
        assert (ship.vx, ship.vy) == pytest.approx((0.0, 0.0))
        assert left.pull_fraction > 0 and right.pull_fraction > 0

    def test_touching_it_stings_flings_and_releases(self):
        anemone, ship, scoring = self.make(10.0)
        ship.vx = -3.0
        EnemyUpdater().update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert scoring.record_enemy_collision.call_count == 1
        assert ship.vx == pytest.approx(config.ANEMONE_FLING_SPEED)
        assert ship.vy == pytest.approx(0.0)
        assert math.hypot(ship.x - POS[0], ship.y - POS[1]) > anemone.radius + ship.radius
        assert anemone.stun_timer == config.ANEMONE_RELEASE_FRAMES
        assert anemone.get_pos() == POS

    def test_it_does_not_drag_the_ship_straight_back(self):
        anemone, ship, scoring = self.make(10.0)
        updater = EnemyUpdater()
        updater.update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        updater.update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert ship.vx == pytest.approx(config.ANEMONE_FLING_SPEED)
        assert scoring.record_enemy_collision.call_count == 1

    def test_fling_from_dead_centre_still_throws_the_ship_clear(self):
        anemone, ship, scoring = self.make(0.0)
        EnemyUpdater().update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert math.hypot(ship.vx, ship.vy) == pytest.approx(config.ANEMONE_FLING_SPEED)
        assert math.hypot(ship.x - POS[0], ship.y - POS[1]) > anemone.radius + ship.radius
        assert all(math.isfinite(v) for v in (ship.x, ship.y, ship.vx, ship.vy))

    def test_shield_stops_both_the_pull_and_the_sting(self):
        anemone = Anemone(POS)
        ship, scoring = Ship((POS[0] + 10.0, POS[1])), Mock()
        ship.activate_shield()
        EnemyUpdater().update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert (ship.vx, ship.vy) == (0.0, 0.0)
        assert scoring.record_enemy_collision.call_count == 0

    def test_dead_anemones_are_skipped(self):
        anemone, ship, scoring = self.make(10.0)
        anemone.die()
        EnemyUpdater().update_anemones([anemone], 1.0, open_maze(), ship, scoring)
        assert (ship.vx, ship.vy) == (0.0, 0.0)
        assert scoring.record_enemy_collision.call_count == 0


class TestBeingShot:
    def test_a_hit_uses_the_shot_and_makes_it_flinch(self):
        handler, anemone = CollisionHandler(Mock(), Mock(), CommandRecorder()), Anemone(POS)
        assert shoot(handler, anemone)
        assert anemone.active
        assert anemone.stun_timer == config.ANEMONE_FLINCH_FRAMES
        assert handler.sound_manager.play_enemy_destroy.call_count == 0

    def test_a_flinch_does_not_cut_a_longer_stun(self):
        handler, anemone = CollisionHandler(Mock(), Mock(), CommandRecorder()), Anemone(POS)
        anemone.stun(500)
        shoot(handler, anemone)
        assert anemone.stun_timer == 500

    def test_killed_and_credited_on_the_last_hit_only(self, monkeypatch):
        monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
        handler, anemone, crystals = CollisionHandler(Mock(), Mock(), CommandRecorder()), Anemone(POS), []
        for _ in range(config.ANEMONE_HIT_POINTS - 1):
            shoot(handler, anemone, crystals)
        assert anemone.active and crystals == []
        assert handler.scoring.record_enemy_destroyed.call_count == 0
        shoot(handler, anemone, crystals)
        assert not anemone.active
        assert handler.sound_manager.play_enemy_destroy.call_count == 1
        assert handler.scoring.record_enemy_destroyed.call_count == 1
        assert len(crystals) == 1

    def test_callers_that_pass_no_anemones_still_work(self):
        handler = CollisionHandler(Mock(), Mock(), CommandRecorder())
        assert handler.handle_projectile_enemy_collisions(
            Projectile(POS, 0.0), [], [], [], [], [], [], [], [], []) is False


class TestRealGame:
    @pytest.fixture
    def game(self, monkeypatch):
        pygame.init()
        screen = pygame.display.set_mode((320, 240))
        monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)  # No hunter, so no pilot requests
        from game import Game
        game = Game(screen)
        game.profile_manager._save_profiles = lambda *args, **kwargs: None
        return game

    def test_scheduled_level_has_an_anemone_that_updates_and_draws(self, game):
        game.level = 5  # No anemone count in its level file, so the schedule decides
        game.start_level()
        game.state = config.STATE_PLAYING
        assert len(game.anemones) == level_rules.get_anemone_count(5) > 0
        assert game.anemones is game.entity_manager.anemones
        game.player_has_moved = True
        for _ in range(5):
            game.update(1.0)
        game.draw_game()

    def test_level_one_has_none(self, game):
        game.level = 1
        game.start_level()
        assert game.anemones == []


class TestRealGameWiring:
    """The game itself must drive the anemone: knowing how is not enough."""

    @pytest.fixture
    def game(self, monkeypatch):
        pygame.init()
        screen = pygame.display.set_mode((320, 240))
        monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)  # No hunter, so no pilot requests
        from game import Game
        game = Game(screen)
        game.profile_manager._save_profiles = lambda *args, **kwargs: None
        game.level = 4
        game.start_level()
        game.state = config.STATE_PLAYING
        return game

    def clear_space(self, game):
        """Leave only the anemone, an empty maze and a still, unshielded ship beside it."""
        anemone = game.anemones[0]
        for group in (game.enemies, game.replay_enemies, game.flockers, game.flighthouses,
                      game.split_bosses, game.mother_bosses, game.babies, game.eggs):
            group.clear()
        game.maze.walls = []
        game.maze.spatial_grid = None
        game.ship.deactivate_shield()
        game.ship.vx = game.ship.vy = 0.0
        return anemone

    @pytest.mark.parametrize('level', [6, 11])
    def test_no_anemone_can_reach_the_player_at_the_start(self, game, level):
        # These two levels used to put one within reach of the start
        game.level = level
        game.start_level()
        assert game.anemones
        for anemone in game.anemones:
            gap = math.hypot(anemone.x - game.ship.x, anemone.y - game.ship.y)
            assert gap > anemone.reach(game.maze)

    def test_range_is_known_before_the_player_first_moves(self, game):
        assert not game.player_has_moved
        assert game.anemones[0].reach_px == pytest.approx(game.anemones[0].reach(game.maze))
        assert game.anemones[0].reach_px > 0

    def test_update_pulls_the_ship(self, game):
        anemone = self.clear_space(game)
        game.ship.x, game.ship.y = anemone.x + anemone.reach(game.maze) * 0.5, anemone.y
        game.player_has_moved = True
        game.update(1.0)
        assert game.ship.vx < 0
        assert anemone.pull_fraction > 0

    def test_player_shots_hurt_it(self, game):
        anemone = self.clear_space(game)
        game.player_has_moved = True
        shot = Projectile(anemone.get_pos(), 0.0)
        shot.source = 'player'
        game.projectiles.append(shot)
        game.ship.x, game.ship.y = anemone.x + anemone.reach(game.maze) * 3, anemone.y
        game.update(1.0)
        assert anemone.hit_points == config.ANEMONE_HIT_POINTS - 1
        assert anemone.is_stunned

    def test_the_hunter_is_shown_anemones(self, game):
        class Observed(Exception):
            """Stops the update once the hunter has been handed what it can see."""

        def tick(observe, **kwargs):
            observe(0.0, 0)
            raise Observed

        seen = []
        game.hunter = Mock(active=True)
        game.hunter_controller = Mock()
        game.hunter_controller.tick.side_effect = tick
        game.hunter_perception = Mock()
        game.hunter_perception.observe.side_effect = lambda hunter, maze, player, enemies, *rest: seen.extend(enemies)
        game.player_has_moved = True
        try:
            with pytest.raises(Observed):
                game._update_hunter(1.0)
        finally:
            game.hunter = game.hunter_controller = game.hunter_perception = None
        assert game.anemones[0] in seen
