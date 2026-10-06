import pytest
import config
from entities.hunter_ship import HunterShip
from hunter.model import ACTIONS, NEUTRAL, HunterSettings

MORTAL = HunterSettings(indestructible=False)


@pytest.mark.parametrize('name', list(ACTIONS))
def test_simultaneous_controls(name):
    action = ACTIONS[name]
    ship = HunterShip((200,200))
    bullet = ship.step(1, action)
    assert (bullet is not None) == action.fire
    assert ship.angle == (action.turn * config.SHIP_ROTATION_SPEED
                          * ship.settings.turn_rate_multiplier) % 360
    assert (abs(ship.vx) + abs(ship.vy) > 0) == action.thrust
    if bullet:
        assert bullet.source == 'hunter'
        assert ship.step(1, action) is None


def test_coasting_keeps_momentum_and_separated_hits_kill():
    ship = HunterShip((200,200), MORTAL)
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


def test_default_hunter_is_indestructible():
    ship = HunterShip((200,200))
    for _ in range(10):
        assert not ship.take_damage()
        ship.step(config.FPS * 0.51, NEUTRAL)
    assert ship.active
    assert ship.health == ship.settings.health


def test_one_trigger_pull_fires_a_burst_of_three_then_cools_down():
    ship = HunterShip((200,200))
    fire,settings = ACTIONS['none_coast_fire'],ship.settings
    shots = [frame for frame in range(1,13) if ship.step(1, fire if frame == 1 else NEUTRAL)]
    spacing = round(settings.burst_spacing*config.FPS)
    assert shots == [1, 1+spacing, 1+2*spacing]
    # Holding the trigger starts the next burst only after the cooldown.
    ship = HunterShip((200,200))
    held = [frame for frame in range(1,31) if ship.step(1, fire)]
    cooldown = round(settings.fire_interval*config.FPS)
    second = 1+2*spacing+cooldown
    assert held == [1, 1+spacing, 1+2*spacing, second, second+spacing, second+2*spacing]
    assert HunterShip((200,200)).step(1, fire).source == 'hunter'


def test_cancelled_burst_fires_no_further_shots():
    ship = HunterShip((200,200))
    assert ship.step(1, ACTIONS['none_coast_fire'])
    ship.cancel_burst()
    assert not any(ship.step(1, NEUTRAL) for _ in range(30))


def test_status_label_shows_pilot_status_and_mortal_health():
    import pygame
    pygame.font.init()
    font, screen = pygame.font.Font(None, 24), pygame.Surface((400,400))
    rendered = []
    class Spy:
        def render(self, text, *args):
            rendered.append(text)
            return font.render(text, *args)
    HunterShip((200,200)).draw_status(screen, Spy(), 'unavailable')
    HunterShip((200,200), MORTAL).draw_status(screen, Spy(), 'active')
    assert rendered == ['unavailable', 'active  +++']
