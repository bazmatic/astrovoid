"""Stand-ins for testing Creatures and Traits without a Game: a Body that only records events, a world, and an
Encounter over a few creatures."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import enemy_kinds
from creatures.creature import Creature
from creatures.encounter import Encounter
from game_handlers.enemy_roster import EnemyRoster


class RecordingBody:
    DEATH_DURATION = 10.0
    DEATH_FRICTION = 0.9

    def __init__(self, creature=None):
        self.events = []

    def update(self, creature, dt, target):
        pass

    def draw(self, screen, creature):
        pass

    def update_death(self, creature, dt):
        pass

    def draw_death(self, screen, creature):
        pass

    def on_event(self, creature, name):
        self.events.append(name)


def creature(traits, pos=(100.0, 100.0), key='static', level=1):
    kind = replace(enemy_kinds.kind(key), allegiance='enemy')
    return Creature(kind, pos, RecordingBody(), traits, level=level)


def open_maze(walls=()):
    """A maze with these walls (none by default) and room everywhere."""
    return SimpleNamespace(walls=list(walls), spatial_grid=None, is_open=lambda pos, radius: True,
                           open_spot_near=lambda origin, radius, max_offset, *a, **k: origin)


def world(**overrides):
    stand_in = SimpleNamespace(
        ship=None, hunter=None, maze=open_maze(), scoring=Mock(),
        sound_manager=Mock(), command_recorder=Mock(), collision_handler=Mock(), projectiles=[], powerup_crystals=[],
        jev_beacon_allowed=lambda: False)
    stand_in.collision_handler.shoot_into.return_value = False
    for key, value in overrides.items():
        setattr(stand_in, key, value)
    return stand_in


def encounter(*creatures, world_=None):
    roster = EnemyRoster()
    roster.extend(creatures)
    return Encounter(roster, world_ or world())


def target(pos):
    """Something to chase or shoot at: alive, at a position."""
    return SimpleNamespace(x=pos[0], y=pos[1], active=True, get_pos=lambda: pos,
                           is_shield_active=lambda: True, check_circle_collision=lambda *a: False)
