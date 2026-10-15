# tests/test_rules_hunter_game.py
import math
from types import SimpleNamespace

import pygame
import pytest

import config
import level_config
from entities.projectile import Projectile
from entities.rules_hunter import RULES_HUNTER_HIT_POINTS, RulesHunter
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_rules_hunter import SilentWorker


@pytest.fixture
def arena(game, monkeypatch):
    """A started level with one Rules hunter whose pilot never answers."""
    workers = []

    def factory():
        workers.append(SilentWorker())
        return workers[-1]

    game._rules_worker_factory = factory
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 1)
    monkeypatch.setattr(level_config, 'get_level_enemy_counts', lambda level: None)
    game.level = 3          # a small level: the fixture's maze is a tiny empty one
    game.start_level()
    game.workers = workers
    return game


def shot_at(hunter, source='player'):
    return Projectile((hunter.x, hunter.y), 0.0, source=source)


def test_the_protagonist_is_the_players_ship(arena):
    assert arena.protagonist() is arena.ship


def test_a_level_with_a_rules_hunter_spawns_one_clear_of_the_player(arena):
    assert len(arena.rules_hunters) == 1 and isinstance(arena.rules_hunters[0], RulesHunter)
    hunter = arena.rules_hunters[0]
    assert hunter in arena.entity_manager.get_all_active_enemies()
    assert math.hypot(hunter.x - arena.ship.x, hunter.y - arena.ship.y) >= config.ENEMY_START_CLEARANCE


def test_it_starts_far_from_the_player_and_clear_of_the_other_enemies(arena):
    hunter = arena.rules_hunters[0]
    others = [e.get_pos() for e in arena.entity_manager.get_all_enemies() if e is not hunter]
    assert all(math.hypot(hunter.x - x, hunter.y - y) > hunter.radius * 2 for x, y in others)


def test_a_level_without_one_spawns_none(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 0)
    game.start_level()
    assert game.rules_hunters == []


def test_restarting_the_level_stops_the_old_hunters_worker(arena):
    first = arena.workers[0]
    arena.start_level()
    assert first.closed and len(arena.workers) == 2 and not arena.workers[1].closed


def test_closing_stops_every_rules_hunters_worker(arena):
    arena._close_enemy_hunters()
    assert all(w.closed for w in arena.workers)


def test_the_players_shots_destroy_it_in_twelve_hits_with_no_crystal(arena):
    hunter = arena.rules_hunters[0]
    crystals_before = len(arena.powerup_crystals)
    destroyed = 0
    for hit in range(RULES_HUNTER_HIT_POINTS):
        projectile = shot_at(hunter)
        used = arena.collision_handler.handle_projectile_enemy_collisions(
            projectile, arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
            arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
            anemones=arena.anemones, jev_beacon_allowed=False, enemy_hunters=arena.rules_hunters)
        assert used
        destroyed += not hunter.active
    assert destroyed == 1 and not hunter.active and hunter.hit_points == 0
    assert len(arena.powerup_crystals) == crystals_before


def test_the_hunters_shots_hurt_it_too(arena):
    hunter = arena.rules_hunters[0]
    arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter, 'hunter'), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, enemy_hunters=arena.rules_hunters)
    assert hunter.hit_points == RULES_HUNTER_HIT_POINTS - 1


def test_its_own_shots_do_not_hurt_it(arena):
    hunter = arena.rules_hunters[0]
    assert not arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter, 'enemy'), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, enemy_hunters=arena.rules_hunters)
    assert hunter.hit_points == RULES_HUNTER_HIT_POINTS


def test_killing_it_with_a_player_shot_feeds_the_level_complete_portrait(arena):
    from rendering.enemy_death_portrait import EnemyDeathPortrait
    hunter = arena.rules_hunters[0]
    hunter.hit_points = 1
    arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, enemy_hunters=arena.rules_hunters)
    assert arena.scoring.enemies_destroyed >= 1
    portrait = EnemyDeathPortrait(arena.collision_handler.last_player_kill, 20)
    portrait.update(5.0)


def test_the_level_cannot_be_finished_while_it_lives(arena):
    hunter = arena.rules_hunters[0]
    assert any(e is hunter for e in arena.entity_manager.get_all_active_enemies())
    for other in list(arena.entity_manager.get_all_active_enemies()):
        if other is not hunter:
            other.active = False
    assert list(arena.entity_manager.get_all_active_enemies()) == [hunter]
    hunter.die()
    assert list(arena.entity_manager.get_all_active_enemies()) == []


def test_touching_it_counts_as_an_enemy_collision_for_the_player(arena):
    hunter = arena.rules_hunters[0]
    arena.ship.x, arena.ship.y = hunter.x, hunter.y
    arena.ship.shield_active = False
    before = arena.scoring.enemy_collisions
    arena._fly_enemy_hunters(1.0)
    assert arena.scoring.enemy_collisions > before


def test_flying_with_the_player_inactive_does_not_crash(arena):
    arena.ship.active = False
    for _ in range(20):
        arena._fly_enemy_hunters(1.0)


def test_its_shots_join_the_games_projectiles(arena):
    hunter = arena.rules_hunters[0]
    hunter.flight.fly = lambda dt: [shot_at(hunter, 'enemy')]
    before = len(arena.projectiles)
    arena._fly_enemy_hunters(1.0)
    assert len(arena.projectiles) == before + 1


def test_a_level_with_no_room_for_it_skips_it_and_stays_playable(arena):
    arena.entity_manager.rules_hunters.clear()
    arena._spawn_enemy_hunters([])                      # no valid spot at all
    assert arena.rules_hunters == []
    arena._spawn_enemy_hunters([(arena.ship.x, arena.ship.y)])    # a spot, but on top of the player's start
    assert len(arena.rules_hunters) <= 1                # placed or skipped, never an exception


def test_it_is_drawn_while_it_lives_and_its_death_is_animated(arena):
    pygame.init()
    screen = pygame.Surface((1352, 878))
    hunter = arena.rules_hunters[0]
    hunter.x, hunter.y = 600.0, 400.0
    arena.draw_enemy_hunters(screen)
    assert any(screen.get_at((x, y))[:3] != (0, 0, 0)
               for x in range(560, 640) for y in range(360, 440))
    hunter.die()
    screen.fill((0, 0, 0))
    arena.entity_manager.draw_dying(screen)
    assert any(screen.get_at((x, y))[:3] != (0, 0, 0)
               for x in range(540, 660) for y in range(340, 460))
