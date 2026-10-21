"""The Anemone as a Creature: rooted to the spot, it pulls the player's ship in, flings it out on contact, and clamps
shut when shot."""
import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config
import creatures
import enemy_kinds
from entities.anemone import AnemoneBody
from entities.command_recorder import CommandRecorder
from entities.explosion import Blast
from entities.projectile import Projectile
from entities.ship import Ship
from game_handlers.collision_handler import CollisionHandler
from tests.creature_parts import encounter, world

POS = (400.0, 300.0)
TRAITS = dict(enemy_kinds.kind('anemone').traits)
PEAK = TRAITS['pullsShip']['strength'] * config.SHIP_THRUST_FORCE


def maze(walls=(), gates=()):
    return SimpleNamespace(cell_size_x=40.0, cell_size_y=40.0, walls=list(walls), spatial_grid=None,
                           gate_segments=list(gates), is_open=lambda pos, radius: True)


def wall(start, end):
    return SimpleNamespace(start=start, end=end, active=True)


def ship_at(dx, dy=0.0, shield=False):
    ship = Ship((POS[0] + dx, POS[1] + dy))
    if not shield:
        ship.deactivate_shield()
    else:
        ship.activate_shield()
    return ship


def setting(ship, *positions, walls=(), gates=()):
    """Anemones at these positions (one at POS by default), the ship, and a level with these walls and gates."""
    anemones = [creatures.build('anemone', pos) for pos in (positions or (POS,))]
    stand_in = world(ship=ship, maze=maze(walls, gates))
    return anemones, encounter(*anemones, world_=stand_in), stand_in


def test_an_anemone_pulls_the_ship_toward_it():
    ship = ship_at(80.0)
    [anemone], enc, _ = setting(ship)
    enc.step(1.0)
    assert isinstance(anemone.body, AnemoneBody)
    assert ship.vx < 0 and ship.vy == pytest.approx(0.0)
    assert 0.0 < anemone.pull_fraction <= 1.0 and math.cos(anemone.pull_angle) == pytest.approx(1.0)


def test_anemones_together_pull_no_harder_than_one():
    ship = ship_at(40.0)   # clear of all three hulls, deep in all three fields
    anemones, enc, _ = setting(ship, *((POS[0], POS[1] + offset) for offset in (-3.0, 0.0, 3.0)))
    enc.step(1.0)
    assert math.hypot(ship.vx, ship.vy) == pytest.approx(PEAK)
    assert all(anemone.pull_fraction > 0 for anemone in anemones)


def test_a_wall_or_a_shield_stops_the_pull():
    between = wall((440.0, 200.0), (440.0, 400.0))
    for ship, walls, gates in ((ship_at(80.0), [between], []), (ship_at(80.0), [], [between]),
                               (ship_at(80.0, shield=True), [], [])):
        _, enc, _ = setting(ship, walls=walls, gates=gates)
        enc.step(1.0)
        assert (ship.vx, ship.vy) == (0.0, 0.0)


def test_touching_it_flings_the_ship_out_and_it_lets_go():
    ship = ship_at(10.0)
    ship.vx = -3.0
    [anemone], enc, stand_in = setting(ship)
    enc.step(1.0)
    fling = TRAITS['flingsShip']
    assert stand_in.scoring.record_enemy_collision.call_count == 1
    assert (ship.vx, ship.vy) == pytest.approx((fling['speed'], 0.0))
    assert math.hypot(ship.x - POS[0], ship.y - POS[1]) > anemone.radius + ship.radius
    assert anemone.flinch_timer == fling['releaseFrames'] and anemone.get_pos() == POS
    enc.step(1.0)   # it lets go: no pull back in, no second sting
    assert ship.vx == pytest.approx(fling['speed']) and stand_in.scoring.record_enemy_collision.call_count == 1


def test_a_hit_clamps_it_shut_for_90_frames():
    ship = ship_at(80.0)
    [anemone], enc, _ = setting(ship)
    enc.step(1.0)
    ship.vx = ship.vy = 0.0
    assert enc.shoot(Projectile(POS, 0.0))
    assert anemone.active and anemone.flinch_timer == 90
    for _ in range(89):
        enc.step(1.0)
    assert (ship.vx, ship.vy) == (0.0, 0.0)
    enc.step(1.0)
    assert ship.vx < 0


def test_four_hits_kill_it():
    [anemone], enc, stand_in = setting(ship_at(500.0))
    enc.step(1.0)
    for _ in range(3):
        enc.shoot(Projectile(POS, 0.0))
    assert anemone.active
    enc.shoot(Projectile(POS, 0.0))
    assert not anemone.active
    stand_in.collision_handler.drop_pickup.assert_called_once()


def test_a_blast_does_not_uproot_an_anchored_creature():
    [anemone], enc, _ = setting(ship_at(500.0))
    enc.step(1.0)
    handler = CollisionHandler(Mock(), Mock(), CommandRecorder())
    handler.handle_blast(Blast((POS[0] - 20.0, POS[1]), 60.0, damage=0, push=8.0), None, None, [anemone],
                         lambda shot: False)
    enc.step(1.0)
    assert anemone.get_pos() == POS and (anemone.vx, anemone.vy) == (0.0, 0.0)
