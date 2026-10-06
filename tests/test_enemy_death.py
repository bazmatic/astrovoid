"""Unit tests for enemy death: the shared die() hook and the squid's withdrawal."""

import math
from unittest.mock import Mock

import pygame
import pytest
from entities.enemy import Enemy
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.baby import Baby
from entities.split_boss import SplitBoss
from entities.mother_boss import MotherBoss
from entities.flocker_enemy_ship import FlockerEnemyShip
from entities.flighthouse_enemy import FlighthouseEnemy
from entities.egg import Egg
from entities.projectile import Projectile
from entities.command_recorder import CommandRecorder
from game_handlers.collision_handler import CollisionHandler
from game_handlers.entity_manager import EntityManager

POS = (400.0, 300.0)
SQUID_CLASSES = [ReplayEnemyShip, Baby, SplitBoss, MotherBoss]


def make_all_enemies():
    recorder = CommandRecorder()
    return [
        Enemy(POS, "static"),
        ReplayEnemyShip(POS, recorder),
        Baby(POS, recorder),
        SplitBoss(POS, recorder),
        MotherBoss(POS, recorder),
        FlockerEnemyShip(POS),
        FlighthouseEnemy(POS),
        Egg(POS),
    ]


def make_squid(cls=ReplayEnemyShip):
    squid = cls(POS, CommandRecorder())
    squid.angle = 0.0
    for _ in range(60):
        squid._update_tentacles(1.0)
    return squid


def run_death(entity, fraction):
    """Advance a dying entity through a fraction of its animation."""
    for _ in range(int(round(entity.DEATH_DURATION * fraction))):
        entity.update_death(1.0)


def longest_reach(squid):
    return max(math.hypot(chain[-1][0] - chain[0][0], chain[-1][1] - chain[0][1]) for chain in squid.tentacles)


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


class TestDieHook:
    """Every enemy type shares the same death interface."""

    @pytest.mark.parametrize("enemy", make_all_enemies(), ids=lambda e: type(e).__name__)
    def test_die_deactivates_immediately(self, enemy):
        assert not enemy.is_dying
        enemy.die()
        assert not enemy.active

    @pytest.mark.parametrize("enemy", make_all_enemies(), ids=lambda e: type(e).__name__)
    def test_death_animation_ends(self, enemy):
        enemy.die()
        for _ in range(int(enemy.DEATH_DURATION) + 1):
            enemy.update_death(1.0)
        assert not enemy.is_dying
        enemy.draw_death(blank_screen())  # Must be safe to call when finished

    @pytest.mark.parametrize("enemy", make_all_enemies(), ids=lambda e: type(e).__name__)
    def test_dying_matches_duration(self, enemy):
        enemy.die()
        assert enemy.is_dying == (enemy.DEATH_DURATION > 0)

    def test_living_entity_is_not_dying(self):
        assert not make_squid().is_dying


class TestSquidWithdrawal:
    """The squid pulls into itself and vanishes."""

    @pytest.mark.parametrize("cls", SQUID_CLASSES)
    def test_squid_has_death_animation(self, cls):
        squid = make_squid(cls)
        squid.die()
        assert squid.is_dying

    def test_progress_runs_from_zero_to_one(self):
        squid = make_squid()
        assert squid.death_progress == 0.0
        squid.die()
        assert squid.death_progress == 0.0
        run_death(squid, 0.5)
        assert squid.death_progress == pytest.approx(0.5, abs=0.05)
        run_death(squid, 0.6)
        assert squid.death_progress == 1.0

    def test_arms_reel_in(self):
        squid = make_squid()
        before = longest_reach(squid)
        squid.die()
        run_death(squid, 0.4)
        midway = longest_reach(squid)
        run_death(squid, 0.4)
        assert midway < before
        assert longest_reach(squid) < squid.radius * 0.1

    def test_short_arms_finish_before_long_tentacles(self):
        squid = make_squid()
        squid.die()
        run_death(squid, 0.55)
        reach = [math.hypot(c[-1][0] - c[0][0], c[-1][1] - c[0][1]) for c in squid.tentacles]
        long_reach = [reach[i] for i in squid.LONG_TENTACLE_INDICES]
        short_reach = [r for i, r in enumerate(reach) if i not in squid.LONG_TENTACLE_INDICES]
        assert max(short_reach) < 0.5
        assert min(long_reach) > 0.5

    def test_eyes_close(self):
        squid = make_squid()
        squid.die()
        run_death(squid, 0.25)
        assert squid.blink_state == 0.0

    def test_remnant_coasts_to_a_stop(self):
        squid = make_squid()
        squid.vx = 2.0
        squid.die()
        run_death(squid, 1.0)
        assert POS[0] < squid.x < POS[0] + 30
        assert abs(squid.vx) < 0.05

    @pytest.mark.parametrize("cls", SQUID_CLASSES)
    def test_drawn_body_shrinks_away(self, cls):
        squid = make_squid(cls)
        squid.die()
        sizes = []
        for _ in range(4):
            run_death(squid, 0.2)
            screen = blank_screen()
            squid.draw_death(screen)
            # Count solid pixels only, so the soft glow doesn't mask the shrinking body
            sizes.append(pygame.mask.from_surface(screen, 254).count())
        assert sizes[0] > sizes[1] > sizes[2] > sizes[3] > 0
        run_death(squid, 0.3)
        screen = blank_screen()
        squid.draw_death(screen)
        assert screen.get_bounding_rect().width == 0

    def test_living_draw_skips_dead_squid(self):
        squid = make_squid()
        squid.die()
        screen = blank_screen()
        squid.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestGameIntegration:
    """Kills go through die(), and the entity manager animates the remnants."""

    def test_projectile_kill_starts_squid_death(self):
        handler = CollisionHandler(Mock(), Mock(), CommandRecorder())
        squid = make_squid()
        projectile = Projectile(POS, 0.0)
        hit = handler.handle_projectile_enemy_collisions(
            projectile, [], [squid], [], [], [], [], [], [], []
        )
        assert hit
        assert not squid.active
        assert squid.is_dying

    def test_entity_manager_updates_and_draws_dying(self):
        manager = EntityManager()
        dying = make_squid()
        alive = make_squid(Baby)
        manager.replay_enemies.append(dying)
        manager.babies.append(alive)
        dying.die()

        manager.update_dying(1.0)
        assert dying.death_progress > 0.0
        assert alive.death_progress == 0.0

        screen = blank_screen()
        manager.draw_dying(screen)
        assert screen.get_bounding_rect().width > 0

        for _ in range(int(dying.DEATH_DURATION) + 1):
            manager.update_dying(1.0)
        screen = blank_screen()
        manager.draw_dying(screen)
        assert screen.get_bounding_rect().width == 0
