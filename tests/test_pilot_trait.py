"""The pilot trait: a creature that follows a craft its pilot flies, and the hunterShip Body that draws it."""
import copy
from dataclasses import replace

import pygame
import pytest

import enemy_kinds
from creatures.creature import Creature
from creatures.traits.combat import TakesHits
from creatures.traits.piloted import Pilot
from creatures.traits.energy import Energy, take_hit
from creatures.traits.propulsion import Thrusters
from creatures.traits.burst_fire import BurstFire
from creatures.traits.combat import Gun
from hunter.build import flight_kind
from hunter.settings_for import hunter_settings_for
from entities.hunter_ship_body import HunterShipBody
from tests.creature_parts import encounter, world
from tests.test_rules_hunter import SilentWorker, Target
from tests.test_senses import world as senses_maze

RED = (255, 90, 90)
TUNING = {'size': 8, 'color': list(RED), 'fill': [110, 25, 25], 'noseColor': [255, 215, 200],
          'cockpitColor': [60, 10, 10], 'engineColor': [170, 60, 20], 'engineLitColor': [255, 150, 80],
          'showsHitPoints': False}


class ThrustAndFire:
    """A neural policy that always thrusts and holds the trigger, never turning."""

    def initial_state(self):
        return None

    def act(self, senses, state, greedy=True, rng=None):
        return (1, True, True), state


class CountingWorker(SilentWorker):
    def __init__(self):
        super().__init__()
        self.closes = 0

    def close(self):
        self.closes += 1


def piloted(mode='neural', policy=None, worker=None, protagonist=None, **tuning):
    """A piloted creature at (500, 500) facing right, set up on a level with a protagonist; and its Encounter."""
    kind = replace(enemy_kinds.kind('static'), allegiance='enemy', tuning={**TUNING, **tuning})
    settings = replace(hunter_settings_for(mode), indestructible=True)
    kind = replace(kind, traits=(('pilot', {'mode': mode}), ('energy', {}),
                                ('thrusters', {'speedShare': 1}), ('burstFire', {}),
                                ('gun', {'cadence': 'burst', 'aimMode': 'nose', 'upgrades': True}),
                                ('takesHits', {'hitPoints': 12})))
    from creatures.registry import TRAITS
    kind = flight_kind(kind, settings)
    c = Creature(kind, (500.0, 500.0), None, [TRAITS[n].from_params(p) for n, p in kind.traits])
    c.settings = settings
    c.body = HunterShipBody(c)
    c.angle = 0.0
    stand_in = world(maze=senses_maze())
    stand_in.protagonist = lambda: protagonist
    stand_in.enemy_policy = lambda: policy
    stand_in.rules_worker = lambda: worker if worker is not None else SilentWorker()
    enc = encounter(c, world_=stand_in)
    enc.ready()
    return c, enc


def test_a_pilot_flies_its_creature_and_its_shots_join_the_level():
    c, enc = piloted(policy=ThrustAndFire(), protagonist=Target(700.0, 500.0, True))
    for _ in range(30):
        enc.step(1.0)
    assert c.x > 510.0 and c.y == pytest.approx(500.0, abs=1.0)
    shots = enc.world.projectiles
    assert shots and all(s.is_enemy and s.source == 'enemy' and s.dynamic_color == RED for s in shots)


def test_the_pilot_flies_the_creature_without_a_craft():
    c, enc = piloted(policy=ThrustAndFire())
    enc.step(1)
    assert c.flight.ship is c
    assert not hasattr(c, 'craft')


def test_a_push_moves_the_creature_and_the_pilot_feels_it():
    c, enc = piloted(mode='rules')
    enc.step(1)
    x = c.x
    c.vx += 3
    enc.step(1)
    assert take_hit(c) == pytest.approx((3, 0))
    assert c.x > x + 2


def test_a_neural_pilot_without_a_model_never_flies():
    c, enc = piloted(policy=None, protagonist=Target(700.0, 500.0, True))
    for _ in range(30):
        enc.step(1.0)
    assert c.flight is None and (c.x, c.y) == (500.0, 500.0) and enc.world.projectiles == []


def test_closing_stops_the_pilot_and_its_worker_once():
    worker = CountingWorker()
    c, enc = piloted(mode='rules', worker=worker)
    enc.step(1.0)
    enc.kill(c)
    enc.close()
    enc.close()
    assert worker.closes == 1


def test_a_copy_leaves_the_pilot_behind():
    c, enc = piloted(policy=ThrustAndFire(), protagonist=Target(700.0, 500.0, True))
    enc.step(1.0)
    clone = copy.deepcopy(c)
    assert clone.flight is None and clone.pilot_worker is None
    assert (clone.x, clone.y, clone.radius) == (c.x, c.y, c.radius)
    x = c.x
    enc.step(1.0)
    assert c.flight is not None and c.x > x


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        Pilot.from_params({'mode': 'unknown'})


def test_the_body_draws_the_arrowhead_in_the_kinds_colours():
    pygame.init()
    c, _ = piloted(policy=None)
    c.x, c.y = 150.0, 150.0
    screen = pygame.Surface((300, 300))
    c.draw(screen)
    pixels = {tuple(screen.get_at((x, y)))[:3] for x in range(300) for y in range(300)}
    assert RED in pixels

    boss, _ = piloted(policy=None, size=16, showsHitPoints=True)
    boss.x, boss.y = 150.0, 150.0
    screen = pygame.Surface((300, 300))
    boss.draw(screen)
    bar_row = round(150 - 16 * 2.2) - 2
    assert any(tuple(screen.get_at((x, bar_row)))[:3] == RED for x in range(300))

    c.die()
    c.death_timer = c.DEATH_DURATION / 2
    screen = pygame.Surface((300, 300))
    c.draw_death(screen)
    ring = round(8 * (1.5 + 4.0 * 0.5))
    assert any(tuple(screen.get_at((150 + r, 150)))[:3] == RED for r in range(ring - 2, ring + 1))
    assert tuple(screen.get_at((150, 150)))[:3] == (0, 0, 0)
