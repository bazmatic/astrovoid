"""The pilot chooses how long to burn: coast, a short pulse, the worked burn, or engine held on."""
import asyncio
import json
import math
from dataclasses import replace
from types import SimpleNamespace

import pytest
import config
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from entities.ship import Ship
from hunter.jev_pilot import PILOT_QUESTIONS, JevPilot, worked_burn
from hunter.model import ACTIONS, PULSE_FRAMES, FiringSolution
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze

FPS = config.FPS


def ship_at(pos=(2000, 2000), heading=0.0, velocity=(0.0, 0.0)):
    ship = HunterShip(pos)
    ship.angle = heading
    ship.vx, ship.vy = velocity
    return ship


def observe(ship, enemies=(), player=None, walls=(), action=ACTIONS['none_coast_hold']):
    world = maze()
    world.walls = [WallSegment(a, b, 3) for a, b in walls]
    return HunterPerception().observe(ship, world, player, list(enemies), [], action, 0, 1)


def reading(ship, **kwargs):
    return pilot_state(json.loads(observe(ship, **kwargs).state_json))


def decide(observation, turn, thrust, fire='hold'):
    class Client:
        async def system_one(self, **kwargs):
            return SimpleNamespace(choices={
                'turn': SimpleNamespace(choice=turn, confidence=.9),
                'thrust': SimpleNamespace(choice=thrust, confidence=.9),
                'fire': SimpleNamespace(choice=fire, confidence=.9)})
    return asyncio.run(JevPilot(Client()).decide(observation)).action


def burned(ship, action, frames=120, solution=None):
    """Frames of thrust the ship applies while this one decision is held."""
    before = ship.thrust_frames
    for _ in range(frames):
        ship.step(1, action, solution)
    return ship.thrust_frames - before


# --- the four settings ---

def test_engine_has_four_settings():
    assert set(PILOT_QUESTIONS['thrust']['criteria']) == {'coast', 'pulse', 'burn', 'thrust'}
    assert len(ACTIONS) == 5 * 4 * 2 == len(set(ACTIONS.values()))
    assert not ACTIONS['none_coast_hold'].thrust
    assert ACTIONS['none_pulse_hold'].burn_frames == PULSE_FRAMES
    assert ACTIONS['none_burn_hold'].worked_burn and not ACTIONS['none_thrust_hold'].worked_burn


def test_coast_burns_nothing_and_thrust_burns_until_replaced(monkeypatch):
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 100000)
    assert burned(ship_at(), ACTIONS['none_coast_hold']) == 0
    assert burned(ship_at(), ACTIONS['none_thrust_hold']) == 120


def test_pulse_is_one_short_burn():
    ship = ship_at()
    assert burned(ship, replace(ACTIONS['none_pulse_hold'])) == PULSE_FRAMES
    assert 0.05 <= PULSE_FRAMES / FPS <= 0.15


def test_every_pulse_decision_pulses_again():
    """Pulses repeat decision after decision, like a low throttle setting."""
    ship = ship_at()
    observation = observe(ship)
    total = 0
    for _ in range(3):
        total += burned(ship, decide(observation, 'none', 'pulse'), frames=27)
    assert total == 3 * PULSE_FRAMES


def test_pulse_works_while_tracking_and_steering():
    for steering in ('track', 'left', 'right', 'none'):
        ship = ship_at()
        assert burned(ship, replace(ACTIONS[f'{steering}_pulse_hold']), solution=FiringSolution(0.0, True)) == PULSE_FRAMES


# --- the worked burn ---

def test_burn_on_a_course_flies_the_navigation_burn():
    ship = ship_at((150, 500), heading=90.0)
    observation = observe(ship, player=Ship((450, 500)))
    course = pilot_state(json.loads(observation.state_json))['follow_player']['course']
    action = decide(observation, 'course', 'burn')
    assert action.burn_heading == course['burn_heading_degrees']
    assert action.burn_frames == pytest.approx(course['burn_seconds'] * FPS)
    assert burned(ship, action, frames=400) == math.ceil(course['burn_seconds'] * FPS)


def test_burn_with_nothing_to_burn_for_stays_off():
    ship = ship_at((150, 500))
    limit = reading(ship, player=Ship((450, 500)))['follow_player']['course']['speed_limit_metres_per_second']
    ship.vx = limit * 0.75 / FPS  # Already on course at a good speed
    action = decide(observe(ship, player=Ship((450, 500))), 'course', 'burn')
    assert action.burn_frames == 0.0
    assert burned(ship, action) == 0


def test_thrust_on_a_course_overrides_the_worked_length(monkeypatch):
    """Holding the engine on keeps burning along the course heading until the next decision."""
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 100000)
    ship = ship_at((150, 500))
    action = decide(observe(ship, player=Ship((450, 500))), 'course', 'thrust')
    assert action.burn_frames is None and action.burn_heading is not None
    assert burned(ship, action, frames=60) > 50


