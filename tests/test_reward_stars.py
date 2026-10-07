"""Reward stars land in order, celebrate records, and leave an opaque frame."""
import pygame
import pytest
import config
from rendering.ui_elements import AnimatedStarRating


@pytest.fixture
def screen():
    pygame.init()
    pygame.display.set_mode((320, 240))
    surface = pygame.Surface((900, 500), pygame.SRCALPHA)
    surface.fill((15, 8, 28, 255))
    return surface


def test_stars_drop_then_land_in_order_with_one_rising_sound_each(screen):
    stars = AnimatedStarRating(1.0, 250, 200)
    sounds = []
    stars.set_sound_callback(sounds.append)
    stars.update(config.STAR_APPEAR_DURATION * 60 * 0.1)
    assert stars.star_scale(0) > 1.0 and stars.star_scale(1) == 0
    assert sounds == []
    stars.update(config.STAR_APPEAR_DURATION * 60 * 0.9)
    assert len(sounds) == 1 and stars.star_scale(0) == pytest.approx(1.0)
    assert stars.bursts and not stars.is_complete()
    for _ in range(4):
        stars.update(config.STAR_APPEAR_DURATION * 60)
    assert stars.is_complete() and len(sounds) == 5
    assert sounds == sorted(set(sounds))
    assert stars.flash > 0.9
    stars.update(60)
    assert stars.bursts == [] and stars.flash == 0
    stars.update(60)
    assert len(sounds) == 5


def test_only_newly_gained_stars_get_record_glow_and_sparks_are_capped(screen):
    stars = AnimatedStarRating(1.0, 250, 200, previous_stars=3)
    assert stars.glow_color(0) == stars.glow_color(2)
    assert stars.glow_color(3) != stars.glow_color(2)
    assert stars.glow_color(4) == stars.glow_color(3)
    for _ in range(180):
        stars.update(1)
        assert sum(len(burst.sparks) for burst in stars.bursts) <= 80
        stars.draw(screen)
    assert pygame.mask.from_surface(screen, 254).count() == 900 * 500


def test_large_time_step_finishes_without_stale_sparks_or_duplicate_sound(screen):
    stars = AnimatedStarRating(0.65, 250, 200)
    sounds = []
    stars.set_sound_callback(sounds.append)
    stars.update(240)
    assert stars.num_stars == 3 and stars.is_complete()
    assert len(sounds) == 3 and stars.bursts == [] and stars.flash == 0
