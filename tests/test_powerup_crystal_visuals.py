"""Unit tests for the powerup crystal's gem rendering and animation."""

import math
from unittest.mock import Mock

import pygame
import pytest
import config
from entities.powerup_crystal import PowerupCrystal
from game import Game
from game_handlers.collision_handler import CollisionHandler

POS = (400.0, 300.0)
FAR = (POS[0] + config.POWERUP_CRYSTAL_ATTRACTION_RADIUS * 4, POS[1])
NEAR = (POS[0] + config.POWERUP_CRYSTAL_ATTRACTION_RADIUS * 0.8, POS[1])


def make_crystal(settled=True):
    crystal = PowerupCrystal(POS)
    if settled:
        for _ in range(int(PowerupCrystal.SPAWN_FRAMES) + 1):
            crystal.update(1.0, FAR)
    return crystal


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def solid_bounds(screen):
    rects = pygame.mask.from_surface(screen, 254).get_bounding_rects()
    return rects[0].unionall(rects) if rects else pygame.Rect(0, 0, 0, 0)


class TestDrop:
    """A dropped crystal pops into view."""

    def test_starts_from_nothing(self):
        assert make_crystal(settled=False).spawn_scale == 0.0

    def test_overshoots_then_settles(self):
        crystal = make_crystal(settled=False)
        scales = []
        for _ in range(int(PowerupCrystal.SPAWN_FRAMES) + 5):
            crystal.update(1.0, FAR)
            scales.append(crystal.spawn_scale)
        assert max(scales) > 1.05
        assert scales[-1] == pytest.approx(1.0)

    def test_can_be_collected_while_popping_in(self):
        crystal = make_crystal(settled=False)
        assert crystal.check_circle_collision(POS, 10.0)


class TestFacets:
    """The gem turns: facets sweep across it and catch the light."""

    @pytest.mark.parametrize("rotation", [0.0, 17.0, 45.0, 123.0, 200.0, 359.0])
    def test_facets_span_the_gem_without_gaps(self, rotation):
        crystal = make_crystal()
        crystal.rotation_angle = rotation
        faces = sorted(crystal.visible_faces())
        assert faces[0][0] == pytest.approx(-PowerupCrystal.GEM_HALF_WIDTH, abs=1e-6)
        assert faces[-1][1] == pytest.approx(PowerupCrystal.GEM_HALF_WIDTH, abs=1e-6)
        for (_, right, _), (left, _, _) in zip(faces, faces[1:]):
            assert right == pytest.approx(left, abs=1e-6)

    def test_facets_differ_in_brightness(self):
        crystal = make_crystal()
        crystal.rotation_angle = 20.0
        brightness = [b for _, _, b in crystal.visible_faces()]
        assert max(brightness) - min(brightness) > 0.2
        assert all(0.0 <= b <= 1.0 for b in brightness)

    def test_light_sweeps_as_it_turns(self):
        crystal = make_crystal()
        crystal.rotation_angle = 0.0
        before = crystal.visible_faces()
        crystal.rotation_angle = 25.0
        assert crystal.visible_faces() != before


class TestTrail:
    """It leaves a trail only while being pulled toward the player."""

    def test_no_trail_at_rest(self):
        assert make_crystal().trail == []

    def test_trail_grows_while_pulled(self):
        crystal = make_crystal()
        for _ in range(6):
            crystal.update(1.0, NEAR)
        assert len(crystal.trail) >= 4
        assert len(crystal.trail) <= PowerupCrystal.TRAIL_LENGTH

    def test_trail_fades_when_released(self):
        crystal = make_crystal()
        for _ in range(6):
            crystal.update(1.0, NEAR)
        for _ in range(PowerupCrystal.TRAIL_LENGTH + 1):
            crystal.update(1.0, FAR)
        assert crystal.trail == []


class TestDrawing:
    """Smoke tests for drawing."""

    def test_gem_is_taller_than_wide(self):
        crystal = make_crystal()
        crystal.motes = 0  # Measure the gem itself
        screen = blank_screen()
        crystal.draw(screen)
        bounds = solid_bounds(screen)
        assert bounds.height > bounds.width
        assert bounds.height > crystal.radius * 2

    def test_draws_through_its_whole_cycle(self):
        crystal = make_crystal(settled=False)
        screen = blank_screen()
        crystal.draw(screen)  # Before any update: nothing to show yet, must not fail
        for step in range(150):
            crystal.update(1.0, NEAR if step > 100 else FAR)
            crystal.draw(screen)
        assert solid_bounds(screen).width > 0

    def test_inactive_draws_nothing(self):
        crystal = make_crystal()
        crystal.active = False
        screen = blank_screen()
        crystal.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestCollect:
    """Collecting it sets off a burst instead of a vanishing act."""

    def test_collecting_starts_the_burst(self):
        crystal = make_crystal()
        assert crystal.check_circle_collision(POS, 10.0)
        assert not crystal.active
        assert crystal.is_dying
        assert len(crystal.sparks) >= 6

    def test_missing_does_nothing(self):
        crystal = make_crystal()
        assert not crystal.check_circle_collision((POS[0] + 200, POS[1]), 10.0)
        assert crystal.active and not crystal.is_dying

    def test_sparks_fly_outward(self):
        crystal = make_crystal()
        crystal.check_circle_collision(POS, 10.0)
        crystal.update_death(1.0)
        before = [math.hypot(x - crystal.x, y - crystal.y) for x, y, _, _ in crystal.sparks]
        crystal.update_death(1.0)
        after = [math.hypot(x - crystal.x, y - crystal.y) for x, y, _, _ in crystal.sparks]
        assert all(b > a for a, b in zip(before, after))

    def test_burst_fades_out(self):
        crystal = make_crystal()
        crystal.check_circle_collision(POS, 10.0)
        shown = []
        for _ in range(int(crystal.DEATH_DURATION)):
            screen = blank_screen()
            crystal.draw_death(screen)
            shown.append(screen.get_bounding_rect().width > 0)
            crystal.update_death(1.0)
        assert shown[0] and shown[len(shown) // 2]
        assert not crystal.is_dying
        screen = blank_screen()
        crystal.draw_death(screen)
        assert screen.get_bounding_rect().width == 0


class TestGameLoop:
    """The game keeps a collected crystal around until its burst has played."""

    @pytest.fixture
    def game(self):
        game = Game.__new__(Game)
        game.scoring = Mock()
        game.collision_handler = CollisionHandler(Mock(), game.scoring, Mock())
        game.ship = Mock(x=POS[0], y=POS[1], radius=10.0)
        game.powerup_crystals = []
        game.hunter = None
        return game

    def test_collected_crystal_upgrades_once_and_plays_out(self, game):
        crystal = make_crystal()
        game.powerup_crystals.append(crystal)
        game._update_powerup_crystals(1.0)
        assert game.ship.activate_gun_upgrade.call_count == 1
        assert game.powerup_crystals == [crystal]
        assert crystal.is_dying

        for _ in range(int(crystal.DEATH_DURATION) + 1):
            game._update_powerup_crystals(1.0)
        assert game.ship.activate_gun_upgrade.call_count == 1
        assert game.powerup_crystals == []

    def test_uncollected_crystal_stays(self, game):
        crystal = PowerupCrystal((POS[0] + 300, POS[1]))
        game.powerup_crystals.append(crystal)
        for _ in range(30):
            game._update_powerup_crystals(1.0)
        assert game.powerup_crystals == [crystal]
        assert crystal.active
