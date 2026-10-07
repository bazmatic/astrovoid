"""The hunter's fire control: tracking a target's firing solution and holding fire until lined up."""
import json
import math
from unittest.mock import Mock

import pytest
import config
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from game_handlers.collision_handler import CollisionHandler
from hunter.fire_control import find_firing_solution
from hunter.jev_pilot import PILOT_QUESTIONS
from hunter.model import ACTIONS, FiringSolution, HunterSettings, PilotAction
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze

LINED_UP = FiringSolution(0.0, True)
SETTINGS = HunterSettings()


def urchin(pos):
    return Enemy(pos, 'static')


def ship_at(pos=(500, 500), heading=0.0):
    ship = HunterShip(pos)
    ship.angle = heading
    return ship


# --- the track control ---

def test_track_is_a_fourth_steering_choice():
    tracking = {name: action for name, action in ACTIONS.items() if name.startswith('track_')}
    assert len(tracking) == 4
    assert all(action.track and action.turn == 0 for action in tracking.values())
    assert not any(action.track for name, action in ACTIONS.items() if not name.startswith('track_'))
    assert ACTIONS['track_thrust_fire'] == PilotAction(0, True, True, True)


def test_pilot_is_offered_track():
    assert set(PILOT_QUESTIONS['turn']['criteria']) == {'left', 'none', 'right', 'track'}


@pytest.mark.parametrize('lead', [40.0, -40.0])
def test_tracking_swings_toward_the_solution_at_the_turn_rate(lead):
    ship = ship_at(heading=90.0)
    ship.step(1, ACTIONS['track_coast_hold'], FiringSolution(lead, False))
    assert ship.angle == pytest.approx(90.0 + math.copysign(ship.current_rotation_speed, lead))


@pytest.mark.parametrize('lead', [1.2, -0.4, 0.0])
def test_tracking_settles_exactly_on_the_solution(lead):
    ship = ship_at(heading=90.0)
    assert abs(lead) < ship.current_rotation_speed
    ship.step(1, ACTIONS['track_coast_hold'], FiringSolution(lead, False))
    assert ship.angle == pytest.approx(90.0 + lead)


def test_tracking_with_nothing_to_track_holds_the_heading():
    ship = ship_at(heading=90.0)
    ship.step(1, ACTIONS['track_coast_hold'], None)
    assert ship.angle == 90.0


def test_other_steering_ignores_the_solution():
    ship = ship_at(heading=90.0)
    ship.step(1, ACTIONS['none_coast_hold'], FiringSolution(40.0, False))
    assert ship.angle == 90.0


# --- holding fire until lined up ---

def test_no_shot_until_the_nose_is_lined_up():
    ship = ship_at()
    fire = ACTIONS['none_coast_fire']
    assert all(ship.step(1, fire, FiringSolution(15.0, False)) is None for _ in range(40))
    assert ship.step(1, fire, LINED_UP) is not None


def test_no_shot_without_a_target():
    ship = ship_at()
    assert all(ship.step(1, ACTIONS['none_coast_fire'], None) is None for _ in range(40))


def test_lined_up_but_trigger_released_does_not_fire():
    ship = ship_at()
    assert all(ship.step(1, ACTIONS['none_coast_hold'], LINED_UP) is None for _ in range(40))


def test_burst_pauses_when_the_aim_slips_and_resumes_when_it_returns():
    ship = ship_at()
    fire = ACTIONS['none_coast_fire']
    assert ship.step(1, fire, LINED_UP) is not None
    assert all(ship.step(1, fire, FiringSolution(9.0, False)) is None for _ in range(20))
    assert ship.step(1, fire, LINED_UP) is not None


def test_unfinished_burst_is_dropped_once_the_trigger_is_released_off_target():
    ship = ship_at()
    assert ship.step(1, ACTIONS['none_coast_fire'], LINED_UP) is not None
    ship.step(1, ACTIONS['none_coast_hold'], FiringSolution(9.0, False))
    assert all(ship.step(1, ACTIONS['none_coast_hold'], LINED_UP) is None for _ in range(40))


# --- finding the solution ---

def test_enemy_dead_ahead_is_on_target():
    solution = find_firing_solution(ship_at(), [urchin((700, 500))], maze(), SETTINGS)
    assert solution.lead_degrees == pytest.approx(0.0, abs=0.01)
    assert solution.on_target


