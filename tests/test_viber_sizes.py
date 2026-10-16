"""The Boss Viber and the Vibelet: Vibers at double and half size, and what an enemy bullet costs."""
from unittest.mock import Mock

import pygame
import pytest

import config
import level_config
from entities.neural_hunter import BossViber, NeuralHunter, Vibelet
from entities.projectile import Projectile
from entities.ship import Ship
from game_handlers.collision_handler import CollisionHandler
from hunter.neural.policy import random_policy
from hunter.surroundings import ProtagonistSurroundings
from level_layout import ENEMY_TYPES, HUNTER_KINDS
from scoring.system import ScoringSystem
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_layout_play import real_level_config
from tests.test_rules_hunter import FakeGame, SilentWorker, target


def make(cls):
    return cls((500.0, 500.0), random_policy(0), ProtagonistSurroundings(FakeGame(target())))


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


def test_a_vibelet_bullet_costs_two_and_a_half_points():
    scoring, _ = hit(0.5)
    assert scoring.enemy_bullet_hits * config.ENEMY_BULLET_PENALTY == 2.5


def test_the_boss_viber_is_double_size_and_takes_double_the_hits():
    boss, viber = make(BossViber), make(NeuralHunter)
    assert boss.radius == 2 * viber.radius
    assert [boss.take_damage() for _ in range(24)] == [False] * 23 + [True]
    assert all(s.strength == 1.0 for s in boss._shots())


def test_the_vibelet_is_half_size_with_half_the_hits_and_half_strength_bullets():
    vibelet, viber = make(Vibelet), make(NeuralHunter)
    assert vibelet.radius == viber.radius / 2
    assert [vibelet.take_damage() for _ in range(6)] == [False] * 5 + [True]
    assert all(s.strength == 0.5 and s.is_enemy for s in vibelet._shots())
    assert all(s.strength == 1.0 for s in viber._shots())


def test_both_are_enemy_kinds_a_level_can_place_and_say_their_kind():
    for kind, cls in (('boss_viber', BossViber), ('vibelet', Vibelet), ('neural_hunter', NeuralHunter)):
        assert kind in ENEMY_TYPES and kind in HUNTER_KINDS and make(cls).type == kind


LAYOUT = {'walls': [], 'start': [1, 1], 'exit': [9, 9],
          'enemies': [{'type': 'boss_viber', 'cell': [7, 2]}, {'type': 'vibelet', 'cell': [2, 7]},
                      {'type': 'vibelet', 'cell': [5, 5]}],
          'beacon': None}


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 11}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: random_policy(0))
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def test_a_layout_places_them_and_the_exit_counts_them_by_kind(played):
    assert level_config.get_level_boss_viber_count(3) == 1 and level_config.get_level_vibelet_count(3) == 2
    assert sorted(type(h).__name__ for h in played.enemy_hunters) == ['BossViber', 'Vibelet', 'Vibelet']
    counts = played.entity_manager.active_counts()
    assert counts.get('boss_viber') == 1 and counts.get('vibelet') == 2 and 'neural_hunter' not in counts


def test_a_level_file_without_a_layout_can_ask_for_them(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
        'enemies': {'static': 0, 'patrol': 0, 'aggressive': 0, 'boss_viber': 1, 'vibelet': 1}} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: random_policy(0))
    game.level = 3
    game.start_level()
    assert sorted(h.type for h in game.enemy_hunters) == ['boss_viber', 'vibelet']


def test_without_a_neural_model_they_are_left_out(game, monkeypatch):  # noqa: F811
    real_level_config(monkeypatch)
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 11}, 'layout': LAYOUT} if level == 3 else None)
    monkeypatch.setattr(type(game), '_load_enemy_policy', lambda self: None)
    game.level = 3
    game.start_level()
    assert game.enemy_hunters == []


def test_the_editor_offers_and_draws_them():
    from editor.model import PALETTE
    from rendering.level_editor import CHIPS, LABELS
    assert LABELS['boss_viber'] == 'Boss Viber' and LABELS['vibelet'] == 'Vibelet'
    assert {'boss_viber', 'vibelet'} <= set(PALETTE) <= set(CHIPS)
    pygame.init()
    for cls in (BossViber, Vibelet):
        cls((400.0, 400.0), None, None).draw(pygame.Surface((800, 800)))
