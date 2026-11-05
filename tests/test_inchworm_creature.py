"""Articulated movement, combat, interruption and solver lifetime in an Encounter."""
import copy
import math
from types import SimpleNamespace

import pygame
import pytest

import creatures
from entities.projectile import Projectile
from physics.inchworm import InchwormCommand
from tests.creature_parts import encounter, open_maze, world


def setting(**settings):
    c = creatures.build('inchworm', (400., 286.))
    wall = SimpleNamespace(start=(0., 300.), end=(1000., 300.), active=True)
    enc = encounter(c, world_=world(maze=open_maze([wall]), **settings))
    enc.ready()
    return c, enc


def test_reflex_controller_walks_using_alternating_surface_grips():
    c, enc = setting()
    seen = set()
    for _ in range(500):
        enc.step(1.)
        seen.add((c.worm_rear_grip, c.worm_front_grip))
    assert c.x > 435.
    assert (True, False) in seen and (False, True) in seen
    assert len(c.worm_observation['joint_angles']) == 5


def test_an_inchworm_appears_humped_away_from_its_wall_with_both_ends_down():
    c, enc = setting()                            # floor at y=300, below the worm
    links = c.worm_physics.links
    ends = (links[0].position.y, links[-1].position.y)
    assert ends[0] == pytest.approx(ends[1]) == pytest.approx(286.)                    # feet level, where they'd stand
    assert all(links[i].position.y < min(ends)-5. for i in (2, 3))                      # the middle bows up off the floor
    assert links[0].angle == pytest.approx(0., abs=1e-6) and links[-1].angle == pytest.approx(0., abs=1e-6)
    enc.close()


def test_external_neutral_command_completely_overrides_walking():
    c, enc = setting(inchworm_posture=(0.,)*5)    # straight, so nothing settles: a relaxing hump lands the head
    c.worm_command = InchwormCommand()
    enc.step(200.)
    assert c.get_pos() == pytest.approx((400., 286.))
    assert not c.worm_rear_grip and not c.worm_front_grip


def test_rears_toward_a_target_by_bending_and_does_not_snap_head():
    c, enc = setting()
    prey = creatures.build('static', (415., 250.))
    prey.allegiance = 'friend'
    enc.roster.add(prey)
    enc.ready()
    head = c.worm_front
    enc.step_creature(c, 1.)
    assert math.dist(head, c.worm_front) < 2.
    assert c.worm_rear_grip
    for _ in range(120):
        enc.step_creature(c, 1.)
        prey.x += prey.vx
        prey.y += prey.vy
    assert c.worm_front[1] < 275.
    assert math.dist(c.worm_front, prey.get_pos()) < 18.


def test_grabs_and_bites_only_after_sustained_mouth_contact():
    c, enc = setting()
    prey = creatures.build('static', (440., 286.))
    prey.allegiance = 'friend'
    enc.roster.add(prey)
    enc.ready()
    c.worm_command = InchwormCommand(rear_grip=True, front_grip=True, bite=True)
    for _ in range(59):
        enc.step_creature(c, 1.)
        prey.x += prey.vx
        prey.y += prey.vy
    assert prey.hit_points == 3
    for _ in range(100):
        enc.step_creature(c, 1.)
        prey.x += prey.vx
        prey.y += prey.vy
    assert prey.hit_points < 3
    c.emit('hit', enc)
    assert c.worm_prey is None
    assert not c.worm_front_grip and not c.worm_rear_grip


def test_shot_can_hit_tail_beyond_old_circle_and_miss_empty_bounding_area():
    c, enc = setting()
    shot = Projectile(c.worm_rear, 0.)
    assert math.dist(c.worm_rear, c.get_pos()) > c.radius
    assert enc.shoot(shot)
    assert c.hit_points == 3 and not shot.active
    miss = Projectile((c.x, c.y-15.), 0.)
    assert not enc.shoot(miss)
    assert miss.active
    assert c.projectile_contact((c.worm_rear[0], c.y-30), (0., 60.), 1.) is not None


def test_shove_preserves_detached_momentum_and_death_portraits_do_not_copy_solver():
    c, enc = setting()
    c.apply_momentum(4., -3.)
    enc.step(1.)
    assert c.vx > 3.5 and c.vy < -2.5
    portrait = copy.deepcopy(c)
    assert portrait.worm_physics is None and portrait.worm_prey is None
    screen = pygame.Surface((800, 600))
    c.body.draw(screen, c)
    portrait.body.draw(screen, portrait)
    enc.kill(c)
    c.update_death(1.)
    c.body.draw_death(screen, c)
    enc.close()
    enc.close()
    assert c.worm_physics is None


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_rejects_invalid_intervals(value):
    from creatures.traits.inchworm import Inchworms
    with pytest.raises(ValueError):
        Inchworms(strideFrames=value)


