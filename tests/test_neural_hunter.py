"""The Viber: a Creature whose neural pilot flies a hunter ship that hunts only the player."""
import copy
import logging

import pygame
import pytest

import creatures
import enemy_kinds
import level_config
from entities.hunter_ship import HunterShip
from entities.projectile import Projectile
from hunter.neural.policy import random_policy
from tests.creature_parts import encounter, pilot_world
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config
from tests.test_rules_hunter import SilentWorker, target

VIBER_KINDS = ('neural_hunter', 'boss_viber', 'vibelet')
MAGENTA = tuple(enemy_kinds.kind('neural_hunter').tuning['color'])


def make(policy=None, kind='neural_hunter', no_model=False):
    """A Viber at (500, 500) set up on a level with a protagonist; and its Encounter."""
    hunter = creatures.build(kind, (500.0, 500.0))
    enc = encounter(hunter, world_=pilot_world(target(), policy=None if no_model else policy or random_policy(0)))
    enc.ready()
    return hunter, enc


def test_it_is_an_enemy_type_a_level_can_place():
    assert 'neural_hunter' in enemy_kinds.kinds()


def test_it_is_magenta_not_the_rules_red_or_the_allied_green():
    assert MAGENTA not in (tuple(enemy_kinds.kind('rules_hunter').tuning['color']), HunterShip.COLOR)
    red, green, blue = MAGENTA
    assert red > 200 and blue > 200 and green < 120


def test_it_flies_on_the_neural_pilot_and_its_shots_join_the_level():
    hunter, enc = make()
    for _ in range(60):
        enc.step(1.0)
    assert hunter.flight.controller.kind == 'neural'
    assert all(s.is_enemy for s in enc.world.projectiles)


def test_its_shots_are_enemy_shots():
    hunter, _ = make()
    assert all(s.is_enemy and s.source == 'enemy' and s.dynamic_color == MAGENTA for s in hunter.craft._shots())


def test_twelve_hits_destroy_it():
    hunter, enc = make()
    alive = []
    for _ in range(12):
        enc.shoot(Projectile(hunter.get_pos(), 0.0))
        alive.append(hunter.active)
    assert alive == [True] * 11 + [False]


def test_without_a_policy_it_is_drawn_but_never_flies():
    hunter, enc = make(no_model=True)
    for _ in range(10):
        enc.step(1.0)
    assert hunter.flight is None and hunter.get_pos() == (500.0, 500.0)
    pygame.init()
    hunter.draw(pygame.Surface((800, 800)))


def test_a_copy_for_the_death_portrait_carries_no_pilot():
    hunter, _ = make()
    clone = copy.deepcopy(hunter)
    assert clone.flight is None and hunter.flight is not None


LAYOUT = {'walls': [], 'start': [1, 1], 'exit': [7, 7],
          'enemies': [{'type': 'neural_hunter', 'cell': [6, 2]}, {'type': 'rules_hunter', 'cell': [2, 6]}],
          'beacon': None}


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: random_policy(0))
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def test_a_layout_places_a_neural_hunter_at_its_cell(played):
    calc = played.maze.position_calculator
    neural = [h for h in played.enemy_hunters if h.type == 'neural_hunter']
    assert [calc.screen_to_grid(*h.get_pos()) for h in neural] == [(6, 2)]
    assert neural[0] in list(played.roster.alive())


def test_it_hunts_only_the_player(played):
    neural = next(h for h in played.enemy_hunters if h.type == 'neural_hunter')
    assert neural.flight.surroundings.enemies() == [played.ship]


def test_the_players_shots_wear_it_down(played):
    neural = next(h for h in played.enemy_hunters if h.type == 'neural_hunter')
    played.encounter.shoot(Projectile(neural.get_pos(), 0.0, source='player'))
    assert neural.hit_points == 11


def test_the_level_flies_and_draws_it(played):
    for _ in range(30):
        played.encounter.step(1.0)
    pygame.init()
    played.roster.draw(pygame.Surface((3840, 2160)))
    played._close_enemy_hunters()


def test_without_a_neural_model_the_level_starts_without_it(game, monkeypatch, caplog):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: None)
    game._rules_worker_factory = SilentWorker
    game.level = 3
    with caplog.at_level(logging.WARNING):
        game.start_level()
    assert not any(h.type in VIBER_KINDS for h in game.enemy_hunters)
    assert any(h.type == 'rules_hunter' for h in game.enemy_hunters)
    assert 'neural' in caplog.text.lower()


def test_a_level_file_can_ask_for_neural_hunters_by_count(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
        'enemies': {'static': 1, 'patrol': 0, 'aggressive': 0, 'neural_hunter': 1}} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: random_policy(0))
    assert level_config.get_level_neural_hunter_count(3) == 1
    game.level = 3
    game.start_level()
    assert sum(h.type == 'neural_hunter' for h in game.enemy_hunters) == 1


def test_without_a_model_no_viber_is_placed_and_the_level_still_plays(game, monkeypatch, caplog):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: None)
    game.level = 21
    with caplog.at_level(logging.WARNING):
        game.start_level()
    kinds = game.roster.counts()
    assert not any(kinds.get(k) for k in VIBER_KINDS)
    assert 'neural' in caplog.text.lower()
    assert kinds.get('static') and kinds.get('anemone')            # the rest of the level is there
    from policies.exit import AllCleared
    game.exit_policy = AllCleared()                                 # the strictest exit: every enemy placed
    assert not game.exit_policy.is_open(game.exit_state())
    for enemy in list(game.roster.alive()):
        enemy.die()
    assert game.exit_policy.is_open(game.exit_state())
