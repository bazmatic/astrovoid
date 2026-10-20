"""The Enemy Kind catalogue (config/enemies.json): every kind, its names and what the game asks of it."""
import json

import pytest

import enemy_kinds
from entities.command_recorder import CommandRecorder
from game_handlers.spawn_manager import make_enemy

ORDER = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone', 'split_boss',
         'mother_boss', 'rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet', 'baby')


def test_the_kinds_come_in_the_files_order():
    assert enemy_kinds.kinds() == ORDER


def test_the_names_chosen_for_the_game():
    expected = {'static': ('Urchin', 'Urchins'), 'patrol': ('Crab', 'Crabs'), 'aggressive': ('Jelly', 'Jellies'),
                'replay': ('Squiddler', 'Squiddlers'), 'flocker': ('Flocker', 'Flockers'),
                'flighthouse': ('Flighthouse', 'Flighthouses'), 'egg': ('Egg', 'Eggs'),
                'baby': ('Squidlet', 'Squidlets'), 'anemone': ('Anemone', 'Anemones'),
                'split_boss': ('Squiddler Boss', 'Squiddler Bosses'), 'mother_boss': ('Mother', 'Mothers'),
                'rules_hunter': ('Terminator', 'Terminators'), 'neural_hunter': ('Viber', 'Vibers'),
                'boss_viber': ('Boss Viber', 'Boss Vibers'), 'vibelet': ('Vibelet', 'Vibelets')}
    assert {k: (enemy_kinds.name(k), enemy_kinds.plural(k)) for k in enemy_kinds.kinds()} == expected


def test_what_each_kind_is():
    assert enemy_kinds.anchored() == ('flighthouse', 'anemone')
    assert enemy_kinds.hunters() == ('rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet')
    assert [k for k in ORDER if enemy_kinds.kind(k).replays_player] == ['replay', 'split_boss', 'mother_boss', 'baby']
    assert [k for k in ORDER if enemy_kinds.kind(k).par_weight == 'spawningBoss'] == ['split_boss', 'mother_boss']
    assert {k: enemy_kinds.kind(k).pilot for k in enemy_kinds.hunters()} == {
        'rules_hunter': 'rules', 'neural_hunter': 'neural', 'boss_viber': 'neural', 'vibelet': 'neural'}


def test_every_kind_has_a_drawing_layer():
    assert [enemy_kinds.kind(k).layer for k in ORDER] == [0, 0, 0, 1, 2, 4, 9, 3, 5, 6, 7, 7, 7, 7, 8]


@pytest.mark.parametrize('kind', [k for k in ORDER if k not in enemy_kinds.hunters()])
def test_every_kind_but_the_hunters_is_made_by_the_factory_and_says_its_kind(kind):
    enemy = make_enemy(kind, (400.0, 400.0), 5, CommandRecorder())
    assert enemy.type == kind
    # Where it is placed has room for all of it
    largest = enemy_kinds.kind('egg').tuning['maxSize'] if kind == 'egg' else enemy.radius
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
