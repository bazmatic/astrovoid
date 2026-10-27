"""Player tuning and hunter tuning must not change one another's flight physics."""
import json

import pytest

import config
from hunter.model import HunterSettings, NEUTRAL, PilotAction
from hunter.perception import HunterPerception
from tests.hunter_fixture import HunterRig
from tests.test_hunter_perception import maze


def test_player_movement_changes_do_not_change_hunters(monkeypatch):
    before = HunterRig((200, 200))
    for name in ('SHIP_THRUST_FORCE', 'SHIP_ROTATION_SPEED', 'SHIP_FRICTION', 'SHIP_MAX_SPEED'):
        monkeypatch.setattr(config, name, 0.01)
    after = HunterRig((200, 200))
    for hunter in (before, after):
        hunter.step(1, PilotAction(1, True, False))
    assert (after.vx, after.vy, after.angle) == pytest.approx((before.vx, before.vy, before.angle))
    assert after.max_speed == before.max_speed


def test_hunter_movement_settings_drive_physics_and_pilot_readings(monkeypatch):
    player_values = (config.SHIP_THRUST_FORCE, config.SHIP_ROTATION_SPEED,
                     config.SHIP_FRICTION, config.SHIP_MAX_SPEED)
    movement = config.HunterShipSettings(rotationSpeed=12, thrustForce=2, friction=0.9, maxSpeed=3)
    monkeypatch.setattr(config.SETTINGS, 'hunterShip', movement)
    settings = HunterSettings(thrust_multiplier=0.5, turn_rate_multiplier=0.25)
    hunter = HunterRig((200, 200), settings)
    hunter.step(1, PilotAction(1, True, False))
    assert hunter.angle == 3
    assert hunter.thrust_force == 1
    assert hunter.max_speed == 3
    assert (hunter.vx ** 2 + hunter.vy ** 2) ** 0.5 == pytest.approx(0.9)
    observation = HunterPerception(settings).observe(hunter, maze(), None, [], [], NEUTRAL, 0, 1)
    physics = json.loads(observation.state_json)['physics']
    assert physics['friction_per_frame'] == 0.9
    assert physics['speed_limit'] == 3
    assert physics['rotation_per_frame'] == 3
    assert physics['thrust_per_frame'] == 1
    assert (config.SHIP_THRUST_FORCE, config.SHIP_ROTATION_SPEED,
            config.SHIP_FRICTION, config.SHIP_MAX_SPEED) == player_values
