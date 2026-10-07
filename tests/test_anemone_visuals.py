"""The anemone shows its reach, reaches for the ship while pulling, and clamps shut when stunned."""
import math

import pygame
import pytest

import config
from entities.anemone import Anemone

POS = (200.0, 200.0)
SIZE = (400, 400)


def draw(anemone, death=False):
    screen = pygame.Surface(SIZE, pygame.SRCALPHA)
    screen.fill((*config.COLOR_BACKGROUND, 255))
    (anemone.draw_death if death else anemone.draw)(screen)
    return screen


def drawn_pixels(screen):
    background = (*config.COLOR_BACKGROUND, 255)
    return [(x, y) for x in range(SIZE[0]) for y in range(SIZE[1]) if screen.get_at((x, y)) != background]


def extent(screen, max_radius):
    """Furthest drawn pixel from the centre, ignoring anything beyond max_radius (the range streaks)."""
    distances = [math.hypot(x - POS[0], y - POS[1]) for x, y in drawn_pixels(screen)]
    return max((d for d in distances if d <= max_radius), default=0.0)


def brightness(screen, radius):
    """Total brightness within a radius of the centre."""
    return sum(sum(screen.get_at((x, y))[:3])
               for x in range(int(POS[0] - radius), int(POS[0] + radius) + 1)
               for y in range(int(POS[1] - radius), int(POS[1] + radius) + 1)
               if math.hypot(x - POS[0], y - POS[1]) <= radius)


def pulling(fraction=1.0, angle=0.0):
    anemone = Anemone(POS)
    anemone.reach_px = 140.0
    anemone.pull_fraction = fraction
    anemone.pull_angle = angle
    return anemone


def test_idle_anemone_is_drawn_around_its_position_with_tentacles_past_its_body():
    anemone = Anemone(POS)
    screen = draw(anemone)
    assert extent(screen, anemone.radius * 3) > anemone.radius * 1.2
    assert screen.get_at((int(POS[0]), int(POS[1])))[:3] != config.COLOR_BACKGROUND


def test_mouth_glows_brighter_the_harder_it_pulls():
    idle = brightness(draw(pulling(0.0)), Anemone(POS).radius * 0.5)
    half = brightness(draw(pulling(0.5)), Anemone(POS).radius * 0.5)
    full = brightness(draw(pulling(1.0)), Anemone(POS).radius * 0.5)
    assert idle < half < full


def test_tentacles_lean_toward_the_ship_it_is_pulling():
    def centre_of_mass_x(screen, radius):
        points = [(x, y) for x, y in drawn_pixels(screen) if math.hypot(x - POS[0], y - POS[1]) <= radius]
        return sum(x for x, _ in points) / len(points)

    radius = Anemone(POS).radius * 3
    right = centre_of_mass_x(draw(pulling(1.0, 0.0)), radius)
    left = centre_of_mass_x(draw(pulling(1.0, math.pi)), radius)
    assert right > POS[0] + 0.5 > POS[0] - 0.5 > left


def test_range_streaks_show_the_reach_and_stay_inside_it():
    anemone = pulling(0.0)
    screen = draw(anemone)
    far = [math.hypot(x - POS[0], y - POS[1]) for x, y in drawn_pixels(screen)]
    assert max(far) > anemone.radius * 3  # Something is drawn well out from the body
    assert max(far) <= anemone.reach_px + 1


def test_range_streaks_are_faint():
    anemone = pulling(0.0)
    screen = draw(anemone)
    streaks = [screen.get_at((x, y))[:3] for x, y in drawn_pixels(screen)
               if math.hypot(x - POS[0], y - POS[1]) > anemone.radius * 3]
    assert streaks
    assert max(sum(color) for color in streaks) < sum(config.ANEMONE_TIP_COLOR) * 0.5


def test_stunned_anemone_folds_in_and_shows_no_streaks():
    open_one = pulling(0.0)
    shut = pulling(0.0)
    shut.stun(90)
    assert shut.closed_fraction == pytest.approx(1.0)
    assert open_one.closed_fraction == 0.0
    limit = open_one.radius * 3
    assert extent(draw(shut), limit) < extent(draw(open_one), limit)
    far = [1 for x, y in drawn_pixels(draw(shut)) if math.hypot(x - POS[0], y - POS[1]) > limit]
    assert far == []


def test_it_reopens_over_the_last_third_of_a_stun():
    anemone = Anemone(POS)
    anemone.stun(90)
    for _ in range(60):
        anemone.update(1.0)
    assert anemone.closed_fraction == pytest.approx(1.0)
    for _ in range(15):
        anemone.update(1.0)
    assert 0.0 < anemone.closed_fraction < 1.0
    for _ in range(15):
        anemone.update(1.0)
    assert anemone.closed_fraction == 0.0


def test_dead_anemone_is_not_drawn_by_draw():
    anemone = Anemone(POS)
    anemone.die()
    assert drawn_pixels(draw(anemone)) == []


def test_death_wilts_and_fades_to_nothing():
    anemone = Anemone(POS)
    assert Anemone.DEATH_DURATION == 30.0
    anemone.die()
    early = len(drawn_pixels(draw(anemone, death=True)))
    for _ in range(20):
        anemone.update_death(1.0)
    late = len(drawn_pixels(draw(anemone, death=True)))
    for _ in range(11):
        anemone.update_death(1.0)
    assert early > late > 0
    assert drawn_pixels(draw(anemone, death=True)) == []


@pytest.mark.parametrize('state', ['idle', 'pulling', 'stunned', 'dying'])
def test_drawing_leaves_the_screen_opaque(state):
    anemone = pulling(1.0 if state == 'pulling' else 0.0)
    if state == 'stunned':
        anemone.stun(90)
    if state == 'dying':
        anemone.die()
        anemone.update_death(5.0)
    screen = draw(anemone, death=state == 'dying')
    assert pygame.mask.from_surface(screen, 254).count() == SIZE[0] * SIZE[1]
