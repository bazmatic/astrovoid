"""Vibehouses share lighthouse sensing and launch functioning neural Vibelets."""
import pytest

import creatures
import level_config
from tests.test_level_arc import game
from tests.creature_parts import encounter, target, world
from entities.projectile import Projectile


@pytest.mark.parametrize('sighted', ['player', 'ally'])
def test_beam_launches_a_vibelet_at_either_friendly_ship(sighted):
    tower = creatures.build('vibehouse',(400,300))
    ship = target((600,300))
    enc = encounter(tower,world_=world(ship=ship if sighted == 'player' else None,
                                      hunter=ship if sighted == 'ally' else None))
    enc.ready()
    tower.angle = 0
    enc.step(1)
    [child] = [c for c in enc.creatures() if c is not tower]
    assert child.type == 'vibelet' and child.hit_points == 1
    assert child.angle == 0 and child.vx > 0
    assert tower.body.launch_flash == 1
    # A cooldown prevents launching again on the following frame.
    enc.step_creature(tower,1)
    assert len(enc.creatures()) == 2
    for _ in range(5):
        enc.apply_hit(tower,Projectile(tower.get_pos(),0))
    enc.step_creature(tower,600)
    assert not tower.active and len(enc.creatures()) == 2


def test_launched_vibelet_starts_its_neural_pilot(game):
    game.level = 1
    game.start_level()
    game.roster.clear()
    tower = creatures.build('vibehouse',(game.ship.x,game.ship.y))
    game.roster.add(tower)
    game.encounter.ready()
    tower.sees_target = True
    tower.sighted_at = (tower.x+100,tower.y)
    launcher = next(t for t in tower.traits if t.NAME == 'launchesFlock')
    launcher.on_frame(tower,game.encounter,1)
    game.encounter.ready()
    [child] = [c for c in game.encounter.creatures() if c is not tower]
    assert child.type == 'vibelet' and child.flight is not None
    game.encounter.step_creature(child,1)
    game.encounter.close()


def test_level_counts_can_place_vibehouses(monkeypatch,game):
    original = level_config.load_level_config
    monkeypatch.setattr(level_config,'load_level_config',
                        lambda level: {**{k:v for k,v in original(1).items() if k != 'layout'},
                                       'enemies': {'vibehouse': 2}})
    game.level = 1
    game.start_level()
    assert len(game.roster.of_kind('vibehouse')) == 2
