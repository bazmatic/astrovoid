"""Inflation changes appearance/target size temporarily and makes the next hit lethal."""
from dataclasses import replace
from unittest.mock import Mock
import pygame
import pytest

import config
from creatures.traits.combat import TakesHits
from entities.projectile import Projectile
from weapons import CATALOG
from weapons.catalog import WeaponCatalog
from weapons.projectile import make_projectile
from weapons.simulation import advance
from tests.creature_parts import creature,encounter,world
from tests.test_level_arc import game


def inflated(hits=50,seconds=None):
    target=creature([TakesHits(hits)],pos=(450,300))
    enc=encounter(target)
    definition=CATALOG['inflator']
    if seconds is not None:
        definition=replace(definition,inflation_seconds=seconds)
    enc.apply_hit(target,make_projectile(target.get_pos(),0,'player',definition))
    return target,enc


def test_first_hit_inflates_without_damage_even_for_one_hit_creature():
    target,enc=inflated(hits=1)
    assert target.active and target.hit_points == 1
    assert target.hit_radius == target.radius*CATALOG['inflator'].inflation_scale
    assert target.inflation.active
    assert enc.hits['player'] == 1
    enc.world.sound_manager.play_inflation.assert_called_once_with()


@pytest.mark.parametrize('followup',['basic','inflator','railgun','scattergun'])
def test_any_followup_pops_full_health_creature_and_credits_shooter(followup):
    target,enc=inflated()
    enc.apply_hit(target,make_projectile(target.get_pos(),0,'hunter',CATALOG[followup]))
    assert not target.active and target.hit_points == 0
    assert target.killed_by == 'hunter'
    assert target.killed_by_weapon == followup
    enc.world.sound_manager.play_inflation.assert_called_once_with()
    enc.world.collision_handler.record_kill.assert_called_once()


def test_expiry_shrinks_to_original_size_and_restores_ordinary_damage():
    target,enc=inflated(seconds=2)
    radius=target.radius
    enc.step(2*config.FPS-1)
    assert target.inflation.active and radius < target.hit_radius < radius*5
    enc.step(1)
    assert not target.inflation.active and target.hit_radius == radius
    enc.apply_hit(target,Projectile(target.get_pos(),0))
    assert target.active and target.hit_points == 49


def test_expanded_outline_can_be_hit_by_legacy_and_new_shots():
    for modern in (False,True):
        target,enc=inflated()
        position=(target.x,target.y+target.radius*3)
        if modern:
            p=make_projectile(position,0,'player',CATALOG['basic'])
            advance(p,1,enc.world.maze,[target],enc.apply_hit,Mock())
        else:
            enc.shoot(Projectile(position,0))
        assert not target.active


def test_blast_pops_the_enlarged_target_and_uses_normal_kill_accounting(game):
    from game_handlers.spawn_manager import make_enemy
    from entities.explosion import Blast
    game.level=1
    game.start_level()
    game.roster.clear()
    target=make_enemy('static',(600,400),1,game.command_recorder)
    game.roster.add(target)
    game.encounter.ready()
    game.encounter.apply_hit(target,make_projectile(target.get_pos(),0,'player',CATALOG['inflator']))
    game.collision_handler.explosions.trigger(Blast((target.x,target.y+target.radius*4),5,source='player'))
    game._update_explosions(1)
    assert not target.active and game.collision_handler.level_kills == 1


def test_bloated_body_draws_larger_without_changing_navigation_radius(game):
    game.level=1
    game.start_level()
    target=game.encounter.creatures()[0]
    target.x,target.y=300,300
    radius=target.radius
    def image():
        surface=pygame.Surface((600,600),pygame.SRCALPHA)
        target.draw(surface)
        return surface.get_bounding_rect()
    normal=image()
    game.encounter.apply_hit(target,make_projectile(target.get_pos(),0,'player',CATALOG['inflator']))
    large=image()
    assert large.width > normal.width*3 and large.height > normal.height*3
    assert target.radius == radius


def test_configured_duration_and_size_are_in_recorded_weapon_tuning():
    definition=CATALOG['inflator']
    assert definition.inflation_seconds == config.SETTINGS.powerups.inflationDurationSeconds
    assert definition.inflation_scale == config.SETTINGS.powerups.inflationSizeMultiplier
    restored=WeaponCatalog(type(definition)(**data) for data in CATALOG.snapshot())
    assert restored['inflator'] == definition
