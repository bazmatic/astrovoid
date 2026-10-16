"""The EXIT block in the side panel."""
import pygame
import pytest

import config
from rendering.exit_panel import EXIT_PANEL_TOP, draw_exit_panel


@pytest.fixture
def surface():
    pygame.init()
    surface = pygame.Surface((1352, 878))
    surface.fill(config.COLOR_BACKGROUND)
    return surface


def pixels(surface, rect):
    return {tuple(surface.get_at((x, y)))[:3] for x in range(rect.left, rect.right) for y in range(rect.top, rect.bottom)}


def test_a_shut_exit_shows_what_is_left(surface):
    rect = draw_exit_panel(surface, ['KILL EGGS', '3 LEFT'], False)
    assert rect.top >= EXIT_PANEL_TOP
    assert pixels(surface, rect) - {tuple(config.COLOR_BACKGROUND)[:3]}


def test_an_open_exit_says_open_in_the_exit_colour(surface):
    rect = draw_exit_panel(surface, [], True)
    assert tuple(config.COLOR_EXIT)[:3] in pixels(surface, rect)


def test_long_text_stays_inside_the_panel(surface):
    rect = draw_exit_panel(surface, ['KILL SQUIDDLER BOSSES, SQUIDLETS', '12 LEFT'], False)
    assert rect.right <= config.UI_ZONE_WIDTH
    beyond = pygame.Rect(config.UI_ZONE_WIDTH, 0, 1352 - config.UI_ZONE_WIDTH, 878)
    assert pixels(surface, beyond) == {tuple(config.COLOR_BACKGROUND)[:3]}
