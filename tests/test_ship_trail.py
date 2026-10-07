"""The player's ship leaves a faint, fading trail so it is easy to find on screen."""
import pygame
import pytest

import config
from entities.ship import Ship

BACKGROUND = (5, 0, 15)
START = (200.0, 300.0)


def moving_ship(frames, speed=4.0):
    ship = Ship(START)
    for _ in range(frames):
        ship.vx, ship.vy = speed, 0.0
        ship.update(1.0)
    return ship


def draw(ship):
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    screen.fill((*BACKGROUND, 255))
    ship.draw(screen)
    return screen


def brightness(screen, x, y):
    return sum(screen.get_at((int(x), int(y)))[:3])


def test_trail_follows_the_ship_and_is_capped():
    ship = moving_ship(5)
    assert len(ship.trail) == 5
    assert ship.trail[0][0] < ship.trail[-1][0] <= ship.x
    ship = moving_ship(Ship.TRAIL_LENGTH * 3)
    assert len(ship.trail) == Ship.TRAIL_LENGTH


def test_trail_runs_out_when_the_ship_stops():
    ship = moving_ship(Ship.TRAIL_LENGTH)
    for _ in range(Ship.TRAIL_LENGTH + 1):
        ship.vx = ship.vy = 0.0
        ship.update(1.0)
    assert ship.trail == []


def test_new_ship_has_no_trail():
    ship = Ship(START)
    assert ship.trail == []
    screen = draw(ship)
    assert brightness(screen, START[0] - 40, START[1]) == sum(BACKGROUND)


def test_trail_is_drawn_behind_the_ship_and_fades_with_age():
    ship = moving_ship(Ship.TRAIL_LENGTH)
    screen = draw(ship)
    background = sum(BACKGROUND)
    newest = brightness(screen, ship.trail[-4][0], ship.y)
    middle = brightness(screen, ship.trail[len(ship.trail) // 2][0], ship.y)
    oldest = brightness(screen, ship.trail[1][0], ship.y)
    assert newest > middle > oldest >= background
    assert newest > background + 30
    # Nothing ahead of the ship
    assert brightness(screen, ship.x + 60, ship.y) == background


def test_trail_is_subtle_and_narrower_than_the_ship():
    ship = moving_ship(Ship.TRAIL_LENGTH)
    screen = draw(ship)
    behind_x = ship.trail[-6][0]
    # Dimmer than the ship's own color, so it never competes with the ship
    assert brightness(screen, behind_x, ship.y) < sum(config.COLOR_SHIP) * 0.6
    lit_rows = [y for y in range(250, 350) if brightness(screen, behind_x, y) > sum(BACKGROUND)]
    assert 1 <= len(lit_rows) <= ship.radius * 2


def test_drawing_the_trail_leaves_the_screen_opaque():
    screen = draw(moving_ship(Ship.TRAIL_LENGTH))
    assert pygame.mask.from_surface(screen, 254).count() == 800 * 600