def test_burn_when_too_fast_is_the_braking_burn():
    ship = ship_at((300, 300), velocity=(3.0, 0.0))
    observation = observe(ship, walls=[((500, 0), (500, 1000))])
    brake = pilot_state(json.loads(observation.state_json))['motion']['brake']
    assert brake['speed_state'] == 'too_fast'
    action = decide(observation, 'course', 'burn')
    assert action.burn_heading == brake['burn_heading_degrees']
    assert action.burn_frames == pytest.approx(brake['burn_seconds'] * FPS)


# --- the combat burn ---

def test_no_engage_reading_without_an_enemy():
    assert reading(ship_at((500, 500)))['engage'] is None


def test_engage_reading_far_from_the_enemy_calls_for_a_closing_burn():
    engage = reading(ship_at((500, 500)), enemies=[Enemy((850, 500), 'static')])['engage']
    assert engage['range_state'] == 'far'
    assert engage['distance_metres'] == pytest.approx(350)
    assert engage['burn_needed'] and engage['burn_seconds'] > 0.2
    assert engage['target_closing_speed_metres_per_second'] > 0
    assert engage['holding_still']


def test_engage_reading_in_range_calls_for_no_burn():
    world_cell = maze().cell_size_x
    engage = reading(ship_at((500, 500)), enemies=[Enemy((500 + world_cell * 1.5, 500), 'static')])['engage']
    assert engage['range_state'] == 'in_range'
    assert engage['standoff_metres'] == pytest.approx(world_cell * 1.5)
    assert not engage['burn_needed'] and engage['burn_seconds'] == 0


def test_engage_reading_too_close():
    engage = reading(ship_at((500, 500)), enemies=[Enemy((560, 500), 'static')])['engage']
    assert engage['range_state'] == 'too_close' and not engage['burn_needed']


def test_already_closing_fast_enough_needs_no_burn():
    slow = reading(ship_at((500, 500)), enemies=[Enemy((850, 500), 'static')])['engage']
    target = slow['target_closing_speed_metres_per_second'] / FPS
    closing = reading(ship_at((500, 500), velocity=(target, 0.0)), enemies=[Enemy((850, 500), 'static')])['engage']
    assert closing['closing_speed_metres_per_second'] == pytest.approx(target * FPS, abs=0.5)
    assert not closing['burn_needed']
    assert not closing['holding_still']


def test_burn_while_tracking_flies_the_combat_burn():
    ship = ship_at((500, 500), heading=0.0)
    observation = observe(ship, enemies=[Enemy((850, 500), 'static')])
    engage = pilot_state(json.loads(observation.state_json))['engage']
    action = decide(observation, 'track', 'burn', 'fire')
    assert action.burn_frames == pytest.approx(engage['burn_seconds'] * FPS)
    length = math.ceil(engage['burn_seconds'] * FPS)
    assert burned(ship, action, frames=length, solution=FiringSolution(0.0, True)) == length
    # ... which leaves the ship closing at about the speed the reading aimed for
    closing = ship.vx * FPS
    assert burned(ship, action, frames=200, solution=FiringSolution(0.0, True)) == 0
    assert closing == pytest.approx(engage['target_closing_speed_metres_per_second'], rel=0.1)


def test_combat_burn_waits_for_the_nose_to_come_round():
    """Thrust goes along the nose, so the combat burn holds off until the nose is near the enemy."""
    ship = ship_at((500, 500), heading=120.0)
    observation = observe(ship, enemies=[Enemy((850, 500), 'static')])
    action = decide(observation, 'track', 'burn', 'fire')
    assert burned(ship, action, frames=10, solution=FiringSolution(-120.0, False)) == 0
    ship.angle = 5.0
    assert burned(ship, action, frames=10, solution=FiringSolution(-5.0, False)) == 10


def test_worked_burn_priority_is_brake_then_enemy_then_course():
    ahead = [((700, 0), (700, 1000))]
    enemy, player = Enemy((620, 560), 'static'), Ship((450, 800))
    too_fast = reading(ship_at((500, 500), velocity=(3.0, 0.0)), enemies=[enemy], player=player, walls=ahead)
    assert worked_burn(too_fast)['burn_heading_degrees'] == too_fast['motion']['brake']['burn_heading_degrees']
    fighting = reading(ship_at((500, 500)), enemies=[enemy], player=player)
    assert worked_burn(fighting)['burn_seconds'] == fighting['engage']['burn_seconds']
    following = reading(ship_at((500, 500)), player=player)
    assert worked_burn(following) == following['follow_player']['course']


# --- the rules ---

def test_rules_say_when_to_use_each_setting():
    thrust = PILOT_QUESTIONS['thrust']
    assert thrust['criteria']['burn'].startswith('brake.speed_state is too_fast;')
    assert 'engage.burn_needed' in thrust['criteria']['burn']
    assert 'holding_still' in thrust['criteria']['pulse']
    for name in ('coast', 'pulse', 'thrust'):
        assert 'not too_fast' in thrust['criteria'][name]
    assert '`engage`' in thrust['instructions']
