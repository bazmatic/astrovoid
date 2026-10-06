"""Unit tests for the exit portal's whirlpool rendering and animation."""

import math
import pygame
import pytest
import config
from entities.exit import ExitPortal

POS = (400.0, 300.0)
RADIUS = 22.0
FAR = (POS[0] + config.EXIT_PORTAL_ATTRACTION_RADIUS * 3, POS[1])
NEAR = (POS[0] + config.EXIT_PORTAL_ATTRACTION_RADIUS * 0.5, POS[1])
SECOND = 60  # Frames


def make_portal():
    return ExitPortal(POS, RADIUS)


def run(portal, frames, player=FAR):
    for _ in range(frames):
        portal.update(1.0, player)


def lock(portal, frames=2 * SECOND):
    portal.set_activated(False)
    run(portal, frames)


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def rim_bounds(portal):
    """Bounding box of the whirlpool out to its rim, ignoring specks and faint ripples."""
    specks, portal.specks = portal.specks, []
    screen = blank_screen()
    portal.draw(screen)
    portal.specks = specks
    rects = pygame.mask.from_surface(screen, ExitPortal.RIM_ALPHA - 10).get_bounding_rects()
    return max(rects, key=lambda r: r.width * r.height)


class TestLocking:
    """The portal eases shut while eggs remain and eases open again."""

    def test_starts_open(self):
        portal = make_portal()
        assert portal.activation == 1.0
        assert portal.mouth_radius > 0.0

    def test_closes_gradually(self):
        portal = make_portal()
        portal.set_activated(False)
        run(portal, 5)
        assert 0.0 < portal.activation < 1.0
        run(portal, 2 * SECOND)
        assert portal.activation == 0.0

    def test_mouth_shuts_when_locked(self):
        portal = make_portal()
        lock(portal)
        assert portal.mouth_radius == 0.0

    def test_reopens_gradually_with_a_ripple(self):
        portal = make_portal()
        lock(portal)
        assert portal.unlock_ripple == 0.0
        portal.set_activated(True)
        run(portal, 1)
        assert portal.unlock_ripple > 0.9
        assert 0.0 < portal.activation < 1.0
        run(portal, 3 * SECOND)
        assert portal.activation == 1.0
        assert portal.unlock_ripple == 0.0

    def test_no_ripple_just_for_starting_open(self):
        portal = make_portal()
        portal.set_activated(True)
        run(portal, 5)
        assert portal.unlock_ripple == 0.0

    def test_spins_slower_when_locked(self):
        open_portal, locked = make_portal(), make_portal()
        lock(locked)
        open_start, locked_start = open_portal.spin, locked.spin
        run(open_portal, SECOND)
        run(locked, SECOND)
        assert locked.spin - locked_start < (open_portal.spin - open_start) * 0.4
        assert locked.spin > locked_start


class TestInflow:
    """Specks spiral into an open portal, showing its pull."""

    def test_specks_start_within_pull_range(self):
        portal = make_portal()
        assert len(portal.specks) == ExitPortal.SPECK_COUNT
        for speck in portal.specks:
            assert portal.speck_distance(speck) <= config.EXIT_PORTAL_ATTRACTION_RADIUS

    def test_specks_move_inward_and_speed_up(self):
        portal = make_portal()
        portal.specks = [[0.0, 1.0]]
        run(portal, 10)
        early = 1.0 - portal.specks[0][1]
        start = portal.specks[0][1]
        run(portal, 10)
        later = start - portal.specks[0][1]
        assert early > 0.0
        assert later > early

    def test_specks_circle_as_they_fall(self):
        portal = make_portal()
        portal.specks = [[0.0, 1.0]]
        run(portal, 10)
        assert portal.specks[0][0] != 0.0

    def test_specks_respawn_at_the_edge(self):
        portal = make_portal()
        portal.specks = [[0.0, 0.01]]
        run(portal, 3)
        assert portal.specks[0][1] > 0.8

    def test_specks_stop_when_locked(self):
        portal = make_portal()
        lock(portal)
        before = [list(speck) for speck in portal.specks]
        run(portal, 30)
        assert portal.specks == before


