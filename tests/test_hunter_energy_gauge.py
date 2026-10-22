"""The hunter's energy gauge: a small HUD bar, shown while a hunter flies, never drawn beside the ship."""
import pygame
import pytest
from rendering.ui_elements import UIElementRenderer
from tests.test_hunter_integration import game   # noqa: F401 - a real Game (pytest fixture)

FILL_GREEN = (120, 255, 90)


def flying(ship):
    """Just enough of a hunter flight for the game to see a hunter: it reads the flight's ship."""
    from types import SimpleNamespace
    return SimpleNamespace(ship=ship, close=lambda: None)


def draw(energy):
    pygame.init()
    screen = pygame.Surface((200, 200))
    bar = UIElementRenderer.draw_energy_gauge(screen, 100, 100, energy, 'x/y')
    return screen, bar


def lit_pixels(screen, bar, color):
    return sum(1 for x in range(bar.left, bar.right) if screen.get_at((x, bar.centery))[:3] == color)


@pytest.mark.parametrize('energy', [1.0, 0.75, 0.5])
def test_the_bar_fills_in_proportion_to_the_energy(energy):
    screen, bar = draw(energy)
    colour = UIElementRenderer._calculate_percentage_color(
        energy, high_color=FILL_GREEN, medium_color=(255, 190, 70), low_color=(255, 90, 90))
    lit = lit_pixels(screen, bar, colour)
    assert lit == pytest.approx(bar.width * energy, abs=3)


def test_an_empty_gauge_shows_no_fill_and_energy_is_clamped():
    screen, bar = draw(0.0)
    assert lit_pixels(screen, bar, FILL_GREEN) == 0
    screen, bar = draw(2.5)
    assert lit_pixels(screen, bar, FILL_GREEN) == pytest.approx(bar.width, abs=3)


def test_the_bar_turns_amber_then_red_as_energy_runs_low():
    def bar_colour(energy):
        screen, bar = draw(energy)
        return screen.get_at((bar.left + 3, bar.centery))[:3]
    assert bar_colour(0.9) == FILL_GREEN
    assert bar_colour(0.4) == (255, 190, 70)
    assert bar_colour(0.1) == (255, 90, 90)


def test_there_is_no_reading_without_a_hunter(game):
    game.hunter_flight = None
    assert game._hunter_energy_reading() is None


def test_the_reading_is_the_hunters_energy_and_its_most_while_it_flies(game):
    from dataclasses import replace
    from tests.hunter_fixture import HunterRig
    from hunter.model import HunterSettings
    game.hunter_flight = flying(HunterRig((300.0, 300.0), replace(HunterSettings(), indestructible=False, health=10)))
    assert game._hunter_energy_reading() == (10, 10)
    game.hunter.take_damage()
    assert game._hunter_energy_reading() == (9, 10)
    game.hunter.active = False
    assert game._hunter_energy_reading() is None


def test_the_gauge_is_drawn_in_the_hud_not_beside_the_ship(game):
    from dataclasses import replace
    from tests.hunter_fixture import HunterRig
    from hunter.model import HunterSettings
    import config
    game.hunter_flight = flying(HunterRig((600.0, 400.0), replace(HunterSettings(), indestructible=False, health=10)))
    pygame.init()
    game.screen = pygame.Surface((1352, 878))
    game.screen.fill((0, 0, 0))
    game._draw_hunter_energy()
    drawn = [(x, y) for x in range(game.screen.get_width()) for y in range(game.screen.get_height())
             if game.screen.get_at((x, y))[:3] != (0, 0, 0)]
    assert drawn
    assert all(x < config.UI_ZONE_WIDTH for x, _ in drawn)                 # inside the left HUD panel
    assert not any(abs(x - game.hunter.x) < 60 and abs(y - game.hunter.y) < 60 for x, y in drawn)


def test_the_gauge_sits_below_whatever_is_above_it_in_the_panel(game):
    from dataclasses import replace
    from tests.hunter_fixture import HunterRig
    from hunter.model import HunterSettings
    game.hunter_flight = flying(HunterRig((600.0, 400.0), replace(HunterSettings(), indestructible=False, health=10)))
    pygame.init()
    game.screen = pygame.Surface((1352, 878))
    game.screen.fill((0, 0, 0))
    game._draw_hunter_energy(below=790)
    drawn = [y for x in range(200) for y in range(878) if game.screen.get_at((x, y))[:3] != (0, 0, 0)]
    assert drawn and min(drawn) > 790 and max(drawn) < 878
