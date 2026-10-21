"""The Boss Viber and the Vibelet: Vibers at double and half size, and what an enemy bullet costs."""
from unittest.mock import Mock

import pygame
import pytest

import config
import level_config
import creatures
from entities.projectile import Projectile
from entities.ship import Ship
from game_handlers.collision_handler import CollisionHandler
from hunter.neural.policy import random_policy
import enemy_kinds
from scoring.system import ScoringSystem
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config
from tests.test_neural_hunter import make as make_viber
from tests.test_rules_hunter import SilentWorker


def make(kind):
    return make_viber(kind=kind)


def strength(kind):
    return dict(enemy_kinds.kind(kind).traits)['pilot'].get('shotStrength', 1.0)


def shoot(viber, enc, times):
    alive = []
    for _ in range(times):
        enc.shoot(Projectile(viber.get_pos(), 0.0))
        alive.append(viber.active)
    return alive


def shot_at(ship, strength=1.0):
    return Projectile((ship.x, ship.y), 0.0, source='enemy', strength=strength)


def hit(strength=1.0):
    """A still ship hit by one enemy bullet: the scoring it leaves and the ship's speed afterwards."""
    ship = Ship((300.0, 300.0))
    ship.shield_active = False
    scoring = ScoringSystem()
    scoring.start_level(1)
    handler = CollisionHandler(Mock(), scoring, Mock())
    bullet = shot_at(ship, strength)
    bullet.vx, bullet.vy = 8.0, 0.0
    bullet.x -= 2
    assert handler.handle_projectile_ship_collision(bullet, ship, scoring)
    return scoring, ship


def test_an_enemy_bullet_costs_only_the_bullet_penalty():
    scoring, _ = hit()
    assert scoring.enemy_collisions == 0 and scoring.enemy_bullet_hits == 1


def test_a_half_strength_bullet_costs_half_and_pushes_half_as_hard():
    full_scoring, full_ship = hit()
    half_scoring, half_ship = hit(0.5)
    assert half_scoring.enemy_bullet_hits == 0.5
    assert half_ship.vx == pytest.approx(full_ship.vx / 2) and half_ship.vy == pytest.approx(full_ship.vy / 2)


def test_a_vibelet_bullet_is_almost_harmless():
    scoring, _ = hit(strength('vibelet'))
    assert scoring.enemy_bullet_hits * config.ENEMY_BULLET_PENALTY == pytest.approx(0.5)


def test_the_boss_viber_is_double_size_and_takes_double_the_hits():
    (boss, enc), (viber, _) = make('boss_viber'), make('neural_hunter')
    assert boss.radius == 2 * viber.radius
    assert all(s.strength == 1.0 for s in boss.craft._shots())
    assert shoot(boss, enc, 24) == [True] * 23 + [False]


def test_the_vibelet_is_half_size_dies_to_one_hit_and_its_bullets_are_a_tenth_as_strong():
    (vibelet, enc), (viber, _) = make('vibelet'), make('neural_hunter')
    assert vibelet.radius == viber.radius / 2
    assert all(s.strength == 0.1 and s.is_enemy for s in vibelet.craft._shots())
    assert all(s.strength == 1.0 for s in viber.craft._shots())
    assert shoot(vibelet, enc, 1) == [False]


def test_both_are_enemy_kinds_a_level_can_place_and_say_their_kind():
    for kind in ('boss_viber', 'vibelet', 'neural_hunter'):
        assert kind in enemy_kinds.hunters() and make(kind)[0].type == kind


