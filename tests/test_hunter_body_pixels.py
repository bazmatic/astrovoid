"""Headless drawing equivalence while the old hunter renderer is still available."""
import random
import hashlib
import json
from pathlib import Path

import numpy as np
import pygame
import pytest

from entities.hunter_ship_body import HunterShipBody
from tests.creature_parts import creature


@pytest.mark.parametrize('angle', [0, 45, 137, 290])
@pytest.mark.parametrize('burning', [False, True])
@pytest.mark.parametrize('immunity', [0.0, 0.25])
def test_the_standalone_body_draws_the_same_pixels(angle, burning, immunity):
    new = creature([], pos=(400, 400))
    new.radius = 8
    new.body = HunterShipBody(new)
    new.angle, new.pilot_thrusting, new.immunity_remaining = angle, burning, immunity
    surface = pygame.Surface((800, 800))
    random.seed(7)
    new.draw(surface)
    frozen = json.loads((Path(__file__).with_name('fixtures') / 'hunter-stage6-pixels.json').read_text())
    assert hashlib.sha256(pygame.surfarray.array3d(surface).tobytes()).hexdigest() == frozen[f'{angle}/{burning}/{immunity}']



@pytest.mark.parametrize('timer', [4, 20, 45])
def test_the_ship_breakup_matches_its_visual_snapshot(timer):
    new = creature([], pos=(400, 400))
    new.radius = 8
    new.body = HunterShipBody(new)
    new.angle = 0
    new.die()
    new.death_timer = timer
    surface = pygame.Surface((800, 800))
    new.draw_death(surface)
    frozen = json.loads((Path(__file__).with_name('fixtures') / 'hunter-stage6-pixels.json').read_text())
    assert hashlib.sha256(pygame.surfarray.array3d(surface).tobytes()).hexdigest() == frozen[f'death/{timer}']
