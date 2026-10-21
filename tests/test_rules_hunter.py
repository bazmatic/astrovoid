# tests/test_rules_hunter.py
"""The Terminator: a Creature whose rules pilot flies a hunter ship that hunts only its protagonist."""
import copy
from types import SimpleNamespace

import pygame
import pytest

import creatures
import enemy_kinds
from creatures.traits import piloted
from entities.hunter_ship import HunterShip
from entities.hunter_ship_body import HunterShipBody
from entities.projectile import Projectile
from hunter.surroundings import ProtagonistSurroundings
from tests.creature_parts import encounter, pilot_world
from tests.test_senses import world

RED = tuple(enemy_kinds.kind('rules_hunter').tuning['color'])


class FakeGame:
    """Just what ProtagonistSurroundings reads from a game."""

    def __init__(self, protagonist, projectiles=()):
        self.maze = world()
        self._protagonist = protagonist
        self.projectiles = list(projectiles)

    def protagonist(self):
        return self._protagonist


class Target:
    """A stand-in protagonist (perception keeps weak references to what it sees, so not a SimpleNamespace)."""

    def __init__(self, x, y, active):
        self.x, self.y, self.vx, self.vy, self.radius, self.active = x, y, 0.0, 0.0, 8, active

    def get_pos(self):
        return (self.x, self.y)


def target(x=700.0, y=500.0, active=True):
    return Target(x, y, active)


def shot(is_enemy):
    return SimpleNamespace(is_enemy=is_enemy, active=True, x=0.0, y=0.0, vx=0.0, vy=0.0, radius=3)


class SilentWorker:
    """A pilot worker that never answers, and records that it was closed."""
    busy = False

    def __init__(self):
        self.closed = False

    def submit(self, observation):
        return True

    def poll(self):
        return None

    def cancel(self):
        pass

    def close(self):
        self.closed = True


def make(protagonist=None, worker=None):
    """A Terminator at (500, 500) set up on a level; its worker; and its Encounter."""
    worker = worker or SilentWorker()
    hunter = creatures.build('rules_hunter', (500.0, 500.0))
    enc = encounter(hunter, world_=pilot_world(protagonist or target(), lambda: worker))
    enc.ready()
    return hunter, worker, enc


def test_it_is_shown_only_its_protagonist_and_the_protagonists_shots():
    mine, theirs = shot(False), shot(True)
    game = FakeGame(target(), [mine, theirs])
    view = ProtagonistSurroundings(game)
    assert view.enemies() == [game.protagonist()]
    assert view.threats() == [mine]                      # enemy shots are not a threat to an enemy
    assert view.pickups() == [] and view.friend() is None
    assert view.maze is game.maze


def test_a_dead_or_missing_protagonist_leaves_it_nothing_to_hunt():
    assert ProtagonistSurroundings(FakeGame(target(active=False))).enemies() == []
    assert ProtagonistSurroundings(FakeGame(None)).enemies() == []


def test_it_flies_without_a_target_and_fires_nothing():
    hunter, _, enc = make(protagonist=target(active=False))
    for _ in range(30):
        enc.step(1.0)
    assert enc.world.projectiles == []


def test_twelve_hits_destroy_it_and_only_the_twelfth():
    hunter, _, enc = make()
    assert hunter.hit_points == hunter.max_hit_points == 12
    alive = []
    for _ in range(12):
        assert enc.shoot(Projectile(hunter.get_pos(), 0.0))
        alive.append(hunter.active)
    assert alive == [True] * 11 + [False]


def test_its_shots_are_enemy_shots_in_its_colour():
    hunter, _, _ = make()
    shots = hunter.craft._shots()
    assert shots and all(s.is_enemy and s.source == 'enemy' and s.dynamic_color == RED for s in shots)


def test_the_normal_hunters_shots_are_still_the_hunters():
    shots = HunterShip((100.0, 100.0))._shots()
    assert all(s.source == 'hunter' and not s.is_enemy for s in shots)


def test_dying_stops_its_pilot_and_its_worker():
    hunter, worker, enc = make()
    enc.kill(hunter)
    assert not hunter.active and hunter.is_dying and worker.closed and hunter.flight is None
    enc.step(1.0)
    assert enc.world.projectiles == []


def test_a_copy_for_the_death_portrait_carries_no_pilot_or_worker():
    hunter, _, _ = make()
    clone = copy.deepcopy(hunter)
    assert clone.flight is None and clone.pilot_worker is None
    assert (clone.x, clone.y, clone.radius) == (hunter.x, hunter.y, hunter.radius)
    assert hunter.flight is not None                     # the original is untouched


def test_the_copy_plays_a_death_portrait():
    from rendering.enemy_death_portrait import EnemyDeathPortrait
    pygame.init()
    hunter, _, enc = make()
    enc.kill(hunter)
    portrait = EnemyDeathPortrait(hunter, 20)
    portrait.update(10.0)
    portrait.draw(pygame.Surface((200, 200)), (100, 100))


def test_it_draws_red():
    pygame.init()
    hunter, _, _ = make()
    assert isinstance(hunter.body, HunterShipBody)
    screen = pygame.Surface((300, 300))
    hunter.x, hunter.y = 150.0, 150.0
    hunter.draw(screen)
    assert any(screen.get_at((x, y))[0] > screen.get_at((x, y))[1] + 40 for x in range(300) for y in range(300))


def test_its_colours_are_not_the_allied_hunters():
    assert RED != HunterShip.COLOR
    assert RED[0] > RED[1]   # red


def test_it_fires_at_a_protagonist_in_the_open_in_a_few_seconds(monkeypatch):
    """The real Rules pilot, answered at once, aims at what it is shown."""
    from experiments.harness import SyncWorker
    from hunter.rule_params import RULES
    clock_time = [1000.0]
    monkeypatch.setattr(piloted, 'monotonic', lambda: clock_time[0])
    hunter, _, enc = make(protagonist=target(x=640.0, y=500.0),
                          worker=SyncWorker(RULES, lambda: clock_time[0]))
    for _ in range(6 * 60):
        clock_time[0] += 1 / 60
        enc.step(1.0)
    fired = enc.world.projectiles
    assert fired and all(s.is_enemy for s in fired)