class TestSize:
    """What you see is the size you have to hit."""

    def test_size_is_steady(self):
        portal = make_portal()
        sizes = set()
        for _ in range(12):
            run(portal, 7)
            bounds = rim_bounds(portal)
            sizes.add((bounds.width, bounds.height))
        assert len(sizes) == 1

    def test_rim_matches_collision_radius(self):
        bounds = rim_bounds(make_portal())
        assert bounds.width == pytest.approx(RADIUS * 2, rel=0.12)
        assert bounds.height == pytest.approx(RADIUS * 2, rel=0.12)

    def test_mouth_widens_when_player_is_near(self):
        portal = make_portal()
        run(portal, SECOND, FAR)
        calm = portal.mouth_radius
        run(portal, SECOND, NEAR)
        assert portal.nearness == pytest.approx(1.0, abs=0.01)
        assert portal.mouth_radius > calm * 1.3

    def test_locked_portal_ignores_the_player(self):
        portal = make_portal()
        lock(portal)
        run(portal, SECOND, NEAR)
        assert portal.nearness < 0.01


class TestUnchangedRules:
    """Collision, pull and locking behave as before."""

    def test_open_portal_can_be_entered(self):
        assert make_portal().check_circle_collision(POS, 5.0)

    def test_locked_portal_cannot_be_entered(self):
        portal = make_portal()
        portal.set_activated(False)
        assert not portal.check_circle_collision(POS, 5.0)

    def test_pull_only_when_open_and_in_range(self):
        portal = make_portal()
        assert portal.get_attraction_force(NEAR) is not None
        assert portal.get_attraction_force(FAR) is None
        portal.set_activated(False)
        assert portal.get_attraction_force(NEAR) is None


class TestDrawing:
    """Smoke tests for drawing."""

    def test_draws_open_closing_locked_and_opening(self):
        portal = make_portal()
        screen = blank_screen()
        portal.draw(screen)
        portal.set_activated(False)
        for _ in range(SECOND):
            run(portal, 1, NEAR)
            portal.draw(screen)
        portal.set_activated(True)
        for _ in range(SECOND):
            run(portal, 1, NEAR)
            portal.draw(screen)
        assert screen.get_bounding_rect().width > RADIUS * 2

    def test_locked_is_dimmer_than_open(self):
        def brightness(portal):
            screen = blank_screen()
            portal.draw(screen)
            total = 0
            for x in range(int(POS[0] - RADIUS), int(POS[0] + RADIUS), 2):
                for y in range(int(POS[1] - RADIUS), int(POS[1] + RADIUS), 2):
                    r, g, b, a = screen.get_at((x, y))
                    total += (r + g + b) * a
            return total

        locked = make_portal()
        lock(locked)
        assert brightness(locked) < brightness(make_portal()) * 0.7

    def test_outer_water_is_clearer_than_the_core(self):
        """Whatever is behind the outer whirlpool shows through; the middle is dense."""
        portal = make_portal()
        portal.specks = []
        samples = {"edge": [], "core": []}
        for _ in range(8):
            run(portal, 5)
            screen = blank_screen()
            portal.draw(screen)
            for step in range(24):
                angle = 2 * math.pi * step / 24
                for name, share in (("edge", 0.8), ("core", 0.3)):
                    point = (int(POS[0] + math.cos(angle) * RADIUS * share), int(POS[1] + math.sin(angle) * RADIUS * share))
                    samples[name].append(screen.get_at(point).a)
        edge = sum(samples["edge"]) / len(samples["edge"])
        core = sum(samples["core"]) / len(samples["core"])
        assert edge < 150
        assert core > 220
        assert min(samples["edge"]) < 100

    def test_inactive_draws_nothing(self):
        portal = make_portal()
        portal.active = False
        screen = blank_screen()
        portal.draw(screen)
        assert screen.get_bounding_rect().width == 0
