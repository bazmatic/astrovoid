"""Unit tests for the egg sac's rendering, embryos and endings."""

import math
import pygame
import pytest
import config
from entities.egg import Egg
from entities.command_recorder import CommandRecorder

POS = (400.0, 300.0)


def make_egg(growth=0.0, babies=None):
    """Create an egg at a given growth progress (0.0 just laid, 1.0 about to hatch)."""
    egg = Egg(POS)
    egg.current_radius = egg.initial_radius + (egg.max_radius - egg.initial_radius) * growth
    egg.radius = egg.current_radius
    if babies is not None:
        egg.baby_count = babies
    return egg


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def solid_bounds(screen):
    rects = pygame.mask.from_surface(screen, 200).get_bounding_rects()
    return rects[0].unionall(rects) if rects else pygame.Rect(0, 0, 0, 0)


class TestHonestCount:
    """The sac shows exactly the babies that will hatch."""

    def test_count_is_rolled_when_laid(self):
        counts = {Egg(POS).baby_count for _ in range(200)}
        assert counts == set(range(config.EGG_BABY_SPAWN_MIN, config.EGG_BABY_SPAWN_MAX + 1))

    @pytest.mark.parametrize("babies", [1, 2, 3])
    def test_hatches_the_babies_it_showed(self, babies):
        egg = make_egg(1.0, babies)
        assert len(egg.embryo_positions()) == babies
        hatched = []
        egg.pop(CommandRecorder(), hatched)
        assert len(hatched) == babies

    @pytest.mark.parametrize("babies", [1, 2, 3])
    def test_embryos_stay_inside_the_sac(self, babies):
        egg = make_egg(1.0, babies)
        for x, y in egg.embryo_positions():
            assert math.hypot(x, y) < 0.6


class TestDevelopment:
    """Embryos develop as the egg grows, so you can read how close it is."""

    def test_growth_progress(self):
        assert make_egg(0.0).growth_progress == pytest.approx(0.0)
        assert make_egg(0.5).growth_progress == pytest.approx(0.5)
        assert make_egg(1.0).growth_progress == pytest.approx(1.0)

    def test_stages_arrive_in_order(self):
        newly_laid, eyed, limbed = make_egg(0.1), make_egg(0.45), make_egg(0.8)
        assert newly_laid.eye_development == 0.0 and newly_laid.tentacle_development == 0.0
        assert eyed.eye_development > 0.0 and eyed.tentacle_development == 0.0
        assert limbed.eye_development == 1.0 and limbed.tentacle_development > 0.0

    def test_urgency_only_near_hatching(self):
        assert make_egg(0.5).urgency == 0.0
        assert 0.0 < make_egg(0.85).urgency < 1.0
        assert make_egg(1.0).urgency == pytest.approx(1.0)

    def test_pulses_faster_when_urgent(self):
        calm, urgent = make_egg(0.2), make_egg(0.99)
        calm.growth_rate = urgent.growth_rate = 0.0
        calm.wobble_phase = urgent.wobble_phase = 0.0
        for _ in range(30):
            calm.update(1.0)
            urgent.update(1.0)
        assert urgent.wobble_phase > calm.wobble_phase * 1.5


class TestHits:
    """The sac jiggles when shot."""

    def test_jiggles_on_hit(self):
        egg = make_egg(0.5)
        assert egg.jiggle == 0.0
        egg.take_damage()
        assert egg.jiggle == 1.0

    def test_jiggle_settles(self):
        egg = make_egg(0.5)
        egg.growth_rate = 0.0
        egg.take_damage()
        for _ in range(90):
            egg.update(1.0)
        assert egg.jiggle < 0.01

    def test_tears_follow_damage(self):
        egg = make_egg(1.0)
        egg.max_hit_points = egg.hit_points = 4
        assert egg.tear_count == 0
        egg.hit_points = 2
        some = egg.tear_count
        egg.hit_points = 1
        assert 0 < some < egg.tear_count


class TestDrawing:
    """Smoke tests for drawing."""

    @pytest.mark.parametrize("growth", [0.0, 0.3, 0.7, 1.0])
    @pytest.mark.parametrize("babies", [1, 3])
    def test_draws_at_every_stage(self, growth, babies):
        egg = make_egg(growth, babies)
        screen = blank_screen()
        egg.draw(screen)
        egg.take_damage()
        egg.update(1.0)
        egg.draw(screen)
        assert screen.get_bounding_rect().width > 0

    @pytest.mark.parametrize("growth", [0.0, 1.0])
    def test_sac_matches_its_collision_size(self, growth):
        egg = make_egg(growth)
        screen = blank_screen()
        egg.draw(screen)
        bounds = solid_bounds(screen)
        assert egg.radius * 1.6 < bounds.width < egg.radius * 2.4
        assert egg.radius * 1.6 < bounds.height < egg.radius * 2.4

    def test_sac_is_see_through(self):
        egg = make_egg(1.0, babies=1)
        screen = blank_screen()
        egg.draw(screen)
        # Between the centre embryo and the rim there is only jelly
        alpha = screen.get_at((int(egg.x), int(egg.y + egg.radius * 0.72))).a
        assert 0 < alpha < 255

    def test_inactive_draws_nothing(self):
        egg = make_egg(0.5)
        egg.active = False
        screen = blank_screen()
        egg.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestEndings:
    """Hatching and being shot each get their own animation."""

    def run_ending(self, egg):
        shown = []
        for _ in range(int(egg.DEATH_DURATION)):
            screen = blank_screen()
            egg.draw_death(screen)
            shown.append(screen.get_bounding_rect().width > 0)
            egg.update_death(1.0)
        screen = blank_screen()
        egg.draw_death(screen)
        return shown, screen.get_bounding_rect().width

    def test_hatching_splits_open(self):
        egg = make_egg(1.0)
        egg.pop(CommandRecorder(), [])
        assert not egg.active
        assert egg.is_dying
        assert egg.ending == "hatched"
        shown, leftover = self.run_ending(egg)
        assert shown[0] and shown[len(shown) // 2]
        assert leftover == 0
        assert not egg.is_dying

    def test_shot_egg_bursts_into_blobs(self):
        egg = make_egg(0.6)
        egg.die()
        assert egg.is_dying
        assert egg.ending == "burst"
        egg.update_death(1.0)
        before = [math.hypot(b.x - egg.x, b.y - egg.y) for b in egg.blobs]
        egg.update_death(1.0)
        after = [math.hypot(b.x - egg.x, b.y - egg.y) for b in egg.blobs]
        assert len(before) >= 5
        assert all(b > a for a, b in zip(before, after))

    def test_burst_fades_out(self):
        egg = make_egg(0.6)
        egg.die()
        shown, leftover = self.run_ending(egg)
        assert shown[0] and shown[len(shown) // 2]
        assert leftover == 0

    def test_shot_egg_hatches_nothing(self):
        egg = make_egg(1.0, babies=3)
        egg.die()
        hatched = []
        for _ in range(int(egg.DEATH_DURATION) + 5):
            egg.update_death(1.0)
            egg.update(1.0)
        assert hatched == []
        assert not egg.should_pop() or not egg.active
