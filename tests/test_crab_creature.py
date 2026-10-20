"""The Crab as a Creature: it patrols, and its gun fires at a target in range when it is ready."""
import pytest

import creatures
from creatures.traits.combat import Gun
from creatures.traits.brains import Patrol
from entities.patrol_crab import PatrolCrab
from entities.projectile import Projectile
from tests.creature_parts import creature, encounter, target, world

POS = (400.0, 300.0)


def gunner(interval=30, rng=200.0):
    crab = creature([Patrol(), Gun(intervalMin=interval, intervalMax=interval, range=rng)], pos=POS, key='patrol')
    stand_in = world(ship=target((POS[0] + 50.0, POS[1])))
    return crab, encounter(crab, world_=stand_in), stand_in


def test_the_catalogue_builds_a_crab():
    crab = creatures.build('patrol', POS, 5)
    assert isinstance(crab.body, PatrolCrab)


def test_the_gun_fires_only_when_ready_and_the_target_is_in_range():
    crab, enc, stand_in = gunner(interval=30)
    fired_on = []
    for frame in range(1, 75):
        before = len(stand_in.projectiles)
        enc.step(1.0)
        if len(stand_in.projectiles) > before:
            fired_on.append(frame)
    assert fired_on == [30, 60]
    shot = stand_in.projectiles[0]
    assert isinstance(shot, Projectile) and shot.is_enemy
    assert shot.vx > 0 and abs(shot.vy) < 1e-6           # aimed at the target, to its right
    assert crab.body.events.count('fired') == 2

    stand_in.ship = target((POS[0] + 900.0, POS[1]))      # out of range: it holds its fire
    for _ in range(100):
        enc.step(1.0)
    assert len(stand_in.projectiles) == 2


def test_gun_charge_rises_from_zero_to_one_across_the_cooldown():
    crab, enc, stand_in = gunner(interval=40)
    stand_in.ship = target((POS[0] + 900.0, POS[1]))      # never fires, so the charge just builds
    charges = []
    for _ in range(45):
        enc.step(1.0)
        charges.append(crab.gun_charge)
    assert charges[0] < 0.05
    assert charges == sorted(charges)
    assert charges[-1] == pytest.approx(1.0)


def test_the_gun_reads_the_levels_strength_when_not_given_numbers():
    import level_rules
    strength = level_rules.get_enemy_strength(7)
    crab = creatures.build('patrol', POS, 7)
    encounter(crab).step(1.0)
    assert crab.gun_range == strength.fire_range
    assert crab.speed == strength.patrol_speed


def test_one_hit_kills_a_crab():
    crab = creatures.build('patrol', POS, 3)
    stand_in = world(ship=target((POS[0] + 900.0, POS[1])))
    enc = encounter(crab, world_=stand_in)
    enc.step(1.0)
    assert enc.shoot(Projectile(crab.get_pos(), 0, source='player'))
    assert not crab.active
    stand_in.collision_handler.drop_pickup.assert_called_once()


@pytest.mark.parametrize('kind', ['patrol', 'aggressive'])
def test_with_no_target_a_crab_and_a_jelly_hold_still(kind):
    still = creatures.build(kind, POS, 5)
    enc = encounter(still)                                # no ship, no hunter: nobody to go after
    for _ in range(120):
        enc.step(1.0)
    assert still.get_pos() == pytest.approx(POS)
    assert not still.controls.fire
