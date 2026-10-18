"""The row of five stars drawn in the side panel during play."""
import pygame

import config
from rendering.star_row import STAR_ROW_Y, draw_star_row


def brightest(surface, rect):
    return max(sum(surface.get_at((x, y))[:3]) for x in range(rect.left, rect.right)
               for y in range(rect.top, rect.bottom))


def test_lit_stars_are_brighter_than_unlit_ones_and_the_row_fits_the_panel():
    pygame.init()
    pygame.display.set_mode((320, 240))
    screen = pygame.Surface((config.UI_ZONE_WIDTH, 100))
    screen.fill(config.COLOR_BACKGROUND)
    size = 20
    rect = draw_star_row(screen, (True, False, True, False, True), 0.0, (config.UI_ZONE_WIDTH // 2, 50), size)
    assert 0 <= rect.left and rect.right <= config.UI_ZONE_WIDTH
    slots = [pygame.Rect(0, 0, size, size) for _ in range(5)]
    step = (rect.width - size) / 4
    for i, slot in enumerate(slots):
        slot.center = (round(rect.left + size / 2 + step * i), 50)
    lit = [brightest(screen, slots[i]) for i in (0, 2, 4)]
    unlit = [brightest(screen, slots[i]) for i in (1, 3)]
    assert min(lit) > max(unlit)
    assert STAR_ROW_Y > 0


def test_the_par_star_pulses():
    pygame.init()
    pygame.display.set_mode((320, 240))
    frames = []
    for pulse in (0.0, 1.0):
        screen = pygame.Surface((config.UI_ZONE_WIDTH, 100))
        screen.fill(config.COLOR_BACKGROUND)
        draw_star_row(screen, (True,) * 5, pulse, (config.UI_ZONE_WIDTH // 2, 50), 20)
        frames.append(pygame.image.tostring(screen, 'RGB'))
    assert frames[0] != frames[1]
