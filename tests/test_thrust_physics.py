"""The ship physics any thruster body shares: thrust, coasting, the screen edges, sweeping into walls, turning."""
import random
from types import SimpleNamespace

import pytest

import config
from tests.hunter_fixture import HunterRig
from physics.thrust import apply_thrust, cap_speed, coast, sweep_walls, turn_toward


def body(**fields):
    values = dict(x=300.0, y=300.0, vx=0.0, vy=0.0, angle=0.0, radius=10.0, prev_x=300.0, prev_y=300.0)
    values.update(fields)
    return SimpleNamespace(**values)


def test_thrust_adds_force_along_the_heading_and_caps_speed():
    b = body(angle=90.0)
    for _ in range(4):
        apply_thrust(b, 0.5, 1.0)
    assert b.vx == pytest.approx(0.0, abs=1e-9) and b.vy == pytest.approx(1.0)


def test_coast_slows_moves_and_bounces_off_an_edge():
    b = body(x=9.0, vx=-2.0)
    assert coast(b, 1.0, config.SHIP_FRICTION) == 1
    assert b.prev_x == 9.0
    assert b.vx > 0 and b.x == b.radius


def test_cap_speed_scales_down_only_what_is_too_fast():
    fast, slow = body(vx=3.0, vy=4.0), body(vx=0.3, vy=0.4)
    cap_speed(fast, 1.0)
    cap_speed(slow, 1.0)
    assert (fast.vx, fast.vy) == pytest.approx((0.6, 0.8)) and (slow.vx, slow.vy) == (0.3, 0.4)


def test_sweep_walls_stops_a_fast_body_at_the_wall():
    b = body(prev_x=100.0, x=200.0, vx=100.0)
    assert sweep_walls(b, [((150.0, 0.0), (150.0, 600.0))])
    assert b.x < 150.0 and b.vx < 0


def test_turn_toward_snaps_within_one_step_and_turns_otherwise():
    for start, heading, expected in ((0.0, 3.0, 3.0), (0.0, 90.0, 5.0), (0.0, 270.0, 355.0)):
        b = body(angle=start)
        turn_toward(b, heading, 5.0)
        assert b.angle == pytest.approx(expected)


def test_the_ships_fly_as_before():
    """A hunter turning and thrusting round a box ends exactly where it did before the physics moved out."""
    box = [((100.0, 100.0), (500.0, 100.0)), ((500.0, 100.0), (500.0, 500.0)),
           ((500.0, 500.0), (100.0, 500.0)), ((100.0, 500.0), (100.0, 100.0))]
    random.seed(0)
    ship = HunterRig((300.0, 300.0))
    hits = 0
    for frame in range(240):
        from hunter.model import PilotAction
        ship.step(1.0, PilotAction(1 if frame % 3 == 0 else 0, frame % 40 < 30, False))
        hits += ship.check_wall_collision(box)
    assert (ship.x, ship.y, ship.vx, ship.vy, ship.angle, len(ship.thrust_particles), hits) == (
        308.6787883735199, 373.9216601532574, -2.7576273993144405, -1.2225346510362698, 200.0, 4, 2)
