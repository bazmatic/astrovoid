import json
from dataclasses import replace

import numpy as np
import pygame
import pytest

import creatures
from entities.hunter_ship import HunterShip
from hunter.flight import HunterFlight, NeuralPilot, WorkerPilot
from hunter.model import ACTIONS, HunterSettings, PilotDecision, PilotResult
from hunter.neural.policy import random_policy
from hunter.senses import SENSE_SIZE
from maze.config import MazeComplexity
from maze.generator import Maze
from tests.test_hunter_controller import Worker


class Surroundings:
    """Plain surroundings for a test: lists the test can change between frames."""

    def __init__(self, maze, enemies=(), threats=(), pickups=(), friend=None):
        self.maze = maze
        self.enemy_list, self.threat_list, self.pickup_list = list(enemies), list(threats), list(pickups)
        self.friend_ship = friend

    def enemies(self):
        return self.enemy_list

    def threats(self):
        return self.threat_list

    def pickups(self):
        return self.pickup_list

    def friend(self):
        return self.friend_ship


@pytest.fixture
def maze():
    pygame.init()
    pygame.display.set_mode((320, 240))
    return Maze(1, complexity=MazeComplexity.EMPTY, grid_size=8)


def cell(maze, col, row):
    return maze.position_calculator.grid_center_to_screen(col, row)


def rules_flight(maze, enemies=(), settings=HunterSettings()):
    now = [10.0]
    worker = Worker()
    flight = HunterFlight(HunterShip(cell(maze, 2, 3), settings), WorkerPilot(worker, lambda: now[0]),
                          Surroundings(maze, enemies))
    return flight, worker, now


def decide(worker, action):
    """Answer the worker's last observation with `action`."""
    sent = worker.sent[-1]
    worker.result = PilotResult(sent.generation, sent.snapshot_at, sent.snapshot_at, PilotDecision(action))


def test_the_pilot_is_shown_the_surroundings_as_they_are_when_it_looks(maze):
    flight, worker, _ = rules_flight(maze)
    enemy = creatures.build('static', cell(maze, 4, 3))
    flight.surroundings.enemy_list.append(enemy)          # arrives after the flight was built
    flight.fly(1.0)
    contacts = json.loads(worker.sent[-1].state_json)['visible_contacts']
    assert [c['allegiance'] for c in contacts] == ['enemy']


def test_the_ship_flies_the_pilots_decision(maze):
    flight, worker, _ = rules_flight(maze)
    flight.fly(1.0)
    assert flight.status == 'waiting' and not flight.ship.vx
    decide(worker, ACTIONS['none_thrust_hold'])
    flight.fly(1.0)
    assert flight.status == 'active' and flight.ship.vx > 0


def test_a_burst_is_dropped_once_the_pilot_is_not_active_even_with_a_target_in_the_sights(maze):
    flight, worker, _ = rules_flight(maze, enemies=[creatures.build('static', cell(maze, 4, 3))])
    flight.ship.angle = 0.0                              # nose on the enemy: the burst would carry on alone
    flight.ship.burst_remaining, flight.ship.fire_remaining = 3, 0.0
    assert flight.fly(1.0) == []                         # no decision yet: the pilot is not behind the trigger
    assert flight.status != 'active' and flight.ship.burst_remaining == 0


def test_pausing_cuts_the_engine_drops_the_burst_and_forgets_the_pending_decision(maze):
    flight, worker, _ = rules_flight(maze)
    flight.fly(1.0)
    generation = flight.controller.generation
    flight.ship.pilot_thrusting, flight.ship.burst_remaining = True, 3
    flight.pause()
    assert not flight.ship.pilot_thrusting and flight.ship.burst_remaining == 0
    assert flight.controller.generation != generation and not worker.busy


def test_a_destroyed_hunter_does_not_fly_and_its_pilot_stops(maze):
    flight, worker, _ = rules_flight(maze)
    flight.ship.active = False
    at = flight.ship.get_pos()
    assert flight.fly(1.0) == []
    assert flight.controller.closed and not worker.sent and flight.ship.get_pos() == at


def test_the_pilot_sees_as_far_as_the_flights_settings_allow(maze):
    ranges = []
    for fraction in (0.2, 0.8):
        flight, worker, _ = rules_flight(maze, settings=replace(HunterSettings(), sensor_range_fraction=fraction))
        flight.fly(1.0)
        ranges.append(json.loads(worker.sent[-1].state_json)['sensor_range'])
    assert ranges[1] == pytest.approx(ranges[0] * 4)


def test_listeners_hear_every_senses_the_neural_pilot_is_shown_until_the_flight_closes(maze):
    flight = HunterFlight(HunterShip(cell(maze, 2, 3)), NeuralPilot(random_policy(1), decision_frames=3),
                          Surroundings(maze, [creatures.build('static', cell(maze, 4, 3))]))
    heard = []
    flight.on_observed(heard.append)
    for _ in range(6):
        flight.fly(1.0)
    assert len(heard) == 2 and all(isinstance(s, np.ndarray) and s.shape == (SENSE_SIZE,) for s in heard)
    flight.close()
    flight.fly(1.0)
    assert len(heard) == 2 and flight.controller.closed


def test_fire_control_only_aims_at_live_enemies(maze):
    flight, worker, _ = rules_flight(maze)
    ahead = creatures.build('static', cell(maze, 4, 3))
    flight.ship.angle = 0.0                              # nose towards the enemy
    flight.surroundings.enemy_list.append(ahead)
    flight.fly(1.0)
    decide(worker, ACTIONS['none_coast_fire'])
    ahead.active = False
    assert flight.fly(1.0) == []
    ahead.active = True
    flight.ship.fire_remaining = 0.0
    assert flight.fly(1.0)


def sealed_neural_flight(maze, angle):
    """A neural hunter at (2, 3) walled in by blocks on all four sides, an enemy at (5, 3), its trigger held."""
    from hunter.model import PilotAction
    for col, row in ((1, 3), (3, 3), (2, 2), (2, 4)):
        maze.grid[row][col] = 1
    maze.rebuild_walls()
    ship = HunterShip(cell(maze, 2, 3))
    ship.angle, ship.fire_remaining = angle, 0.0
    flight = HunterFlight(ship, NeuralPilot(random_policy(1), decision_frames=1),
                          Surroundings(maze, [creatures.build('static', cell(maze, 5, 3))]))
    fire = PilotAction(0, False, True)

    def fly():
        flight.controller.override = fire
        return flight.fly(1.0)
    return flight, fly


def test_with_no_enemy_in_sight_the_neural_hunter_fires_along_its_nose(maze):
    _, fly = sealed_neural_flight(maze, angle=180.0)         # nose west, on a wall, the enemy out of sight
    assert any(fly() for _ in range(3))


def test_with_an_enemy_in_sight_fire_control_still_holds_the_shot_until_lined_up(maze):
    from hunter.model import PilotAction
    ship = HunterShip(cell(maze, 2, 3))
    ship.angle, ship.fire_remaining = 90.0, 0.0              # nose south, the enemy due east in plain sight and reach
    flight = HunterFlight(ship, NeuralPilot(random_policy(1), decision_frames=1),
                          Surroundings(maze, [creatures.build('static', cell(maze, 4, 3))]))
    shots = []
    for _ in range(3):
        flight.controller.override = PilotAction(0, False, True)
        shots.append(flight.fly(1.0))
    assert not any(shots)


def test_the_ship_counts_its_shots(maze):
    flight, fly = sealed_neural_flight(maze, angle=180.0)
    fired = sum(len(fly() or []) > 0 for _ in range(3))
    assert flight.ship.shots_fired == fired > 0
