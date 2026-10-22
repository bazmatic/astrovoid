"""The Creature owns its flight: steering precedes the shot, integration follows it."""
import math

import pytest

from creatures.traits.burst_fire import BurstFire
from creatures.traits.combat import Gun
from creatures.traits.energy import Energy
from creatures.traits.propulsion import Thrusters
from tests.creature_parts import creature, encounter


def make():
    c = creature([Energy(), Thrusters(speedShare=1, thrust=0.1, turnRate=5, mode='hunter'),
                  BurstFire(), Gun(cadence='burst', aimMode='nose')])
    c.angle = 0
    enc = encounter(c)
    enc.ready()
    return c, enc


def test_steering_and_shooting_precede_movement():
    c, enc = make()
    c.vx = 1
    c.controls.turn = 1
    c.controls.fire = c.controls.on_target = True
    x, y = c.get_pos()
    enc.step(1)
    shot = enc.world.projectiles[0]
    assert shot.angle == 5
    assert shot.x == pytest.approx(x + (c.radius + 5) * math.cos(math.radians(5)))
    assert c.x > x


def test_a_held_burn_does_not_restart_its_budget():
    c, enc = make()
    c.controls.decision_token = object()
    c.controls.thrust = True
    c.controls.burn_frames = 2
    for _ in range(10):
        enc.step(1)
    assert c.thrust_frames == 2
    c.controls.decision_token = object()
    enc.step(1)
    assert c.thrust_frames == 3


def test_a_course_turns_before_burning_and_tracks_the_reference():
    c, enc = make()
    c.controls.decision_token = object()
    c.controls.course = c.controls.thrust = True
    c.controls.burn_heading = 90
    c.controls.burn_frames = 2
    enc.step(1)
    assert c.angle == 5
    assert c.thrust_frames == 0
    c.angle = 90
    c.thrust_frames = 1
    c.controls.burn_reference = 0
    c.controls.decision_token = object()
    for _ in range(4):
        enc.step(1)
    assert c.thrust_frames == 2
