"""The Encounter runs every Creature on the level: its traits in catalogue order, then each kind's crowd traits, and
it offers each friendly shot to the creatures in roster order."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import enemy_kinds
from creatures import registry
from creatures.creature import Creature
from creatures.encounter import Encounter
from creatures.trait import Trait
from entities.projectile import Projectile
from game_handlers.enemy_roster import EnemyRoster


class _Body:
    DEATH_DURATION = 10.0
    DEATH_FRICTION = 0.9

    def update(self, creature, dt, target):
        pass

    def draw(self, screen, creature):
        pass

    def update_death(self, creature, dt):
        pass

    def draw_death(self, screen, creature):
        pass

    def on_event(self, creature, name):
        pass


def _recording(name, log, **hooks):
    """A trait that logs (name, hook) for every hook it is given, and runs the given hook bodies."""

    class Recording(Trait):
        NAME = name

        def on_spawn(self, c, enc):
            log.append((name, 'spawn'))
            hooks.get('on_spawn', lambda *a: None)(c, enc)

        def on_frame(self, c, enc, dt):
            log.append((name, 'frame'))
            hooks.get('on_frame', lambda *a: None)(c, enc, dt)

        def on_shot(self, c, shot, enc):
            log.append((name, 'shot', id(c)))

        def on_death(self, c, enc):
            log.append((name, 'death'))

    return Recording()


def _creature(traits, pos=(100.0, 100.0), key='static'):
    kind = replace(enemy_kinds.kind(key), allegiance='enemy')
    return Creature(kind, pos, _Body(), traits)


def _world(**overrides):
    world = SimpleNamespace(
        ship=None, hunter=None, maze=None, scoring=Mock(), sound_manager=Mock(), command_recorder=Mock(),
        collision_handler=Mock(), projectiles=[], powerup_crystals=[], jev_beacon_allowed=lambda: False)
    for key, value in overrides.items():
        setattr(world, key, value)
    return world


def _encounter(*creatures, world=None):
    roster = EnemyRoster()
    roster.extend(creatures)
    return Encounter(roster, world or _world())


def test_traits_run_in_catalogue_order_every_frame():
    log = []
    encounter = _encounter(_creature([_recording('first', log), _recording('second', log)]))
    encounter.step(1.0)
    assert [name for name, hook in log if hook == 'frame'] == ['first', 'second']


def test_on_spawn_runs_once_before_the_first_frame():
    log = []
    encounter = _encounter(_creature([_recording('only', log)]))
    encounter.step(1.0)
    encounter.step(1.0)
    assert log == [('only', 'spawn'), ('only', 'frame'), ('only', 'frame')]


def test_a_shot_hits_only_the_first_creature_it_reaches():
    log = []
    first, second = _creature([_recording('a', log)]), _creature([_recording('b', log)])
    world = _world()
    encounter = _encounter(first, second, world=world)
    assert encounter.shoot(Projectile((100.0, 100.0), 0))
    assert [entry for entry in log if entry[1] == 'shot'] == [('a', 'shot', id(first))]


def test_a_shot_that_misses_every_creature_is_not_consumed():
    world = _world()
    encounter = _encounter(_creature([], pos=(500.0, 500.0)), world=world)
    shot = Projectile((100.0, 100.0), 0)
    assert encounter.shoot(shot) is False
    assert shot.active
    assert not world.collision_handler.mock_calls


def test_enemy_shots_are_not_offered_to_creatures():
    log = []
    encounter = _encounter(_creature([_recording('a', log)]))
    encounter.shoot(Projectile((100.0, 100.0), 0, is_enemy=True))
    assert not [entry for entry in log if entry[1] == 'shot']


def test_a_creature_killed_this_frame_does_not_act_again():
    log = []
    killer = _recording('killer', log, on_frame=lambda c, enc, dt: enc.kill(c))
    creature = _creature([killer, _recording('after', log)])
    encounter = _encounter(creature)
    encounter.step(1.0)
    encounter.step(1.0)
    assert ('after', 'frame') not in log
    assert log.count(('killer', 'death')) == 1
    assert log.count(('after', 'death')) == 1
    assert log.count(('killer', 'frame')) == 1
    assert not creature.active


def test_crowd_traits_run_once_per_kind_with_the_live_creatures_of_that_kind():
    calls = []

    class Crowd(Trait):
        NAME = 'crowd'
        CROWD = True

        def on_crowd(self, creatures, enc, dt):
            calls.append(sorted(id(c) for c in creatures))

    crowd = Crowd()
    jellies = [_creature([crowd], key='aggressive') for _ in range(3)]
    crabs = [_creature([crowd], key='patrol') for _ in range(2)]
    urchin = _creature([])
    encounter = _encounter(*jellies, urchin, *crabs)
    encounter.kill(jellies[2])
    encounter.step(1.0)
    assert sorted(calls) == sorted([sorted(id(c) for c in jellies[:2]), sorted(id(c) for c in crabs)])
