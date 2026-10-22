"""Headless drawing equivalence while the old hunter renderer is still available."""
import random

import numpy as np
import pygame
import pytest

from entities.hunter_ship import HunterShip
from entities.hunter_ship_body import HunterShipBody
from tests.creature_parts import creature


@pytest.mark.parametrize('angle', [0, 45, 137, 290])
@pytest.mark.parametrize('burning', [False, True])
@pytest.mark.parametrize('immunity', [0.0, 0.25])
def test_the_standalone_body_draws_the_same_pixels(angle, burning, immunity):
    old = HunterShip((400, 400))
    new = creature([], pos=(400, 400))
    new.radius = old.radius
    new.body = HunterShipBody(new)
    for ship in (old, new):
        ship.angle = angle
        ship.pilot_thrusting = burning
        ship.immunity_remaining = immunity
    a, b = pygame.Surface((800, 800)), pygame.Surface((800, 800))
    random.seed(7)
    old.draw(a)
    random.seed(7)
    new.draw(b)
    np.testing.assert_array_equal(pygame.surfarray.array3d(a), pygame.surfarray.array3d(b))


@pytest.mark.parametrize('timer', [4, 20, 45])
def test_the_standalone_body_draws_the_same_death(timer):
    old = HunterShip((400, 400))
    new = creature([], pos=(400, 400))
    new.radius = old.radius
    new.body = HunterShipBody(new)
    for ship in (old, new):
        ship.die()
        ship.death_timer = timer
    a, b = pygame.Surface((800, 800)), pygame.Surface((800, 800))
    old.draw_death(a)
    new.draw_death(b)
    np.testing.assert_array_equal(pygame.surfarray.array3d(a), pygame.surfarray.array3d(b))
