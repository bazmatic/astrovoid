"""Unit tests for the Crab's crab Body: rendering and animation."""

import math
import pygame
import pytest
import creatures
from tests.creature_parts import encounter, target, world
from utils import get_angle_to_point

POS = (400.0, 300.0)


def make_patrol(angle=0.0):
    """A crab travelling along a known axis, its gun loaded as on its first frame."""
    enemy = creatures.build("patrol", POS)
    for trait in enemy.traits:
        trait.on_spawn(enemy, None)
    enemy.has_spawned = True
    enemy.angle = angle
    enemy.body.reset(enemy)
    return enemy


def angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def solid_pixels(screen):
    return pygame.mask.from_surface(screen, 254).count()


class TestRig:
    """The Crab is drawn as a crab."""

    def test_patrol_has_crab(self):
        assert make_patrol().body is not None


class TestFacing:
    """A crab walks sideways: it faces across its direction of travel."""

    def test_faces_across_travel_axis(self):
        enemy = make_patrol(angle=30.0)
        assert angle_gap(enemy.body.facing, 30.0) == pytest.approx(90.0)

    def test_keeps_facing_when_patrol_reverses(self):
        enemy = make_patrol(angle=30.0)
        facing = enemy.body.facing
        enemy.angle = 210.0
        for _ in range(10):
            enemy.body.update(enemy, 1.0, None)
        assert angle_gap(enemy.body.facing, facing) == pytest.approx(0.0, abs=1e-6)

    def test_turns_to_stay_sideways_when_axis_changes(self):
        enemy = make_patrol(angle=0.0)
        enemy.angle = 60.0
        for _ in range(120):
            enemy.body.update(enemy, 1.0, None)
        assert angle_gap(enemy.body.facing, 60.0) == pytest.approx(90.0, abs=0.5)


class TestGait:
    """Legs step with real movement."""

    def test_legs_still_when_not_moving(self):
        enemy = make_patrol()
        phase = enemy.body.walk_phase
        for _ in range(10):
            enemy.body.update(enemy, 1.0, None)
        assert enemy.body.walk_phase == phase

    def test_legs_step_when_moving(self):
        enemy = make_patrol()
        phase = enemy.body.walk_phase
        enemy.x += 3.0
        enemy.body.update(enemy, 1.0, None)
        assert enemy.body.walk_phase != phase

    def test_gait_reverses_with_direction(self):
        enemy = make_patrol()
        phase = enemy.body.walk_phase
        enemy.x += 3.0
        enemy.body.update(enemy, 1.0, None)
        forward = enemy.body.walk_phase - phase
        enemy.x -= 3.0
        enemy.body.update(enemy, 1.0, None)
        assert enemy.body.walk_phase == pytest.approx(phase)
        assert forward != 0.0


