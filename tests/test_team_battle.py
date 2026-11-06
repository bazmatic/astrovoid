import json
import random
from unittest.mock import Mock

import pygame
import pytest

import config
from creatures.team_battle import MATCH_PATH, TeamBattle, load_match
from entities.projectile import Projectile
from rendering.battle_view import banner_text
from tests.test_fun_menu import to_fun
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture


def battle(match=None):
    return TeamBattle(match or load_match(), Mock(), rng=random.Random(1))


def kinds(b, side):
    return sorted(c.type for c in b.alive(side))


def test_the_match_file_starts_each_side_in_its_own_third_with_a_free_gate():
    b = battle()
    assert kinds(b, 'flockers') == ['flighthouse'] + ['flocker'] * 14
    assert kinds(b, 'wallcrawlers') == ['wallcrawler'] * 8
    assert kinds(b, 'worms') == ['inchworm'] * 2
    assert max(c.x for c in b.alive('flockers') if c.type == 'flocker') < min(c.x for c in b.alive('worms'))
    assert max(c.x for c in b.alive('worms')) < min(c.x for c in b.alive('wallcrawlers'))
    assert len(b.obstacles.gates) == 1 and b.obstacles.gates[0].motor is None
    b.close()


def test_shots_hurt_only_the_sides_their_side_fights():
    b = battle()
    flocker = next(c for c in b.alive('flockers') if c.type == 'flocker')
    worm = b.alive('worms')[0]
    for shooter in ('flockers', 'wallcrawlers'):              # past its own side, and past the worms nobody fights
        b.shots(shooter).append(Projectile(worm.get_pos(), 0, is_enemy=True))
    b.shots('flockers').append(Projectile(flocker.get_pos(), 0, is_enemy=True))
    b._move_shots(0.0)
    assert flocker.active and worm.active and len(b.shots('flockers')) == len(b.shots('wallcrawlers')) + 1 == 2
    hostile = Projectile(flocker.get_pos(), 0, is_enemy=True)
    b.shots('wallcrawlers').append(hostile)
    b._move_shots(0.0)
    assert not flocker.active and not hostile.active
    b.close()


def test_the_worms_hunt_both_teams_and_nobody_hunts_the_worms():
    from creatures.traits.inchworm import Inchworms
    b = battle()
    worm = b.alive('worms')[0]
    assert set(b.targets('worms')) == set(b.alive('flockers') + b.alive('wallcrawlers'))
    assert worm not in b.targets('flockers') + b.targets('wallcrawlers')
    flocker = next(c for c in b.alive('flockers') if c.type == 'flocker')
    Inchworms._bite(flocker, worm.encounter)
    assert not flocker.active
    b.close()


def test_the_last_contender_standing_wins_and_a_non_contender_does_not_count():
    b = battle()
    enc = b.encounters['flockers']
    for c in b.alive('flockers'):
        if c.type == 'flocker':
            enc.kill(c)
    b._judge()
    assert b.result is None                                  # the Flighthouse still stands
    enc.kill(b.alive('flockers')[0])
    b._judge()
    assert b.alive('worms') and b.result.winner == 'wallcrawlers'
    assert banner_text(b.result) == 'WALLCRAWLERS WIN'
    b.close()


def test_a_side_that_fights_an_unknown_side_is_refused(tmp_path):
    data = json.load(open(MATCH_PATH))
    data['sides']['worms']['fights'] = ['nobody']
    path = tmp_path / 'match.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='nobody'):
        load_match(str(path))


def test_the_battle_plays_from_the_fun_list_and_returns_to_it(game, monkeypatch):
    monkeypatch.setitem(type(game).__init__.__globals__, 'DUEL_BANNER_SECONDS', 0.0)
    to_fun(game)
    key(game, pygame.K_DOWN)
    key(game, pygame.K_RETURN)
    assert game.state == config.STATE_DUEL and isinstance(game.duel, TeamBattle)
    for _ in range(3):
        game.update(1.0)
    game.draw()
    game.duel.timeout_seconds = 0.0
    game.update(1.0)
    assert banner_text(game.duel.result) == 'DRAW: TIME UP'
    game.draw()
    game.update(1.0)
    assert game.state == config.STATE_FUN and game.duel is None


@pytest.mark.parametrize('flora', [True, False, None])
def test_a_match_file_can_say_whether_the_arena_grows_living_weed(tmp_path, flora):
    data = json.load(open(MATCH_PATH))
    data.pop('flora', None)
    if flora is not None:
        data['flora'] = flora
    path = tmp_path / 'match.json'
    path.write_text(json.dumps(data))
    assert load_match(str(path)).flora is flora   # None: the flora setting decides
