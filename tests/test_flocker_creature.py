"""The Flocker as a Creature: a flying fish that flocks with its kind, seeks the nearest friend, and fires with its
neighbours."""
import itertools
import math

import pygame

import creatures
from creatures.traits.flock import Flocks
from entities.flocker import FlockerBody
from entities.projectile import Projectile
from tests.creature_parts import encounter, target, world


def flocker(pos, angle=0.0):
    bird = creatures.build('flocker', pos)
    bird.angle = angle
    return bird


def flocking(bird):
    return next(t for t in bird.traits if isinstance(t, Flocks))


def test_flockers_keep_apart_and_head_for_their_target():
    goal = (900.0, 300.0)

    def fly(separation):
        birds = [flocker((300.0 + dx, 300.0 + dy)) for dx, dy in itertools.product((-6.0, 0.0, 6.0), repeat=2)][:8]
        for bird in birds:
            weights = flocking(bird).weights
            flocking(bird).weights = (weights[0] * separation,) + weights[1:]
        enc = encounter(*birds, world_=world(ship=target(goal)))
        for _ in range(60):
            enc.step(1.0)
        spread = sum(math.dist(a.get_pos(), b.get_pos()) for a, b in itertools.combinations(birds, 2))
        return spread, sum(math.dist(b.get_pos(), goal) for b in birds) / len(birds)

    (spread, distance), (huddled, _) = fly(1.0), fly(0.0)
    assert spread > huddled * 1.5
    assert distance < math.dist((300.0, 300.0), goal) - 100


def test_a_flocker_fires_at_close_range_when_facing_its_target():
    bird = flocker((300.0, 300.0), angle=0.0)
    stand_in = world(ship=target((400.0, 300.0)))
    enc = encounter(bird, world_=stand_in)
    enc.step(1.0)
    bird.gun_cooldown = 0.0
    enc.step(1.0)
    enc.step(1.0)
    [shot] = stand_in.projectiles
    assert shot.is_enemy and shot.vx > 0 and abs(shot.vy) < 1e-6


def test_a_neighbour_firing_sets_off_the_flock():
    shooter, neighbour = flocker((300.0, 300.0), angle=90.0), flocker((360.0, 300.0), angle=90.0)
    enc = encounter(shooter, neighbour, world_=world(ship=target((330.0, 600.0))))   # in range, not close
    enc.step(1.0)
    shooter.gun_cooldown, neighbour.gun_cooldown = 300.0, 0.0
    flocks = flocking(neighbour)
    flocks.sync_chance = 1.0
    flocks.on_crowd([shooter, neighbour], enc, 1.0)
    assert not neighbour.controls.fire
    shooter.just_fired = True
    flocks.on_crowd([shooter, neighbour], enc, 1.0)
    assert neighbour.controls.fire and neighbour.controls.aim == (330.0, 600.0)


def test_one_hit_kills_a_flocker():
    bird = flocker((300.0, 300.0))
    stand_in = world(ship=target((900.0, 800.0)))
    enc = encounter(bird, world_=stand_in)
    enc.step(1.0)
    assert enc.shoot(Projectile(bird.get_pos(), 0.0))
    assert not bird.active
    stand_in.collision_handler.drop_pickup.assert_called_once()


def test_a_fresh_flocker_draws():
    bird = flocker((300.0, 300.0))
    assert isinstance(bird.body, FlockerBody)
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    bird.draw(screen)
    assert screen.get_bounding_rect().width > 0


def test_a_surviving_hit_flinches_then_recovers_without_changing_flight():
    bird=flocker((300,300))
    enc=encounter(bird)
    enc.ready()
    bird.hit_points=3
    position=bird.get_pos()
    assert enc.shoot(Projectile(position,0))
    assert bird.active and bird.body.flinch_remaining == bird.body.FLINCH_FRAMES
    for _ in range(int(bird.body.FLINCH_FRAMES)):
        bird.body.update(bird,1)
    assert bird.body.flinch_remaining == 0
    assert bird.get_pos() == position


def test_lethal_hit_keeps_impact_visible_during_death_then_fades():
    bird=flocker((300,300))
    enc=encounter(bird)
    enc.ready()
    enc.shoot(Projectile(bird.get_pos(),0))
    assert not bird.active and bird.is_dying
    assert bird.body.flinch_remaining > 0
    surface=pygame.Surface((600,600),pygame.SRCALPHA)
    bird.draw_death(surface)
    assert surface.get_bounding_rect().width > 0
    for _ in range(int(bird.body.FLINCH_FRAMES)):
        bird.update_death(1)
    assert bird.body.flinch_remaining == 0 and bird.is_dying
