import pytest
import config
from entities.hunter_ship import HunterShip
from hunter.model import ACTIONS, NEUTRAL


@pytest.mark.parametrize('name', list(ACTIONS))
def test_simultaneous_controls(name):
    action = ACTIONS[name]
    ship = HunterShip((200,200))
    bullet = ship.step(1, action)
    assert (bullet is not None) == action.fire
    assert ship.angle == (action.turn * config.SHIP_ROTATION_SPEED) % 360
    assert (abs(ship.vx) + abs(ship.vy) > 0) == action.thrust
    if bullet:
        assert bullet.source == 'hunter'
        assert ship.step(1, action) is None


def test_coasting_keeps_momentum_and_separated_hits_kill():
    ship = HunterShip((200,200))
    ship.vx = 2
    ship.step(1, NEUTRAL)
    assert ship.x > 200
    for remaining in (2,1,0):
        assert ship.take_damage() == (remaining == 0)
        assert ship.health == remaining
        ship.take_damage()
        assert ship.health == remaining
        ship.step(config.FPS * 0.51, NEUTRAL)
    assert not ship.active
    assert ship.step(1, ACTIONS['none_thrust_fire']) is None
