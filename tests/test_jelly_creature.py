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
