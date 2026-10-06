"""Unit tests for the replay enemy's squid rendering and animation."""

import math
import pygame
import pytest
import config
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.baby import Baby
from entities.split_boss import SplitBoss
from entities.mother_boss import MotherBoss
from entities.command_recorder import CommandRecorder
from utils import angle_to_radians

SQUID_CLASSES = [ReplayEnemyShip, Baby, SplitBoss, MotherBoss]


def make_squid(cls=ReplayEnemyShip, pos=(400.0, 300.0), angle=0.0):
    """Create a squid facing a known direction."""
    squid = cls(pos, CommandRecorder())
    squid.angle = angle
    return squid


def settle(squid, frames=120):
    """Run the tentacle animation until it settles."""
    for _ in range(frames):
        squid._update_tentacles(1.0)


class TestTentacleChains:
    """Tests for the trailing tentacle simulation."""

    def test_one_chain_per_tentacle(self):
        squid = make_squid()
        settle(squid, 1)
        assert len(squid.tentacles) == squid.TENTACLE_COUNT

    def test_two_tentacles_are_longer(self):
        squid = make_squid()
        settle(squid, 1)
        lengths = sorted(len(chain) for chain in squid.tentacles)
        assert lengths[-1] > lengths[0]
        assert sum(1 for n in lengths if n == lengths[-1]) == 2

    @pytest.mark.parametrize("cls", SQUID_CLASSES)
    def test_segments_keep_their_length(self, cls):
        """Segments stay rigid while the squid moves and turns."""
        squid = make_squid(cls)
        for frame in range(90):
            squid.x += 2.0
            squid.y += 1.0
            squid.angle = (squid.angle + 4.0) % 360
            squid._update_tentacles(1.0)
        segment = squid._tentacle_segment_length()
        for chain in squid.tentacles:
            for a, b in zip(chain, chain[1:]):
                assert math.hypot(b[0] - a[0], b[1] - a[1]) == pytest.approx(segment, rel=1e-6)

    @pytest.mark.parametrize("angle", [0.0, 90.0, 200.0])
    def test_tentacles_trail_behind_the_heading(self, angle):
        squid = make_squid(angle=angle)
        settle(squid)
        angle_rad = angle_to_radians(angle)
        forward = (math.cos(angle_rad), math.sin(angle_rad))
        for chain in squid.tentacles:
            tip = chain[-1]
            along = (tip[0] - squid.x) * forward[0] + (tip[1] - squid.y) * forward[1]
            assert along < 0

    def test_tentacles_stream_behind_when_moving(self):
        """Moving forward pulls the arms into a tighter bundle than at rest."""
        resting = make_squid()
        settle(resting)
        moving = make_squid()
        for _ in range(120):
            moving.x += 3.0
            moving._update_tentacles(1.0)

        def spread(squid):
            return max(abs(chain[-1][1] - squid.y) for chain in squid.tentacles)

        assert spread(moving) < spread(resting)

    def test_chains_follow_a_teleport(self):
        squid = make_squid()
        settle(squid, 10)
        squid.x += 5000.0
        squid._update_tentacles(1.0)
        reach = squid.radius * 4
        for chain in squid.tentacles:
            assert math.hypot(chain[-1][0] - squid.x, chain[-1][1] - squid.y) < reach

    def test_chains_scale_with_radius(self):
        """Bosses change radius after construction; chains must follow."""
        regular = make_squid(ReplayEnemyShip)
        boss = make_squid(MotherBoss)
        ratio = boss.radius / regular.radius
        assert boss._tentacle_segment_length() == pytest.approx(
            regular._tentacle_segment_length() * ratio
        )


class TestJetAnimation:
    """Tests for the thrust-driven jet pulse."""

    def test_thrust_raises_jet(self):
        squid = make_squid()
        assert squid.jet == 0.0
        squid.apply_thrust()
        assert squid.jet > 0.0

    def test_jet_is_capped(self):
        squid = make_squid()
        for _ in range(100):
            squid.apply_thrust()
        assert squid.jet == pytest.approx(1.0)

    def test_jet_decays_when_idle(self):
        squid = make_squid()
        for _ in range(20):
            squid.apply_thrust()
        settle(squid, 200)
        assert squid.jet < 0.01

    def test_update_advances_animation(self):
        squid = make_squid()
        squid.update(1.0, (0.0, 0.0))
        assert squid.pulse_phase > 0.0
        assert len(squid.tentacles) == squid.TENTACLE_COUNT


class TestDrawing:
    """Smoke tests: every squid variant draws without error."""

    @pytest.fixture
    def screen(self):
        # Transparent surface so get_bounding_rect() reports only drawn pixels
        return pygame.Surface((800, 600), pygame.SRCALPHA)

    @pytest.mark.parametrize("cls", SQUID_CLASSES)
    def test_draws_pixels(self, screen, cls):
        squid = make_squid(cls, angle=37.0)
        squid.draw(screen)  # Before any update
        squid.apply_thrust()
        squid.update(1.0, (0.0, 0.0))
        squid.trigger_blink()
        for _ in range(8):
            squid.update(1.0, (0.0, 0.0))
            squid.draw(screen)
        bounds = screen.get_bounding_rect()
        assert squid.radius < bounds.width < 800
        assert squid.radius < bounds.height < 600

    def test_inactive_squid_draws_nothing(self, screen):
        squid = make_squid()
        squid.active = False
        squid.draw(screen)
        assert screen.get_bounding_rect().width == 0

    def test_damaged_boss_draws(self, screen):
        boss = make_squid(SplitBoss)
        boss.hit_points = 1
        boss.update(1.0, (0.0, 0.0))
        boss.draw(screen)
