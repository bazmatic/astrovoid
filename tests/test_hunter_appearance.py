"""The hunter is drawn as an arrowhead so its front and back are obvious."""
import math

import pygame
import pytest
from entities.hunter_ship import HunterShip
from hunter.model import HunterSettings

POS = (200.0, 200.0)
HEADINGS = [0.0, 45.0, 90.0, 160.0, 233.0, 301.0]


def ship_at(heading):
    ship = HunterShip(POS)
    ship.angle = heading
    return ship


def along(ship, point):
    """How far a point lies ahead of the ship's centre along its heading (negative is behind)."""
    nose = math.radians(ship.angle)
    return (point[0] - ship.x) * math.cos(nose) + (point[1] - ship.y) * math.sin(nose)


def across(ship, point):
    nose = math.radians(ship.angle)
    return -(point[0] - ship.x) * math.sin(nose) + (point[1] - ship.y) * math.cos(nose)


def drawn(ship):
    """Opaque pixels the ship draws, as {(x, y): (r, g, b)}."""
    screen = pygame.Surface((400, 400), pygame.SRCALPHA)
    ship.draw(screen)
    mask = pygame.mask.from_surface(screen, 254)
    return {(x, y): tuple(screen.get_at((x, y)))[:3]
            for x in range(150, 250) for y in range(150, 250) if mask.get_at((x, y))}


@pytest.mark.parametrize('heading', HEADINGS)
def test_nose_is_the_point_furthest_ahead(heading):
    ship = ship_at(heading)
    nose, right_wing, notch, left_wing = ship.outline()
    assert along(ship, nose) == pytest.approx(max(along(ship, p) for p in ship.outline()))
    assert across(ship, nose) == pytest.approx(0.0, abs=1e-6)
    assert along(ship, nose) > ship.radius


@pytest.mark.parametrize('heading', HEADINGS)
def test_tail_is_notched_between_swept_back_wings(heading):
    ship = ship_at(heading)
    nose, right_wing, notch, left_wing = ship.outline()
    # Wing tips trail behind the notch, one each side
    assert along(ship, right_wing) < along(ship, notch) < 0
    assert along(ship, left_wing) == pytest.approx(along(ship, right_wing))
    assert across(ship, right_wing) == pytest.approx(-across(ship, left_wing))
    assert across(ship, right_wing) > 0
    assert across(ship, notch) == pytest.approx(0.0, abs=1e-6)


def test_longer_than_wide():
    ship = ship_at(0.0)
    nose, right_wing, notch, left_wing = ship.outline()
    length = along(ship, nose) - along(ship, right_wing)
    assert length > 2 * across(ship, right_wing) * 1.15


@pytest.mark.parametrize('heading', HEADINGS)
def test_front_is_brighter_than_the_back(heading):
    ship = ship_at(heading)
    front, back = [], []
    for point, color in drawn(ship).items():
        # Compare the green body only, leaving out the amber engine mark
        if color[0] > color[1]:
            continue
        (front if along(ship, point) > ship.radius * 0.3 else back).append(sum(color))
    assert front and back
    assert sum(front) / len(front) > sum(back) / len(back) * 1.25


@pytest.mark.parametrize('heading', HEADINGS)
def test_engine_mark_sits_at_the_tail(heading):
    ship = ship_at(heading)
    amber = [point for point, color in drawn(ship).items() if color[0] > color[1] > color[2]]
    assert amber
    assert all(along(ship, point) < 0 for point in amber)
    assert all(abs(across(ship, point)) < ship.radius * 0.6 for point in amber)


def test_engine_mark_brightens_under_thrust():
    def engine_glow(thrusting):
        ship = ship_at(0.0)
        ship.pilot_thrusting = thrusting
        ship.draw_thrust_plume = lambda *args, **kwargs: None  # Measure the mark, not the flame
        return max(sum(color) for color in drawn(ship).values() if color[0] > color[1] > color[2])

    assert engine_glow(True) > engine_glow(False) * 1.3


def test_cockpit_sits_forward_of_centre():
    ship = ship_at(0.0)
    assert along(ship, ship.cockpit()) > ship.radius * 0.25


def test_stays_green_and_flashes_when_hit():
    ship = HunterShip(POS, HunterSettings(indestructible=False))
    ship.angle = 0.0
    calm = drawn(ship)
    greens = [c for c in calm.values() if c[1] > c[0] and c[1] > c[2]]
    assert len(greens) > len(calm) * 0.7
    ship.immunity_remaining = 0.075  # A frame on the bright half of the flash
    assert drawn(ship) != calm


def test_inactive_draws_nothing():
    ship = ship_at(0.0)
    ship.active = False
    assert drawn(ship) == {}
