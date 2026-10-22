"""Energy belongs to a Creature; wall loss and bullet immunity have distinct rules."""
import pytest

from creatures.traits.energy import Energy, damage, register_hit, take_hit
from tests.creature_parts import creature, encounter


def make(**params):
    c = creature([Energy(**params)])
    enc = encounter(c)
    enc.ready()
    return c, enc


def test_hits_observe_immunity_and_close_on_the_killing_hit():
    c, enc = make(health=2, indestructible=False, immunity=0.5)
    assert not damage(c, enc)
    assert c.health == 1
    assert not damage(c, enc)
    assert c.health == 1
    enc.step(31)
    assert damage(c, enc)
    assert c.is_dying and not c.active
    assert not damage(c, enc)
    assert c.health == 0


def test_an_indestructible_creature_keeps_its_energy():
    c, enc = make(health=3)
    assert not damage(c, enc)
    assert c.health == 3


def test_only_the_strongest_knock_is_kept_until_read():
    c, _ = make()
    register_hit(c, 3, 4)
    register_hit(c, 1, 2)
    assert take_hit(c) == (3, 4)
    assert take_hit(c) is None


def test_wall_energy_is_fractional_and_does_not_use_bullet_immunity():
    c, enc = make(health=2, indestructible=False, wallEnergy=3)
    c.max_speed = 10
    c.immunity_remaining = 1
    c.wall_impulse = (1, 0)
    c.emit('hit_wall', enc)
    assert c.health == pytest.approx(1.7)
    assert take_hit(c) == (1, 0)
    c.wall_impulse = (10, 0)
    c.emit('hit_wall', enc)
    assert not c.active
