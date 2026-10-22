"""Test rigs for exercising Creature traits with explicit controls or a pilot.

The rigs translate older behavioral test setup into Encounter operations. They contain no flight physics,
weapon scheduling or damage policy; production code never imports them.
"""
from copy import deepcopy
from types import SimpleNamespace

import config
import creatures
from creatures.encounter import Encounter
from creatures.traits.burst_fire import cancel_burst
from creatures.traits.energy import damage, register_hit, take_hit
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.fire_rate_calculator import cooldown_for_upgrade
from hunter.build import PilotSetup
from hunter.flight import HunterFlight as Flight
from hunter.model import HunterSettings
from physics import thrust


def test_world():
    return SimpleNamespace(ship=None, hunter=None, maze=None, projectiles=[], scoring=None, command_recorder=None)


class HunterRig:
    COLOR = (120, 255, 90)
    BURN_ALIGNMENT_DEGREES = 5.0
    LOOSE_BURN_ALIGNMENT_DEGREES = 20.0
    DEATH_DURATION = 48.0

    def __init__(self, pos, settings=HunterSettings()):
        c = creatures.build('allied_hunter', pos, pilot_setup=PilotSetup(settings, None, None), angle=0)
        c.traits = tuple(t for t in c.traits if t.NAME != 'pilot')
        c.pilot_setup = c.flight = c.pilot_worker = None
        object.__setattr__(self, 'creature', c)
        roster = EnemyRoster()
        roster.add(c)
        Encounter(roster, test_world()).ready()

    def __getattr__(self, name):
        c = object.__getattribute__(self, 'creature')
        if name == 'fire_interval':
            return c.base_fire_interval * cooldown_for_upgrade(c.gun_upgrade_level) / config.SETTINGS.powerups.fireRateBaseCooldown
        return getattr(c, name)

    def __setattr__(self, name, value):
        setattr(self.creature, name, value)

    def __deepcopy__(self, memo):
        clone = object.__new__(type(self))
        object.__setattr__(clone, 'creature', deepcopy(self.creature, memo))
        roster = EnemyRoster()
        roster.add(clone.creature)
        clone.creature.encounter = Encounter(roster, test_world())
        return clone

    def step(self, dt, action, solution=None):
        c = self.creature
        for field in ('turn', 'thrust', 'fire', 'track', 'course', 'burn_heading', 'burn_frames', 'burn_reference'):
            setattr(c.controls, field, getattr(action, field))
        c.controls.decision_token = action
        c.controls.on_target = solution is not None and solution.on_target
        c.controls.lead_degrees = solution.lead_degrees if solution is not None else None
        c.controls.gun_enabled = True
        sink = c.encounter.world.projectiles
        before = len(sink)
        c.encounter.step_creature(c, dt)
        return sink[before:] or None

    def take_damage(self):
        return damage(self.creature, self.encounter)

    def register_hit(self, dvx, dvy):
        register_hit(self.creature, dvx, dvy)

    def take_hit(self):
        return take_hit(self.creature)

    def collect_powerup(self):
        self.creature.emit('pickup', self.encounter)

    def get_gun_upgrade_level(self):
        return self.gun_upgrade_level

    def cancel_burst(self):
        cancel_burst(self.creature)

    def _shots(self):
        from tests.creature_parts import fire_round
        clone = deepcopy(self)
        clone.fire_remaining = 0
        clone.burst_remaining = 0
        return fire_round(clone.creature, clone.encounter)

    def check_wall_collision(self, walls, spatial_grid=None):
        c = self.creature
        vx, vy = c.vx, c.vy
        hit = thrust.sweep_walls(c, walls, spatial_grid)
        if hit and c.active:
            c.wall_impulse = (c.vx - vx, c.vy - vy)
            c.emit('hit_wall', c.encounter)
        c._pilot_velocity = (c.vx, c.vy)
        return hit

    def outline(self):
        return self.body.outline(self.creature)

    def cockpit(self):
        return self.body._place(self.creature, 0.5, 0)


class FlightRig:
    """A pilot-driven flight with a private shot sink, exposed for behavioral tests."""
    def __init__(self, ship, pilot, surroundings):
        from creatures.traits.piloted import Pilot
        c = ship.creature if isinstance(ship, HunterRig) else ship
        enc = c.encounter
        enc.world.maze = surroundings.maze
        c.traits = (Pilot('jev'),) + tuple(t for t in c.traits if t.NAME != 'pilot')
        self._flight = Flight(c, pilot, surroundings, encounter=enc)
        c.flight = self._flight
        self.ship = ship

    def __getattr__(self, name):
        return getattr(self._flight, name)

    def fly(self, dt):
        sink = self._flight.encounter.world.projectiles
        before = len(sink)
        self._flight.step(dt)
        return sink[before:]
