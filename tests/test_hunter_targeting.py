from types import SimpleNamespace
from game_handlers.combat_targets import nearest_friendly


def test_nearest_living_ally_and_player_tiebreak():
    enemy = SimpleNamespace(x=0,y=0)
    player = SimpleNamespace(x=10,y=0,active=True)
    hunter = SimpleNamespace(x=5,y=0,active=True)
    assert nearest_friendly(enemy,player,hunter) is hunter
    hunter.x=10
    assert nearest_friendly(enemy,player,hunter) is player
    hunter.active=False
    assert nearest_friendly(enemy,player,hunter) is player
    player.active=False
    assert nearest_friendly(enemy,player,hunter) is None


import pytest
from unittest.mock import Mock
from entities.command_recorder import CommandRecorder
import creatures
from entities.ship import Ship
from entities.hunter_ship import HunterShip


def test_a_creature_aims_at_the_nearest_hunter():
    from tests.creature_parts import encounter, world
    crab = creatures.build('patrol', (300, 300), 1)
    player = Ship((900, 800))
    player.shield_active = True
    hunter = HunterShip((320, 300))
    enc = encounter(crab, world_=world(ship=player, hunter=hunter))
    enc.step(1.0)
    assert enc.target_for(crab) == hunter.get_pos()
    assert crab.controls.aim == hunter.get_pos()


@pytest.mark.parametrize('kind', ['patrol', 'replay', 'baby', 'split_boss', 'mother_boss', 'flocker'])
def test_a_creature_targets_the_nearest_hunter(kind):
    from tests.creature_parts import encounter, world
    creature = creatures.build(kind, (300, 300), 1, CommandRecorder())
    player = Ship((900, 800))
    player.shield_active = True
    hunter = HunterShip((320, 300))
    assert encounter(creature, world_=world(ship=player, hunter=hunter)).target_for(creature) == hunter.get_pos()


def test_a_flocker_aims_at_the_nearest_hunter():
    from tests.creature_parts import encounter, world
    flocker = creatures.build('flocker', (300, 300), 1)
    flocker.angle = 0.0
    player = Ship((900, 800))
    player.shield_active = True
    hunter = HunterShip((320, 300))
    enc = encounter(flocker, world_=world(ship=player, hunter=hunter))
    enc.step(1.0)
    flocker.gun_cooldown = 0.0
    enc.step(1.0)
    assert flocker.controls.aim == hunter.get_pos()
