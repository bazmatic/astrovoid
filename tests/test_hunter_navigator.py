"""The hunter's navigator: flying a course decision's burn heading and burn length."""
from dataclasses import replace

import pytest
from entities.hunter_ship import HunterShip
from hunter.model import ACTIONS


def ship_at(heading=0.0):
    ship = HunterShip((2000, 2000))
    ship.angle = heading
    return ship


def course(heading, frames, thrust=True, reference=0):
    action = ACTIONS['course_thrust_hold' if thrust else 'course_coast_hold']
    return replace(action, burn_heading=heading, burn_frames=frames, burn_reference=reference)


def test_course_is_a_fifth_steering_choice():
    flying = {name: action for name, action in ACTIONS.items() if name.startswith('course_')}
    assert len(flying) == 8
    assert all(action.course and not action.track and action.turn == 0 for action in flying.values())


def test_nose_swings_onto_the_burn_heading_and_stops_there():
    ship = ship_at(heading=10.0)
    action = course(100.0, 0.0)
    ship.step(1, action)
    assert ship.angle == pytest.approx(10.0 + ship.current_rotation_speed)
    for _ in range(80):
        ship.step(1, action)
    assert ship.angle == pytest.approx(100.0)


def test_swings_the_short_way_round():
    ship = ship_at(heading=10.0)
    ship.step(1, course(300.0, 0.0))
    assert ship.angle == pytest.approx(10.0 - ship.current_rotation_speed)


def test_engine_waits_until_the_nose_is_lined_up():
    ship = ship_at(heading=0.0)
    action = course(90.0, 30.0)
    frames_to_align = round((90.0 - HunterShip.BURN_ALIGNMENT_DEGREES) / ship.current_rotation_speed)
    for _ in range(frames_to_align - 2):
        ship.step(1, action)
        assert not ship.pilot_thrusting
    for _ in range(6):
        ship.step(1, action)
    assert ship.pilot_thrusting
    # All of the push went along the burn heading, give or take the alignment tolerance
    assert ship.vy > 0 and abs(ship.vx) < ship.vy * 0.15


def test_engine_cuts_when_the_burn_is_complete():
    ship = ship_at(heading=0.0)
    action = course(0.0, 12.0)
    burned = sum(1 for _ in range(60) if ship.step(1, action) is None and ship.pilot_thrusting)
    assert burned == 12
    assert ship.thrust_frames == 12


def test_no_burn_when_the_course_needs_none():
    ship = ship_at()
    action = course(0.0, 0.0)
    for _ in range(30):
        ship.step(1, action)
    assert ship.vx == 0.0 and ship.thrust_frames == 0


def test_coasting_on_a_course_still_turns_but_never_burns():
    ship = ship_at()
    action = course(40.0, 30.0, thrust=False)
    for _ in range(60):
        ship.step(1, action)
    assert ship.angle == pytest.approx(40.0)
    assert ship.thrust_frames == 0


def test_each_decision_brings_its_own_burn():
    ship = ship_at()
    first = course(0.0, 5.0)
    for _ in range(20):
        ship.step(1, first)
    assert ship.thrust_frames == 5
    second = course(0.0, 5.0, reference=ship.thrust_frames)
    for _ in range(20):
        ship.step(1, second)
    assert ship.thrust_frames == 10


def test_thrust_since_the_course_was_worked_out_is_not_burned_twice():
    """A course worked out before an earlier burn finished must not repeat that burn."""
    ship = ship_at()
    first = course(0.0, 8.0)
    for _ in range(20):
        ship.step(1, first)
    # Worked out when the ship had burned nothing, asking for the same 8 frames
    stale = course(0.0, 8.0, reference=0)
    for _ in range(20):
        ship.step(1, stale)
    assert ship.thrust_frames == 8


def test_course_without_a_worked_course_leaves_the_controls_alone():
    ship = ship_at(heading=30.0)
    for _ in range(10):
        ship.step(1, ACTIONS['course_thrust_hold'])
    assert ship.angle == 30.0
    assert ship.thrust_frames == 10
