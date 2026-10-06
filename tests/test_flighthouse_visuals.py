"""Unit tests for the flighthouse's lighthouse rendering and animation."""

import math
import pygame
import pytest
import config
from entities.flighthouse_enemy import FlighthouseEnemy


def make_flighthouse(angle=0.0, pos=(400.0, 300.0)):
    """Create a flighthouse facing a known direction."""
    flighthouse = FlighthouseEnemy(pos)
    flighthouse.angle = angle
    return flighthouse


def in_view(flighthouse, dist=100.0):
    """A player position straight ahead of the flighthouse."""
    angle_rad = math.radians(flighthouse.angle)
    return (flighthouse.x + math.cos(angle_rad) * dist, flighthouse.y + math.sin(angle_rad) * dist)


class TestAlertLevel:
    """Tests for the eased calm-to-alert transition."""

    def test_starts_calm(self):
        assert make_flighthouse().alert_level == 0.0

    def test_rises_while_player_visible(self):
        flighthouse = make_flighthouse()
        for _ in range(30):
            flighthouse.update(1.0, in_view(flighthouse))
        assert flighthouse.alert_level == pytest.approx(1.0)

    def test_falls_after_player_lost(self):
        flighthouse = make_flighthouse()
        for _ in range(30):
            flighthouse.update(1.0, in_view(flighthouse))
        for _ in range(120):
            flighthouse.update(1.0, None)
        assert flighthouse.alert_level == 0.0

    def test_alert_snaps_on_faster_than_it_fades(self):
        flighthouse = make_flighthouse()
        flighthouse.update(1.0, in_view(flighthouse))
        rise = flighthouse.alert_level
        flighthouse.alert_level = 1.0
        flighthouse.update(1.0, None)
        assert rise > 1.0 - flighthouse.alert_level


class TestLaunchFlash:
    """Tests for the flash shown when a flocker is released."""

    def test_no_flash_while_scanning(self):
        flighthouse = make_flighthouse()
        flighthouse.update(1.0, None)
        assert flighthouse.launch_flash == 0.0

    def test_flash_starts_on_spawn(self):
        flighthouse = make_flighthouse()
        spawned = flighthouse.update(1.0, in_view(flighthouse))
        assert len(spawned) == 1
        assert flighthouse.launch_flash == pytest.approx(1.0)

    def test_flash_decays(self):
        flighthouse = make_flighthouse()
        flighthouse.update(1.0, in_view(flighthouse))
        for _ in range(60):
            flighthouse.update(1.0, None)
        assert flighthouse.launch_flash == 0.0


class TestBeamSurface:
    """Tests for the pre-rendered searchlight cone (apex at left centre, pointing +x)."""

    @pytest.fixture
    def beam(self):
        return make_flighthouse()._get_beam_surface((120, 240, 200))

    def alpha_at(self, beam, dist, degrees):
        angle = math.radians(degrees)
        x = int(dist * math.cos(angle))
        y = int(beam.get_height() / 2 + dist * math.sin(angle))
        return beam.get_at((x, y)).a

    def test_is_cached(self):
        flighthouse = make_flighthouse()
        assert flighthouse._get_beam_surface((1, 2, 3)) is flighthouse._get_beam_surface((1, 2, 3))

    def test_length_follows_vision_range(self, beam):
        expected = config.FLIGHTHOUSE_ENEMY_VISION_RANGE * FlighthouseEnemy.BEAM_LENGTH_FRACTION
        assert beam.get_width() == pytest.approx(expected, abs=2)

    def test_lit_inside_vision_cone(self, beam):
        half = config.FLIGHTHOUSE_ENEMY_VISION_CONE_DEGREES * 0.5
        assert self.alpha_at(beam, 80, 0) > 0
        assert self.alpha_at(beam, 80, half - 3) > 0
        assert self.alpha_at(beam, 80, -(half - 3)) > 0

    def test_dark_outside_vision_cone(self, beam):
        half = config.FLIGHTHOUSE_ENEMY_VISION_CONE_DEGREES * 0.5
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
        flighthouse.update(1.0, in_view(flighthouse))
        flighthouse.draw(screen)
        flighthouse.alert_level = 0.5
        flighthouse.take_damage()
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
        flighthouse._anim_time = anim_time
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
        points = flighthouse._base_outline((400, 300), flighthouse.radius)
        offsets = {(x - 400, y - 300) for x, y in points}
        assert len(offsets) == FlighthouseEnemy.BASE_SIDES
        assert offsets == {(-x, y) for x, y in offsets} == {(x, -y) for x, y in offsets}
        assert offsets == {(y, x) for x, y in offsets}
