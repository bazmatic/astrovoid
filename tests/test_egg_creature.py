"""The Egg as a Creature: it grows and hardens, then hatches Squidlets, or bursts when shot."""
import pygame

import creatures
from creatures.creature import Creature
from creatures.traits.combat import TakesHits
from creatures.traits.growth import Grows, Hatches
from creatures.traits.spawning import LaysEggs
from entities.command_recorder import CommandRecorder
from entities.egg import EggBody
from entities.projectile import Projectile
from tests.creature_parts import creature, encounter, world

POS = (400.0, 300.0)


def quick_egg():
    """An egg that grows a pixel a frame: from 8 it reaches 24 on frame 16."""
    return creature([TakesHits(2), Grows(to=24, rateMin=1.0, rateMax=1.0, hitPointsGrown=4),
                     Hatches(into='baby', countMin=1, countMax=3, spread=60)], pos=POS, key='egg')


def hatchlings(enc, egg):
    return [e for e in enc.roster.all() if e is not egg]


def test_an_egg_grows_hardens_and_hatches_squidlets():
    egg = quick_egg()
    enc = encounter(egg, world_=world(command_recorder=CommandRecorder()))
    hit_points = []
    for _ in range(15):
        enc.step(1.0)
        hit_points.append(egg.max_hit_points)
    assert egg.active and egg.radius == 23
    assert hit_points[0] == 2 and hit_points[-1] == 4 and hit_points == sorted(hit_points)
    enc.step(1.0)
    assert not egg.active and egg.hatched
    babies = hatchlings(enc, egg)
    assert len(babies) == egg.hatch_count and all(isinstance(b, Creature) and b.type == 'baby' for b in babies)


def test_hatching_is_not_a_kill_and_bursting_is():
    hatching = creatures.build('egg', POS, 1, CommandRecorder())
    stand_in = world(command_recorder=CommandRecorder())
    enc = encounter(hatching, world_=stand_in)
    enc.step(1.0)
    hatching.radius = 24
    enc.step(1.0)
    assert not hatching.active
    stand_in.collision_handler.drop_pickup.assert_not_called()
    stand_in.collision_handler.record_kill.assert_not_called()

    bursting = creatures.build('egg', POS, 1, CommandRecorder())
    stand_in = world(command_recorder=CommandRecorder())
    enc = encounter(bursting, world_=stand_in)
    enc.step(1.0)
    while bursting.active:
        enc.shoot(Projectile(POS, 0))
    stand_in.collision_handler.drop_pickup.assert_called_once()
    stand_in.collision_handler.record_kill.assert_called_once()
    assert hatchlings(enc, bursting) == []


def test_a_shot_shoves_an_egg():
    egg = creatures.build('egg', POS, 1, CommandRecorder())
    enc = encounter(egg)
    enc.step(1.0)
    enc.shoot(Projectile(POS, 0))
    assert egg.vx > 0


def test_a_fresh_egg_draws():
    egg = creatures.build('egg', POS, 1, CommandRecorder())
    assert isinstance(egg.body, EggBody)
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    egg.draw(screen)
    assert screen.get_bounding_rect().width > 0


def test_a_hatched_and_a_burst_egg_die_differently():
    hatched = creatures.build('egg', POS, 1, CommandRecorder())
    enc = encounter(hatched, world_=world(command_recorder=CommandRecorder()))
    enc.step(1.0)
    hatched.radius = 24
    enc.step(1.0)
    assert hatched.body.ending == 'hatched' and hatched.body.blobs == []

    burst = creatures.build('egg', POS, 1, CommandRecorder())
    enc = encounter(burst)
    enc.step(1.0)
    while burst.active:
        enc.shoot(Projectile(POS, 0))
    assert burst.body.ending == 'burst' and len(burst.body.blobs) == EggBody.BLOB_COUNT


def test_a_mother_lays_creature_eggs():
    mother = creature([LaysEggs(interval=180)], pos=POS, key='mother_boss')
    enc = encounter(mother, world_=world(command_recorder=CommandRecorder()))
    enc.step(1.0)
    [egg] = hatchlings(enc, mother)
    assert isinstance(egg, Creature) and egg.type == 'egg'
