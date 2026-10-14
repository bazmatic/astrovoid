# tests/test_rules_hunter.py
"""The Rules hunter: the Rules pilot's hunter ship as an enemy that hunts only its protagonist."""
import copy
from types import SimpleNamespace

import pygame
import pytest

from entities.hunter_ship import HunterShip
from entities.rules_hunter import RULES_HUNTER_HIT_POINTS, RulesHunter
from hunter.surroundings import ProtagonistSurroundings
from tests.test_senses import world


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


def make(game=None, worker=None):
    game = game or FakeGame(target())
    worker = worker or SilentWorker()
    return RulesHunter((500.0, 500.0), worker, ProtagonistSurroundings(game)), worker, game


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


def test_it_flies_without_a_target_and_returns_a_list():
    hunter, _, _ = make(FakeGame(None))
    for _ in range(30):
        assert hunter.fly(1.0) == []


def test_twelve_hits_destroy_it_and_the_twelfth_reports_it():
    hunter, _, _ = make()
    assert hunter.hit_points == hunter.max_hit_points == RULES_HUNTER_HIT_POINTS == 12
    assert [hunter.take_damage() for _ in range(12)] == [False] * 11 + [True]


def test_its_shots_are_enemy_shots():
    hunter, _, _ = make()
    shots = hunter._shots()
    assert shots and all(s.is_enemy and s.source == 'enemy' for s in shots)


def test_the_normal_hunters_shots_are_still_the_hunters():
    shots = HunterShip((100.0, 100.0))._shots()
    assert all(s.source == 'hunter' and not s.is_enemy for s in shots)


def test_dying_stops_its_pilot_and_its_worker():
    hunter, worker, _ = make()
    hunter.die()
    assert not hunter.active and hunter.is_dying and worker.closed
    assert hunter.fly(1.0) == []


def test_a_copy_for_the_death_portrait_carries_no_pilot_worker_or_game():
    hunter, _, game = make()
    clone = copy.deepcopy(hunter)
    assert clone.flight is None and clone._worker is None and clone.surroundings is None
    assert (clone.x, clone.y, clone.radius) == (hunter.x, hunter.y, hunter.radius)
    assert hunter.flight is not None                     # the original is untouched


def test_the_copy_plays_a_death_portrait():
    from rendering.enemy_death_portrait import EnemyDeathPortrait
    pygame.init()
    hunter, _, _ = make()
    hunter.die()
    portrait = EnemyDeathPortrait(hunter, 20)
    portrait.update(10.0)
    portrait.draw(pygame.Surface((200, 200)), (100, 100))


def test_it_draws_red_with_a_health_bar_that_shrinks():
    pygame.init()
    hunter, _, _ = make()

    def red_pixels():
        screen = pygame.Surface((300, 300))
        hunter.x, hunter.y = 150.0, 150.0
        hunter.draw(screen)
        return sum(1 for x in range(300) for y in range(300)
                   if screen.get_at((x, y))[0] > screen.get_at((x, y))[1] + 40)

    full = red_pixels()
    assert full > 0
    for _ in range(6):
        hunter.take_damage()
    assert red_pixels() < full                          # the bar has lost half its fill


def test_its_colours_are_not_the_allied_hunters():
    assert RulesHunter.COLOR != HunterShip.COLOR
    assert RulesHunter.COLOR[0] > RulesHunter.COLOR[1]   # red


def test_it_fires_at_a_protagonist_in_the_open_in_a_few_seconds():
    """The real Rules pilot, answered at once, aims at what it is shown."""
    from experiments.harness import SyncWorker
    from hunter.rule_params import RULES
    clock_time = [1000.0]
    game = FakeGame(target(x=640.0, y=500.0))
    hunter = RulesHunter((500.0, 500.0), SyncWorker(RULES, lambda: clock_time[0]),
                         ProtagonistSurroundings(game), clock=lambda: clock_time[0])
    fired = []
    for _ in range(6 * 60):
        clock_time[0] += 1 / 60
        fired += hunter.fly(1.0)
    assert fired and all(s.is_enemy for s in fired)
