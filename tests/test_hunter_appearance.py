"""The hunter is drawn as a fish with a trailing tail, so its front and back are obvious."""
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
    outline = ship.outline()
    nose = outline[0]
    assert along(ship, nose) == pytest.approx(max(along(ship, p) for p in outline))
    assert across(ship, nose) == pytest.approx(0.0, abs=1e-6)
    assert along(ship, nose) > ship.radius


@pytest.mark.parametrize('heading', HEADINGS)
def test_the_body_is_symmetric_and_the_eyes_sit_forward_on_either_side(heading):
    ship = ship_at(heading)
    left, right = ship.eyes()
    assert along(ship, left) == pytest.approx(along(ship, right))
    assert across(ship, left) == pytest.approx(-across(ship, right))
    assert along(ship, left) > ship.radius * 0.5 and across(ship, left) != 0
    assert all(abs(across(ship, p)) < ship.radius for p in ship.outline())


def test_longer_than_wide():
    ship = ship_at(0.0)
    outline = ship.outline()
    length = max(along(ship, p) for p in outline) - min(along(ship, p) for p in outline)
    width = max(across(ship, p) for p in outline) - min(across(ship, p) for p in outline)
    assert length > width * 1.5


def segment_lengths(ship):
    tail = ship._tail
    return [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(tail, tail[1:])]


@pytest.mark.parametrize('heading', HEADINGS)
def test_a_new_tail_trails_straight_out_behind_the_body(heading):
    ship = ship_at(heading)
    ship._drag_tail(snap=True)
    assert all(along(ship, p) < along(ship, ship._tail[0]) + 1e-6 for p in ship._tail[1:])
    assert along(ship, ship._tail[0]) < 0
    assert along(ship, ship._tail[-1]) < -ship.radius * 1.5


def test_the_tail_keeps_its_segment_lengths_while_the_ship_turns_and_moves():
    from hunter.model import PilotAction
    ship = ship_at(0.0)
    expected = None
    for step in range(120):
        ship.step(1.0, PilotAction(turn=-1 if (step // 6) % 2 == 0 else 1, thrust=True, fire=False), None)
        lengths = segment_lengths(ship)
        expected = expected or lengths
        assert lengths == pytest.approx(expected, rel=1e-6)
    assert expected[0] == pytest.approx(ship.radius * ship.TAIL_SEGMENT)


def test_the_tail_lags_a_turn_and_then_catches_up():
    ship = ship_at(0.0)
    ship._drag_tail(snap=True)
    ship.angle = 90.0                         # the ship snaps a quarter turn; the tail has not followed yet
    ship._drag_tail()
    tip = ship._tail[-1]
    assert abs(across(ship, tip)) > ship.radius * 0.3              # swung out to the side of the new heading
    for _ in range(400):
        ship._drag_tail()
    assert along(ship, ship._tail[-1]) < -ship.radius * 1.5        # settled behind the body again


def test_the_tail_whips_back_and_forth_when_the_ship_flips_left_and_right():
    from hunter.model import PilotAction
    ship = ship_at(0.0)
    ship.rotation_speed_multiplier = 1.0
    sides = []
    for step in range(180):
        ship.step(1.0, PilotAction(turn=-1 if (step // 6) % 2 == 0 else 1, thrust=False, fire=False), None)
        sides.append(across(ship, ship._tail[-1]))
    assert max(sides) > ship.radius * 0.2 and min(sides) < -ship.radius * 0.2


def test_a_jump_does_not_stretch_the_tail_across_the_screen():
    ship = ship_at(0.0)
    ship._drag_tail(snap=True)
    ship.x, ship.y = ship.x + 900.0, ship.y + 400.0                # a respawn
    ship._drag_tail()
    assert max(segment_lengths(ship)) < ship.radius * 1.5
    assert math.hypot(ship._tail[0][0] - ship.x, ship._tail[0][1] - ship.y) < ship.radius * 2


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
