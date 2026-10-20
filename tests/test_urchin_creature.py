"""The Urchin as a Creature: built from the catalogue, in a real level, in the editor preview and in the death
portrait."""
import copy

import pygame

import creatures
from creatures.encounter import Encounter
from entities.projectile import Projectile
from entities.urchin import Urchin
from tests.creature_parts import encounter
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture

POS = (400.0, 300.0)


def lit(screen):
    return pygame.mask.from_surface(screen, 1).count()


def test_the_catalogue_builds_an_urchin():
    urchin = creatures.build('static', POS)
    assert isinstance(urchin.body, Urchin)
    assert urchin.allegiance == 'enemy'


def test_an_urchin_in_a_real_level_takes_three_shots(game):
    game.start_level()
    urchins = game.roster.of_kind('static')
    assert urchins and all(isinstance(u.body, Urchin) for u in urchins)
    urchin = urchins[0]
    game.encounter.step(1.0)
    for _ in range(2):
        assert game.encounter.shoot(Projectile(urchin.get_pos(), 0, source='player'))
        assert urchin.active
    assert game.encounter.shoot(Projectile(urchin.get_pos(), 0, source='player'))
    assert not urchin.active
    assert game.collision_handler.last_player_kill is not None


def test_a_fresh_urchin_draws():
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    creatures.build('static', POS).draw(screen)
    assert lit(screen) > 0


def test_a_dead_urchin_copies_for_its_portrait():
    urchin = creatures.build('static', POS)
    enc = encounter(urchin)
    enc.step(1.0)
    enc.kill(urchin)
    portrait = copy.deepcopy(urchin)
    assert portrait is not urchin and portrait.body is not urchin.body
    assert not any(isinstance(value, Encounter) for value in vars(portrait).values())
    portrait.update_death(5.0)
    screen = pygame.Surface((800, 600), pygame.SRCALPHA)
    portrait.draw_death(screen)
    assert lit(screen) > 0
