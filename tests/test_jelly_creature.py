"""The Jelly as a Creature: it chases the nearest friend, and one hit kills it."""
import creatures
from entities.jellyfish import Jellyfish
from entities.projectile import Projectile
from tests.creature_parts import encounter, target, world

POS = (400.0, 300.0)


def test_the_catalogue_builds_a_jelly():
    jelly = creatures.build('aggressive', POS, 5)
    assert isinstance(jelly.body, Jellyfish)


def test_a_jelly_chases_and_one_hit_kills_it():
    jelly = creatures.build('aggressive', POS, 5)
    enc = encounter(jelly, world_=world(ship=target((POS[0] + 300.0, POS[1]))))
    for _ in range(30):
        enc.step(1.0)
    assert jelly.x > POS[0] + 10
    assert enc.shoot(Projectile(jelly.get_pos(), 0, source='player'))
    assert not jelly.active


def _ally(pos):
    ally = creatures.build('aggressive', pos, 5)
    ally.allegiance = 'ally'
    return ally


def test_enemy_targets_nearest_ally_creature_over_farther_ship():
    jelly = creatures.build('aggressive', POS, 5)
    ally = _ally((POS[0] + 100.0, POS[1]))
    enc = encounter(jelly, ally, world_=world(ship=target((POS[0] + 400.0, POS[1]))))
    assert enc.target_for(jelly) == ally.get_pos()


def test_target_for_unchanged_without_allied_creatures():
    jelly = creatures.build('aggressive', POS, 5)
    other = creatures.build('aggressive', (POS[0] + 50.0, POS[1]), 5)
    enc = encounter(jelly, other, world_=world(ship=target((POS[0] + 400.0, POS[1]))))
    assert enc.target_for(jelly) == (POS[0] + 400.0, POS[1])
    assert encounter(jelly, world_=world()).target_for(jelly) is None


def test_target_for_ignores_same_allegiance_and_self():
    ally_a = _ally(POS)
    ally_b = _ally((POS[0] + 10.0, POS[1]))
    enc = encounter(ally_a, ally_b, world_=world())
    assert enc.target_for(ally_a) is None
    dead = _ally((POS[0] + 5.0, POS[1]))
    jelly = creatures.build('aggressive', POS, 5)
    dead.active = False
    assert encounter(jelly, dead, world_=world()).target_for(jelly) is None
