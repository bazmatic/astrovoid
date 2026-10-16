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


def test_a_long_list_of_kinds_wraps_instead_of_shrinking_out_of_sight(surface):
    from rendering.fonts import get_font
    line_height = get_font(20).get_height()
    rect = draw_exit_panel(surface, ['KILL SQUIDDLER BOSSES, SQUIDLETS, TERMINATORS, CRABS', '9 LEFT'], False)
    label_height = get_font(16).get_height()
    # The kinds wrap onto lines of full-size text: at least three lines, none of them shrunk
    assert rect.height >= label_height + 3 * line_height
    assert rect.right <= config.UI_ZONE_WIDTH


def test_without_room_to_wrap_the_kinds_shrink_onto_one_line(surface):
    bottom = EXIT_PANEL_TOP + 66
    rect = draw_exit_panel(surface, ['KILL SQUIDDLER BOSSES, SQUIDLETS', '12 LEFT'], False, bottom=bottom)
    assert rect.bottom <= bottom and rect.right <= config.UI_ZONE_WIDTH
