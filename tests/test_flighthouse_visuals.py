"""Unit tests for the flighthouse's lighthouse rendering and animation."""

import math
import pygame
import pytest
import creatures
import enemy_kinds
from entities.flighthouse import FlighthouseBody
from tests.creature_parts import encounter, target, world

SCANS = dict(enemy_kinds.kind('flighthouse').traits)['scans']
_ENCOUNTERS = {}


def make_flighthouse(angle=0.0, pos=(400.0, 300.0)):
    """Create a flighthouse facing a known direction, set up on a level of its own."""
    flighthouse = creatures.build('flighthouse', pos)
    enc = encounter(flighthouse, world_=world())
    enc.ready()
    flighthouse.angle = angle
    _ENCOUNTERS[id(flighthouse)] = enc
    return flighthouse


def step(flighthouse, player_pos):
    """One frame with the player at a position (or nowhere); returns what it launched."""
    enc = _ENCOUNTERS[id(flighthouse)]
    enc.world.ship = target(player_pos) if player_pos is not None else None
    before = set(map(id, enc.roster.all()))
    enc.step(1.0)
    return [e for e in enc.roster.all() if id(e) not in before]


def in_view(flighthouse, dist=100.0):
    """A player position straight ahead of the flighthouse."""
    angle_rad = math.radians(flighthouse.angle)
    return (flighthouse.x + math.cos(angle_rad) * dist, flighthouse.y + math.sin(angle_rad) * dist)


class TestAlertLevel:
    """Tests for the eased calm-to-alert transition."""

    def test_starts_calm(self):
        assert make_flighthouse().body.alert_level == 0.0

    def test_rises_while_player_visible(self):
        flighthouse = make_flighthouse()
        for _ in range(30):
            step(flighthouse, in_view(flighthouse))
        assert flighthouse.body.alert_level == pytest.approx(1.0)

    def test_falls_after_player_lost(self):
        flighthouse = make_flighthouse()
        for _ in range(30):
            step(flighthouse, in_view(flighthouse))
        for _ in range(120):
            step(flighthouse, None)
        assert flighthouse.body.alert_level == 0.0

    def test_alert_snaps_on_faster_than_it_fades(self):
        flighthouse = make_flighthouse()
        step(flighthouse, in_view(flighthouse))
        rise = flighthouse.body.alert_level
        flighthouse.body.alert_level = 1.0
        step(flighthouse, None)
        assert rise > 1.0 - flighthouse.body.alert_level


class TestLaunchFlash:
    """Tests for the flash shown when a flocker is released."""

    def test_no_flash_while_scanning(self):
        flighthouse = make_flighthouse()
        step(flighthouse, None)
        assert flighthouse.body.launch_flash == 0.0

    def test_flash_starts_on_spawn(self):
        flighthouse = make_flighthouse()
        spawned = step(flighthouse, in_view(flighthouse))
        assert len(spawned) == 1
        assert flighthouse.body.launch_flash == pytest.approx(1.0)

    def test_flash_decays(self):
        flighthouse = make_flighthouse()
        step(flighthouse, in_view(flighthouse))
        for _ in range(60):
            step(flighthouse, None)
        assert flighthouse.body.launch_flash == 0.0