def test_shared_weapon_sweep_hits_the_articulated_tail():
    from weapons import CATALOG
    from weapons.projectile import make_projectile
    from weapons.simulation import advance
    c, enc = setting()
    p = make_projectile((c.worm_rear[0], c.y-20.), 90., 'player', CATALOG['basic'])
    advance(p, 5., enc.maze, [c], enc.apply_hit, lambda blast: None)
    assert c.hit_points < 4 and not p.active


def test_inflation_scales_the_articulated_hit_shape_and_drawing_consistently():
    c, enc = setting()
    before = c.hit_radius
    c.inflation.remaining, c.inflation.multiplier = 60., 2.
    assert c.hit_radius == pytest.approx(before*2)
    end = c.body.collision_segments(c)[0][0]
    assert math.dist(end, c.get_pos()) == pytest.approx(math.dist(c.worm_rear, c.get_pos())*2)
    radius = c.radius
    c.draw(pygame.Surface((800, 600)))
    assert c.radius == radius


def test_blast_hits_the_selected_worm_even_when_its_centre_is_inside_the_arch():
    from entities.explosion import Blast
    from game_handlers.collision_handler import CollisionHandler
    from unittest.mock import Mock
    from creatures.inchworm_control import ARCH
    c, enc = setting()
    c.worm_command = InchwormCommand(ARCH, False, True)
    enc.step(80.)
    handler = CollisionHandler(Mock(), Mock(), Mock())
    handler.handle_blast(Blast(c.get_pos(), 60., damage=1, push=0.), None, None, [c], enc.shoot)
    assert c.hit_points == 3


def test_shield_and_intervening_wall_prevent_grabbing_and_feeding():
    from entities.ship import Ship
    c, enc = setting()
    ship = Ship((440., 286.))
    enc.world.ship = ship
    c.worm_command = InchwormCommand(rear_grip=True, front_grip=True, bite=True)
    ship.activate_shield()
    enc.step(100.)
    assert c.worm_prey is None
    enc.scoring.record_enemy_collision.assert_not_called()
    ship.deactivate_shield()
    enc.maze.walls.append(SimpleNamespace(start=(435., 200.), end=(435., 300.), active=True))
    enc.step(100.)
    assert c.worm_prey is None
    enc.scoring.record_enemy_collision.assert_not_called()


def test_an_inchworm_hunts_and_eats_other_enemies_but_never_another_inchworm():
    from maze.wall_segment import WallSegment
    c = creatures.build('inchworm', (400., 286.))
    enc = encounter(c, world_=world(maze=open_maze([WallSegment((0., 300.), (1000., 300.), 1)])))
    enc.ready()
    victim = creatures.build('static', (470., 286.))        # an enemy-allegiance creature, on its own side
    sibling = creatures.build('inchworm', (330., 286.))
    enc.roster.add(victim)
    enc.roster.add(sibling)
    enc.ready()
    assert victim.allegiance == c.allegiance
    for _ in range(3000):
        enc.step(1.)
        if not victim.active:
            break
    assert not victim.active                      # eaten
    assert c.active and sibling.active and sibling.hit_points == sibling.kind.tuning.get('hit_points', sibling.hit_points)
    assert sibling.worm_prey is None


def test_an_inchworm_whose_physics_blows_up_does_not_take_the_game_down(monkeypatch):
    from physics.inchworm import InchwormPhysics
    c, enc = setting()
    def explode(self, *args, **kwargs):
        raise RuntimeError('inchworm physics exceeded its stable substep budget')
    monkeypatch.setattr(InchwormPhysics, 'step', explode)
    for _ in range(10):
        enc.step(1.)                              # no exception escapes
    assert c.worm_resets >= 1
    assert not c.active                           # it keeps failing, so it dies instead of looping forever
    for _ in range(int(c.body.DEATH_DURATION)):
        c.update_death(1.)                        # and its death plays out without the physics


def test_a_dying_inchworm_rolls_up_into_a_spiral():
    c, enc = setting()
    for _ in range(60):
        enc.step(1.)
    straight = sum(abs(b.angle-a.angle) for a, b in zip(c.worm_physics.links, c.worm_physics.links[1:]))
    enc.kill(c)
    for _ in range(int(c.body.DEATH_DURATION)):
        c.update_death(1.)
    bends = [b.angle-a.angle for a, b in zip(c.worm_physics.links, c.worm_physics.links[1:])]
    assert all(v > 0 for v in bends) or all(v < 0 for v in bends)       # every joint curls the same way
    assert abs(sum(bends)) > math.radians(300) > straight               # most of a full turn, from a body that was nearly straight
    assert abs(bends[-1]) > abs(bends[0])                               # tightening toward the head
    enc.close()
