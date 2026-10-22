"""Flight traces captured at ffc8d91: refactoring must preserve the trained simulation."""
from dataclasses import replace
from pathlib import Path
import random

import config
import numpy as np

from tests.hunter_fixture import HunterRig
from hunter.model import ACTIONS, FiringSolution, HunterSettings, NEUTRAL, PilotAction
from maze.wall_segment import WallSegment
from hunter.senses import FEATURE_NAMES
from tests.test_senses import sense, world

FIXTURE = Path(__file__).with_name('fixtures') / 'hunter-stage6-baseline.npz'


def contract_trace(direct=False):
    states, shots, observations = [], [], []
    extra = [PilotAction(0, True, False, course=True, burn_heading=90, burn_frames=6),
             PilotAction(0, True, True, track=True, burn_heading=0, burn_frames=6, burn_reference=0)]
    actions = list(ACTIONS.values()) + extra
    for dt in (0.5, 1.0, 2.0):
        for mortal in (False, True):
            for action in actions:
                random.seed(42)
                ship = HunterRig((500.0, 500.0), replace(HunterSettings(), indestructible=not mortal))
                if direct:
                    from creatures.traits.energy import Energy
                    from creatures.traits.propulsion import Thrusters
                    from creatures.traits.burst_fire import BurstFire
                    from creatures.traits.combat import Gun
                    from entities.hunter_ship_body import HunterShipBody
                    from tests.creature_parts import creature, encounter
                    settings = ship.settings
                    ship = creature([Energy(settings.health, settings.indestructible, settings.damage_immunity,
                                            settings.wall_energy),
                                     Thrusters(1, config.SHIP_THRUST_FORCE * settings.thrust_multiplier,
                                               config.SHIP_ROTATION_SPEED * settings.turn_rate_multiplier, mode='hunter'),
                                     BurstFire(settings.burst_size, settings.burst_spacing, settings.fire_interval),
                                     Gun(cadence='burst', aimMode='nose', upgrades=True)], pos=(500.0, 500.0))
                    ship.radius = config.SHIP_SIZE
                    ship.body = HunterShipBody(ship)
                    ship.angle = 0
                    ship.settings = settings
                    enc = encounter(ship)
                    enc.ready()
                    random.seed(42)
                ship.gun_upgrade_level = 2
                ship.upgrade_remaining = 0.3
                ship.vx = 0.25
                maze = world([WallSegment((510, 400), (510, 600), 3)])
                for frame in range(24):
                    held = action if frame < 12 else NEUTRAL
                    solution = FiringSolution(3.0, frame % 4 != 0)
                    if direct:
                        from creatures.traits.energy import damage
                        for field in ('turn', 'thrust', 'fire', 'track', 'course', 'burn_heading',
                                      'burn_frames', 'burn_reference'):
                            setattr(ship.controls, field, getattr(held, field))
                        ship.controls.decision_token = held
                        ship.controls.on_target = solution.on_target
                        ship.controls.lead_degrees = solution.lead_degrees
                        enc.world.maze = maze
                        before = len(enc.world.projectiles)
                        enc.step(1 * dt)
                        fired = enc.world.projectiles[before:]
                        if frame in (3, 10, 20):
                            damage(ship, enc)
                    else:
                        fired = ship.step(dt, held, solution) or []
                        ship.check_wall_collision(maze.walls, maze.spatial_grid)
                        if frame in (3, 10, 20):
                            ship.take_damage()
                    states.append([ship.x, ship.y, ship.vx, ship.vy, ship.angle, ship.health,
                                   ship.immunity_remaining, ship.thrust_frames, ship.burst_remaining,
                                   ship.fire_remaining, ship.gun_upgrade_level, ship.shots_fired, ship.active])
                    shots.append([len(fired), sum(s.x for s in fired), sum(s.y for s in fired),
                                  sum(s.vx for s in fired), sum(s.vy for s in fired)])
                observations.append(sense(ship, maze))
    return np.asarray(states), np.asarray(shots), np.asarray(observations)


def test_the_trained_flight_and_observation_contract_is_preserved():
    states, shots, observations = contract_trace()
    with np.load(FIXTURE) as baseline:
        np.testing.assert_allclose(states, baseline['states'], rtol=0, atol=1e-10)
        np.testing.assert_allclose(shots, baseline['shots'], rtol=0, atol=1e-10)
        # Senses added since are appended (so trained policies migrate), so the baseline is a prefix of them.
        width = baseline['observations'].shape[1]
        np.testing.assert_array_equal(observations[:, :width], baseline['observations'])
        assert tuple(baseline['features']) == FEATURE_NAMES[:width]


def test_direct_creature_flight_matches_the_frozen_contract():
    states, shots, observations = contract_trace(direct=True)
    with np.load(FIXTURE) as baseline:
        np.testing.assert_allclose(states, baseline['states'], rtol=0, atol=1e-10)
        np.testing.assert_allclose(shots, baseline['shots'], rtol=0, atol=1e-10)
        width = baseline['observations'].shape[1]
        np.testing.assert_array_equal(observations[:, :width], baseline['observations'])