class TestBeamSurface:
    """Tests for the pre-rendered searchlight cone (apex at left centre, pointing +x)."""

    @pytest.fixture
    def beam(self):
        return make_flighthouse().body._get_beam_surface((120, 240, 200))

    def alpha_at(self, beam, dist, degrees):
        angle = math.radians(degrees)
        x = int(dist * math.cos(angle))
        y = int(beam.get_height() / 2 + dist * math.sin(angle))
        return beam.get_at((x, y)).a

    def test_is_cached(self):
        flighthouse = make_flighthouse()
        assert flighthouse.body._get_beam_surface((1, 2, 3)) is flighthouse.body._get_beam_surface((1, 2, 3))

    def test_length_follows_vision_range(self, beam):
        expected = SCANS['range'] * FlighthouseBody.BEAM_LENGTH_FRACTION
        assert beam.get_width() == pytest.approx(expected, abs=2)

    def test_lit_inside_vision_cone(self, beam):
        half = SCANS['coneDegrees'] * 0.5
        assert self.alpha_at(beam, 80, 0) > 0
        assert self.alpha_at(beam, 80, half - 3) > 0
        assert self.alpha_at(beam, 80, -(half - 3)) > 0

    def test_dark_outside_vision_cone(self, beam):
        half = SCANS['coneDegrees'] * 0.5
        assert self.alpha_at(beam, 80, half + 3) == 0
        assert self.alpha_at(beam, 80, -(half + 3)) == 0

    def test_fades_with_distance(self, beam):
        near = self.alpha_at(beam, 30, 0)
        far = self.alpha_at(beam, beam.get_width() - 10, 0)
        assert near > far


class TestDrawing:
    """Smoke tests for drawing."""

    @pytest.fixture
    def screen(self):
        # Transparent surface so get_bounding_rect() reports only drawn pixels
        return pygame.Surface((800, 600), pygame.SRCALPHA)

    @pytest.mark.parametrize("angle,axis,direction", [
        (0.0, "x", 1), (180.0, "x", -1), (90.0, "y", 1), (270.0, "y", -1),
    ])
    def test_beam_points_along_facing(self, screen, angle, axis, direction):
        flighthouse = make_flighthouse(angle)
        flighthouse.draw(screen)
        bounds = screen.get_bounding_rect()
        if axis == "x":
            ahead = bounds.right - flighthouse.x if direction > 0 else flighthouse.x - bounds.left
            behind = flighthouse.x - bounds.left if direction > 0 else bounds.right - flighthouse.x
        else:
            ahead = bounds.bottom - flighthouse.y if direction > 0 else flighthouse.y - bounds.top
            behind = flighthouse.y - bounds.top if direction > 0 else bounds.bottom - flighthouse.y
        assert ahead > flighthouse.radius * 4
        assert behind < flighthouse.radius * 4

    def test_draws_alert_launch_and_damage_states(self, screen):
        flighthouse = make_flighthouse(33.0)
        step(flighthouse, in_view(flighthouse))
        flighthouse.draw(screen)
        flighthouse.body.alert_level = 0.5
        flighthouse.hit_points -= 1
        flighthouse.draw(screen)
        assert screen.get_bounding_rect().width > 0

    def test_inactive_draws_nothing(self, screen):
        flighthouse = make_flighthouse()
        flighthouse.active = False
        flighthouse.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestBaseShape:
    """The base is a neat, steady octagon on the pixel grid."""

    def outline_reach(self, anim_time, pos=(400.4, 300.7)):
        """Distance from the centre to the outer wall, right/left/down, in pixels."""
        flighthouse = make_flighthouse(angle=270.0, pos=pos)  # Hood and beam point up, out of the way
        flighthouse.body._anim_time = anim_time
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        flighthouse.draw(screen)
        solid = pygame.mask.from_surface(screen, 254)
        cx, cy = int(flighthouse.x), int(flighthouse.y)
        reach = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1)):
            reach.append(max(r for r in range(1, 40) if solid.get_at((cx + dx * r, cy + dy * r))))
        return reach

    def test_walls_are_symmetric(self):
        right, left, down = self.outline_reach(0.0)
        assert right == left == down

    def test_walls_do_not_move(self):
        shapes = {tuple(self.outline_reach(step * 0.07)) for step in range(40)}
        assert len(shapes) == 1

    def test_outline_points_are_mirror_symmetric(self):
        flighthouse = make_flighthouse()
        points = flighthouse.body._base_outline((400, 300), flighthouse.radius)
        offsets = {(x - 400, y - 300) for x, y in points}
        assert len(offsets) == FlighthouseBody.BASE_SIDES
        assert offsets == {(-x, y) for x, y in offsets} == {(x, -y) for x, y in offsets}
        assert offsets == {(y, x) for x, y in offsets}