LAYOUT = {'walls': [], 'start': [1, 1], 'exit': [9, 9],
          'enemies': [{'type': 'boss_viber', 'cell': [7, 2]}, {'type': 'vibelet', 'cell': [2, 7]},
                      {'type': 'vibelet', 'cell': [5, 5]}],
          'beacon': None}


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 11}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: random_policy(0))
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def test_a_layout_places_them_and_the_exit_counts_them_by_kind(played):
    assert level_config.get_level_boss_viber_count(3) == 1 and level_config.get_level_vibelet_count(3) == 2
    assert sorted(h.type for h in played.enemy_hunters) == ['boss_viber', 'vibelet', 'vibelet']
    counts = played.roster.counts()
    assert counts.get('boss_viber') == 1 and counts.get('vibelet') == 2 and 'neural_hunter' not in counts


def test_a_level_file_without_a_layout_can_ask_for_them(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
        'enemies': {'static': 0, 'patrol': 0, 'aggressive': 0, 'boss_viber': 1, 'vibelet': 1}} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: random_policy(0))
    game.level = 3
    game.start_level()
    assert sorted(h.type for h in game.enemy_hunters) == ['boss_viber', 'vibelet']


def test_without_a_neural_model_they_are_left_out(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 11}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), 'enemy_policy', lambda self: None)
    game.level = 3
    game.start_level()
    assert game.enemy_hunters == []


def test_the_editor_offers_and_draws_them():
    from editor.model import PALETTE
    from rendering.level_editor import CHIPS, LABELS
    assert LABELS['boss_viber'] == 'Boss Viber' and LABELS['vibelet'] == 'Vibelet'
    assert {'boss_viber', 'vibelet'} <= set(PALETTE) <= set(CHIPS)
    pygame.init()
    for kind in ('boss_viber', 'vibelet'):
        creatures.build(kind, (400.0, 400.0)).draw(pygame.Surface((800, 800)))


@pytest.mark.parametrize('kind', ['neural_hunter', 'vibelet', 'rules_hunter'])
def test_no_hit_point_bar_is_drawn_above_an_enemy_hunter(kind):
    pygame.init()
    surface = pygame.Surface((800, 800))
    hunter = creatures.build(kind, (400.0, 400.0))
    hunter.draw(surface)
    above = range(0, round(400 - hunter.radius * 1.6))
    assert not any(surface.get_at((x, y))[:3] != (0, 0, 0) for x in range(300, 500) for y in above)


def test_the_boss_viber_has_a_power_bar_above_it_that_drains_as_it_is_hit():
    pygame.init()
    boss, enc = make('boss_viber')
    boss.x, boss.y = 400.0, 400.0
    colour = tuple(enemy_kinds.kind('boss_viber').tuning['color'])

    def bar_pixels():
        surface = pygame.Surface((800, 800))
        boss.draw(surface)
        above = range(0, round(400 - boss.radius * 1.6))
        return sum(1 for x in range(300, 500) for y in above if surface.get_at((x, y))[:3] == colour)

    full = bar_pixels()
    assert full > 0
    shoot(boss, enc, 12)
    assert 0 < bar_pixels() < full


def test_each_kind_says_whether_it_carries_a_bar(monkeypatch):
    from dataclasses import replace
    assert [k for k in enemy_kinds.hunters() if enemy_kinds.kind(k).tuning['showsHitPoints']] == ['boss_viber']
    pygame.init()

    def has_bar(key):
        surface = pygame.Surface((800, 800))
        hunter = creatures.build(key, (400.0, 400.0))
        hunter.draw(surface)
        above = range(0, round(400 - hunter.radius * 1.6))
        return any(surface.get_at((x, y))[:3] != (0, 0, 0) for x in range(300, 500) for y in above)

    for key, shows in (('boss_viber', False), ('vibelet', True), ('rules_hunter', True)):
        entry = enemy_kinds.kind(key)
        monkeypatch.setitem(enemy_kinds._CATALOGUE, key, replace(entry, tuning={**entry.tuning, 'showsHitPoints': shows}))
    assert {k: has_bar(k) for k in ('neural_hunter', 'boss_viber', 'vibelet', 'rules_hunter')} == {
        'neural_hunter': False, 'boss_viber': False, 'vibelet': True, 'rules_hunter': True}
