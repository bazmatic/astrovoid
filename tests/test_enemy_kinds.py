"""The Enemy Kind catalogue (config/enemies.json): every kind, its names and what the game asks of it."""
import json

import pytest

import enemy_kinds
from entities.command_recorder import CommandRecorder
from game_handlers.spawn_manager import make_enemy


@pytest.mark.parametrize('kind', [k for k in enemy_kinds.kinds() if k not in enemy_kinds.hunters()])
def test_every_kind_but_the_hunters_is_made_by_the_factory_and_says_its_kind(kind, monkeypatch):
    monkeypatch.setenv('SCRIPTED_JELLIES', '1')   # by default the factory swaps the scripted Jelly for the neural one
    enemy = make_enemy(kind, (400.0, 400.0), 5, CommandRecorder())
    assert enemy.type == kind
    # Where it is placed has room for all of it
    largest = dict(enemy_kinds.kind('egg').traits)['grows']['to'] if kind == 'egg' else enemy.radius
    assert enemy_kinds.kind(kind).spawn_radius == 0 or enemy_kinds.kind(kind).spawn_radius >= largest


@pytest.mark.parametrize('change, message', [
    (lambda e: e.pop('anchored'), "missing ['anchored']"),
    (lambda e: e.update(colour='red'), "unknown ['colour']"),
    (lambda e: e.update(parWeight='huge'), 'parWeight'),
])
def test_a_kind_the_file_gets_wrong_stops_the_game_at_startup(tmp_path, change, message):
    raw = json.loads(open('config/enemies.json').read())
    change(raw['patrol'])
    path = tmp_path / 'enemies.json'
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="'patrol'.*" + message.replace('[', r'\[').replace(']', r'\]')):
        enemy_kinds.load(str(path))
