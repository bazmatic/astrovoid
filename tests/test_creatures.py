"""A Creature is built from its kind's catalogue entry: a Body and Traits, checked when the game starts."""
from dataclasses import replace

import pytest

import creatures
import enemy_kinds
from creatures import registry
from creatures.trait import Trait


class _Body:
    DEATH_DURATION = 10.0
    DEATH_FRICTION = 0.9

    def __init__(self, creature):
        self.creature = creature

    def update(self, creature, dt, target):
        pass

    def draw(self, screen, creature):
        pass

    def update_death(self, creature, dt):
        pass

    def draw_death(self, screen, creature):
        pass

    def on_event(self, creature, name):
        pass


class _First(Trait):
    NAME = 'first'

    def __init__(self, strength: int = 1):
        self.strength = strength


class _Second(Trait):
    NAME = 'second'
    REQUIRES = ('first',)


@pytest.fixture
def test_parts(monkeypatch):
    monkeypatch.setitem(registry.TRAITS, 'first', _First)
    monkeypatch.setitem(registry.TRAITS, 'second', _Second)
    monkeypatch.setitem(registry.BODIES, 'testBody', _Body)


def _catalogue(traits):
    return {'static': replace(enemy_kinds.kind('static'), body='testBody', traits=traits)}


@pytest.mark.parametrize('traits, problem', [
    ((('nosuch', {}),), 'nosuch'),
    ((('first', {'colour': 'red'}),), 'colour'),
    ((('second', {}),), 'first'),
])
def test_the_catalogue_rejects_an_unknown_trait_a_bad_parameter_and_a_missing_requirement(test_parts, traits, problem):
    with pytest.raises(ValueError, match='static') as raised:
        registry.validate(_catalogue(traits))
    assert problem in str(raised.value)


def test_the_catalogue_rejects_an_unknown_body(test_parts):
    catalogue = {'static': replace(enemy_kinds.kind('static'), body='nosuch', traits=())}
    with pytest.raises(ValueError, match='static'):
        registry.validate(catalogue)


def test_build_gives_the_kinds_size_and_traits_in_order(test_parts, monkeypatch):
    kind = replace(enemy_kinds.kind('static'), body='testBody',
                   traits=(('first', {'strength': 3}), ('second', {})))
    monkeypatch.setitem(enemy_kinds._CATALOGUE, 'static', kind)
    creature = creatures.build('static', (10.0, 20.0), 4, None)
    assert creature.type == 'static'
    assert creature.get_pos() == (10.0, 20.0)
    assert creature.radius == kind.tuning['size']
    assert creature.level == 4
    assert [type(t) for t in creature.traits] == [_First, _Second]
    assert creature.traits[0].strength == 3
    assert isinstance(creature.body, _Body) and creature.body.creature is creature


def test_allegiance_must_be_friend_or_enemy(tmp_path):
    import json
    raw = json.loads(open('config/enemies.json').read())
    raw['static']['allegiance'] = 'neutral'
    path = tmp_path / 'enemies.json'
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='static'):
        enemy_kinds.load(str(path))