class TestClaw:
    """The cannon claw tracks the player and telegraphs shots."""

    def test_claw_rests_facing_forward(self):
        enemy = make_patrol()
        for _ in range(60):
            enemy.body.update(enemy, 1.0, None)
        assert angle_gap(enemy.body.claw_angle, enemy.body.facing) < 1.0

    @pytest.mark.parametrize("player", [(500.0, 300.0), (400.0, 100.0), (250.0, 420.0)])
    def test_claw_swivels_to_player(self, player):
        enemy = make_patrol()
        for _ in range(90):
            enemy.body.update(enemy, 1.0, player)
        assert angle_gap(enemy.body.claw_angle, get_angle_to_point(POS, player)) < 1.0

    def test_claw_turns_gradually(self):
        enemy = make_patrol()
        start = enemy.body.claw_angle
        behind = (POS[0] - math.cos(math.radians(start)) * 100, POS[1] - math.sin(math.radians(start)) * 100)
        enemy.body.update(enemy, 1.0, behind)
        assert 0 < angle_gap(enemy.body.claw_angle, start) < 45

    def test_charge_builds_as_shot_nears(self):
        enemy = make_patrol()
        enemy.gun_charge = 0.95
        near = (POS[0] + enemy.gun_range * 0.5, POS[1])
        for _ in range(60):
            enemy.body.update(enemy, 1.0, near)
        assert enemy.body.charge > 0.9

    def test_no_charge_just_after_firing(self):
        enemy = make_patrol()
        enemy.gun_charge = 0.0
        near = (POS[0] + enemy.gun_range * 0.5, POS[1])
        for _ in range(60):
            enemy.body.update(enemy, 1.0, near)
        assert enemy.body.charge < 0.05

    def test_no_charge_out_of_range(self):
        enemy = make_patrol()
        enemy.gun_charge = 1.0
        far = (POS[0] + enemy.gun_range * 2, POS[1])
        for _ in range(60):
            enemy.body.update(enemy, 1.0, far)
        assert enemy.body.charge < 0.05

    def test_firing_snaps_the_claw(self):
        enemy = make_patrol()
        near = (POS[0] + enemy.gun_range * 0.5, POS[1])
        enemy.emit("fired", None)
        assert enemy.body.fire_flash == 1.0
        for _ in range(60):
            enemy.body.update(enemy, 1.0, near)
        assert enemy.body.fire_flash == 0.0

    def test_holding_fire_does_not_snap(self):
        enemy = make_patrol()
        enc = encounter(enemy, world_=world(ship=target((450.0, 300.0))))
        enemy.gun_cooldown = 50
        enc.step(1.0)
        assert enc.world.projectiles == []
        assert enemy.body.fire_flash == 0.0


class TestDrawing:
    """Smoke tests for drawing."""

    def test_draws_wider_along_travel_axis(self):
        """Body and legs spread along the patrol line, like a crab walking sideways."""
        enemy = make_patrol(angle=0.0)
        # Pin the pose: legs mid-stride and the claw held out along the patrol line
        enemy.body.walk_phase = 0.0
        enemy.body.claw_angle = 0.0
        screen = blank_screen()
        enemy.draw(screen)
        bounds = pygame.mask.from_surface(screen, 254).get_bounding_rects()[0].unionall(
            pygame.mask.from_surface(screen, 254).get_bounding_rects())
        assert bounds.width > bounds.height
        assert bounds.width > enemy.radius * 2

    @pytest.mark.parametrize("angle", [0.0, 73.0, 180.0, 291.0])
    def test_draws_at_any_angle_and_state(self, angle):
        enemy = make_patrol(angle)
        screen = blank_screen()
        enemy.body.charge = 1.0
        enemy.draw(screen)
        enemy.body.fire_flash = 1.0
        enemy.draw(screen)
        assert solid_pixels(screen) > 0

    def test_inactive_draws_nothing(self):
        enemy = make_patrol()
        enemy.active = False
        screen = blank_screen()
        enemy.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestDeath:
    """The crab flips onto its back, curls up and fades."""

    def test_patrol_has_death_animation(self):
        enemy = make_patrol()
        enemy.die()
        assert not enemy.active
        assert enemy.is_dying

    def test_flips_onto_back(self):
        enemy = make_patrol()
        assert enemy.body.flip(0.0) == pytest.approx(1.0)
        assert enemy.body.flip(0.5) == pytest.approx(-1.0)

    def test_death_fades_out(self):
        enemy = make_patrol()
        enemy.die()
        shown = []
        for _ in range(int(enemy.DEATH_DURATION)):
            screen = blank_screen()
            enemy.draw_death(screen)
            shown.append(screen.get_bounding_rect().width > 0)
            enemy.update_death(1.0)
        assert shown[0] and shown[len(shown) // 2]
        assert not enemy.is_dying
        screen = blank_screen()
        enemy.draw_death(screen)
        assert screen.get_bounding_rect().width == 0

    def test_dead_crab_stops_moving(self):
        enemy = make_patrol()
        enemy.vx = 2.0
        enemy.die()
        for _ in range(int(enemy.DEATH_DURATION)):
            enemy.update_death(1.0)
        assert enemy.x < POS[0] + 20
        assert abs(enemy.vx) < 0.05
