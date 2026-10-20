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
import enemy_kinds
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


def test_a_vibelet_bullet_is_almost_harmless():
    scoring, _ = hit(enemy_kinds.kind('vibelet').hunter.shot_strength)
    assert scoring.enemy_bullet_hits * config.ENEMY_BULLET_PENALTY == pytest.approx(0.5)


def test_the_boss_viber_is_double_size_and_takes_double_the_hits():
    boss, viber = make(BossViber), make(NeuralHunter)
    assert boss.radius == 2 * viber.radius
    assert [boss.take_damage() for _ in range(24)] == [False] * 23 + [True]
    assert all(s.strength == 1.0 for s in boss._shots())


def test_the_vibelet_is_half_size_dies_to_one_hit_and_its_bullets_are_a_tenth_as_strong():
    vibelet, viber = make(Vibelet), make(NeuralHunter)
    assert vibelet.radius == viber.radius / 2
    assert vibelet.take_damage()
    assert all(s.strength == 0.1 and s.is_enemy for s in vibelet._shots())
    assert all(s.strength == 1.0 for s in viber._shots())


def test_both_are_enemy_kinds_a_level_can_place_and_say_their_kind():
    for kind, cls in (('boss_viber', BossViber), ('vibelet', Vibelet), ('neural_hunter', NeuralHunter)):
        assert kind in enemy_kinds.hunters() and make(cls).type == kind


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
    counts = played.roster.counts()
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


@pytest.mark.parametrize('kind', ['neural_hunter', 'vibelet', 'rules_hunter'])
def test_no_hit_point_bar_is_drawn_above_an_enemy_hunter(kind):
    from entities.neural_hunter import VIBERS
    from entities.rules_hunter import RulesHunter
    pygame.init()
    surface = pygame.Surface((800, 800))
    hunter = (RulesHunter((400.0, 400.0), SilentWorker(), None) if kind == 'rules_hunter'
              else VIBERS[kind]((400.0, 400.0), None, None))
    hunter.draw(surface)
    above = range(0, round(400 - hunter.radius * 1.6))
    assert not any(surface.get_at((x, y))[:3] != (0, 0, 0) for x in range(300, 500) for y in above)


def test_the_boss_viber_has_a_power_bar_above_it_that_drains_as_it_is_hit():
    pygame.init()
    boss = BossViber((400.0, 400.0), None, None)

    def bar_pixels():
        surface = pygame.Surface((800, 800))
        boss.draw(surface)
        above = range(0, round(400 - boss.radius * 1.6))
        return sum(1 for x in range(300, 500) for y in above if surface.get_at((x, y))[:3] == BossViber.COLOR)

    full = bar_pixels()
    assert full > 0
    for _ in range(12):
        boss.take_damage()
    assert 0 < bar_pixels() < full


def test_each_kind_says_whether_it_carries_a_bar(monkeypatch):
    from dataclasses import replace
    from entities.rules_hunter import RulesHunter
    assert [k for k in enemy_kinds.hunters() if enemy_kinds.kind(k).hunter.shows_hit_points] == ['boss_viber']
    for key, shows in (('boss_viber', False), ('vibelet', True), ('rules_hunter', True)):
        entry = enemy_kinds.kind(key)
        monkeypatch.setitem(enemy_kinds._CATALOGUE, key, replace(entry, hunter=replace(entry.hunter, shows_hit_points=shows)))
    shows = {cls.__name__: cls((400.0, 400.0), *((SilentWorker(), None) if cls is RulesHunter else (None, None)))
             .shows_hit_points() for cls in (NeuralHunter, BossViber, Vibelet, RulesHunter)}
    assert shows == {'NeuralHunter': False, 'BossViber': False, 'Vibelet': True, 'RulesHunter': True}