@pytest.mark.parametrize('heading,lead', [(0.0, 30.0), (60.0, -30.0), (200.0, -170.0)])
def test_lead_is_measured_from_the_nose(heading, lead):
    target = (500 + 200 * math.cos(math.radians(30)), 500 + 200 * math.sin(math.radians(30)))
    solution = find_firing_solution(ship_at(heading=heading), [urchin(target)], maze(), SETTINGS)
    assert solution.lead_degrees == pytest.approx(lead, abs=0.01)
    assert not solution.on_target


def test_on_target_matches_the_width_of_the_enemy():
    """At 200 away an urchin is a few degrees wide: 2 off is a hit, 6 off is a miss."""
    enemy = urchin((700, 500))
    assert find_firing_solution(ship_at(heading=2.0), [enemy], maze(), SETTINGS).on_target
    assert not find_firing_solution(ship_at(heading=6.0), [enemy], maze(), SETTINGS).on_target


def test_nearest_enemy_is_chosen():
    near, far = urchin((500, 620)), urchin((800, 500))
    solution = find_firing_solution(ship_at(), [far, near], maze(), SETTINGS)
    assert solution.lead_degrees == pytest.approx(90.0, abs=0.01)


def test_enemy_behind_a_wall_is_not_a_target():
    world = maze()
    world.walls = [WallSegment((600, 0), (600, 1000), 3)]
    hidden, open_ground = urchin((700, 500)), urchin((500, 800))
    assert find_firing_solution(ship_at(), [hidden], world, SETTINGS) is None
    assert find_firing_solution(ship_at(), [hidden, open_ground], world, SETTINGS).lead_degrees == pytest.approx(90.0, abs=0.01)


def test_enemy_beyond_sensor_range_or_dead_is_not_a_target():
    reach = SETTINGS.sensor_cells * maze().cell_size_x
    assert find_firing_solution(ship_at(), [urchin((500 + reach + 50, 500))], maze(), SETTINGS) is None
    dead = urchin((700, 500))
    dead.active = False
    assert find_firing_solution(ship_at(), [dead], maze(), SETTINGS) is None
    assert find_firing_solution(ship_at(), [], maze(), SETTINGS) is None


def test_moving_enemy_is_led():
    enemy = urchin((700, 500))
    enemy.vy = 2.0
    solution = find_firing_solution(ship_at(), [enemy], maze(), SETTINGS)
    assert solution.lead_degrees > 5.0
    assert not solution.on_target


def test_solution_agrees_with_what_the_pilot_is_shown():
    ship, enemy, world = ship_at(heading=20.0), urchin((700, 560)), maze()
    enemy.vx = -1.0
    observation = HunterPerception().observe(ship, world, None, [enemy], [], ACTIONS['none_coast_hold'], 0, 1)
    shown = pilot_state(json.loads(observation.state_json))['visible_contacts'][0]['aim']
    solution = find_firing_solution(ship, [enemy], world, SETTINGS)
    assert solution.lead_degrees == pytest.approx(shown['lead_degrees_off_nose'], abs=0.06)
    assert solution.on_target == shown['on_target']


def test_pilot_is_told_it_is_tracking():
    ship, world = ship_at(), maze()
    observation = HunterPerception().observe(ship, world, None, [], [], ACTIONS['track_coast_hold'], 0, 1)
    assert pilot_state(json.loads(observation.state_json))['turning']['direction'] == 'track'


# --- the point of it all ---

@pytest.mark.parametrize('distance', [100, 200, 300])
@pytest.mark.parametrize('bearing', [0, 77, 160, 251])
def test_tracking_hunter_kills_a_static_urchin(distance, bearing, monkeypatch):
    """Held 'track and fire' must reliably destroy a stationary urchin from any angle."""
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 4000)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 4000)
    world = maze()
    ship = ship_at((2000, 2000), heading=0.0)
    angle = math.radians(bearing)
    enemy = urchin((2000 + math.cos(angle) * distance, 2000 + math.sin(angle) * distance))
    handler = CollisionHandler(Mock(), Mock(), Mock())
    shots = []
    for frame in range(10 * config.FPS):
        enemy.update(1.0, None, None)
        solution = find_firing_solution(ship, [enemy], world, SETTINGS)
        shot = ship.step(1, ACTIONS['track_coast_fire'], solution)
        if shot:
            shots.append(shot)
        for projectile in shots:
            if projectile.active:
                projectile.update(1.0)
                handler.handle_projectile_enemy_collisions(projectile, [enemy], [], [], [], [], [], [], [], [])
        if not enemy.active:
            break
    assert not enemy.active, f'urchin survived {len(shots)} shots'
    assert len(shots) <= 4 * config.STATIC_ENEMY_HIT_POINTS
