"""The Flighthouse as a Creature: rooted, it sweeps its beam until it sees the player, then tracks them and launches
Flockers."""
import math
from types import SimpleNamespace

import pygame
import pytest

import config
import creatures
import enemy_kinds
from creatures.creature import Creature
from entities.flighthouse import FlighthouseBody
from entities.projectile import Projectile
from tests.creature_parts import encounter, open_maze, target, world

POS = (400.0, 300.0)
SCANS = dict(enemy_kinds.kind('flighthouse').traits)['scans']


def lighthouse(angle=0.0, **stand_in):
    """A flighthouse at POS facing `angle`, set up on a level; the Encounter is returned too."""
    tower = creatures.build('flighthouse', POS)
    enc = encounter(tower, world_=world(**stand_in))
    enc.ready()
    tower.angle = angle
    return tower, enc


def ahead(angle, dist=300.0):
    return (POS[0] + math.cos(math.radians(angle)) * dist, POS[1] + math.sin(math.radians(angle)) * dist)


def launched(enc, tower):
    return [e for e in enc.roster.all() if e is not tower]


def test_it_sweeps_until_it_sees_the_player_then_tracks_and_launches():
    tower, enc = lighthouse(angle=0.0, ship=target(ahead(90.0)))
    enc.step(1.0)
    assert tower.angle == pytest.approx(SCANS['scanSpeed'] / config.FPS) and not tower.sees_target
    for _ in range(60):
        enc.step(1.0)
    assert tower.sees_target and tower.angle == pytest.approx(90.0)
    assert launched(enc, tower)


def test_a_wall_or_a_gate_hides_the_player():
    between = SimpleNamespace(start=(500.0, 200.0), end=(500.0, 400.0), active=True)
    for walls, gates, seen in (([], [], True), ([between], [], False), ([], [between], False)):
        maze = open_maze(walls)
        maze.gate_segments = gates
        tower, enc = lighthouse(angle=0.0, ship=target(ahead(0.0)), maze=maze)
        enc.step(1.0)
        assert tower.sees_target is seen
        assert bool(launched(enc, tower)) is seen


def test_a_flighthouse_ignores_the_hunter():
    tower, enc = lighthouse(angle=0.0, ship=target(ahead(180.0)), hunter=target(ahead(0.0)))
    enc.step(1.0)
    assert not tower.sees_target and launched(enc, tower) == []


def test_a_launched_flocker_is_a_creature_on_the_roster():
    tower, enc = lighthouse(angle=0.0, ship=target(ahead(0.0)))
    enc.step(1.0)
    [flocker] = launched(enc, tower)
    share = dict(enemy_kinds.kind('flocker').traits)['thrusters']['speedShare']
    assert isinstance(flocker, Creature) and flocker.type == 'flocker'
    assert flocker.angle == pytest.approx(0.0) and flocker.vy == pytest.approx(0.0)
    assert flocker.vx == pytest.approx(0.8 * share * config.SHIP_MAX_SPEED)
    assert not flocker.has_spawned
    enc.step(1.0)
    assert flocker.has_spawned


def test_five_hits_kill_it():
    tower, enc = lighthouse(ship=target(ahead(180.0, 2000.0)))
    enc.step(1.0)
    for _ in range(4):
        enc.shoot(Projectile(POS, 0.0))
    assert tower.active
    enc.shoot(Projectile(POS, 0.0))
    assert not tower.active


def test_a_fresh_flighthouse_draws():
    tower = creatures.build('flighthouse', POS)
    assert isinstance(tower.body, FlighthouseBody)
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    tower.draw(screen)
    assert screen.get_bounding_rect().width > 0
