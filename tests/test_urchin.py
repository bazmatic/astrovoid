"""Unit tests for the static enemy's sea urchin rendering and animation."""

import math
import pygame
import pytest
from entities.enemy import Enemy
from entities.urchin import Urchin

POS = (400.0, 300.0)


def make_urchin():
    return Enemy(POS, "static")


def settle(enemy, player=None, frames=60):
    for _ in range(frames):
        enemy.urchin.update(enemy, 1.0, player)


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def solid_bounds(screen):
    rects = pygame.mask.from_surface(screen, 254).get_bounding_rects()
    return rects[0].unionall(rects) if rects else pygame.Rect(0, 0, 0, 0)


class TestRig:
    """Only static enemies are urchins."""

    def test_static_has_urchin(self):
        assert isinstance(make_urchin().urchin, Urchin)

    @pytest.mark.parametrize("enemy_type", ["patrol", "aggressive"])
    def test_other_types_have_no_urchin(self, enemy_type):
        assert Enemy(POS, enemy_type).urchin is None

    def test_every_type_has_exactly_one_body(self):
        for enemy_type in ("static", "patrol", "aggressive"):
            enemy = Enemy(POS, enemy_type)
            assert sum(body is not None for body in (enemy.urchin, enemy.crab, enemy.jellyfish)) == 1


class TestSpines:
    """Spines show health: they snap off as the urchin takes hits."""

    def test_all_spines_intact_at_full_health(self):
        enemy = make_urchin()
        settle(enemy, frames=1)
        assert enemy.urchin.intact_spines == Urchin.SPINE_COUNT

    def test_spines_snap_off_with_damage(self):
        enemy = make_urchin()
        counts = [enemy.urchin.intact_spines]
        while enemy.hit_points > 1:
            enemy.take_damage()
            settle(enemy, frames=1)
            counts.append(enemy.urchin.intact_spines)
        assert counts == sorted(counts, reverse=True)
        assert len(set(counts)) == len(counts)
        assert counts[-1] > 0

    def test_snapped_spines_fly_off_then_vanish(self):
        enemy = make_urchin()
        enemy.take_damage()
        settle(enemy, frames=1)
        lost = Urchin.SPINE_COUNT - enemy.urchin.intact_spines
        assert len(enemy.urchin.shards) == lost > 0
        settle(enemy, frames=int(Urchin.SHARD_FRAMES) + 2)
        assert enemy.urchin.shards == []

    def test_broken_spines_are_stubs(self):
        enemy = make_urchin()
        enemy.take_damage()
        settle(enemy, frames=1)
        urchin = enemy.urchin
        broken = [i for i in range(Urchin.SPINE_COUNT) if not urchin.spine_intact[i]]
        intact = [i for i in range(Urchin.SPINE_COUNT) if urchin.spine_intact[i]]
        assert max(urchin.spine_reach(i) for i in broken) < min(urchin.spine_reach(i) for i in intact)


class TestBristle:
    """Spines bristle toward a nearby player."""

    def test_calm_when_player_far(self):
        enemy = make_urchin()
        settle(enemy, (POS[0] + Urchin.ALARM_RANGE * 3, POS[1]))
        assert enemy.urchin.alarm < 0.05

    def test_alarmed_when_player_near(self):
        enemy = make_urchin()
        settle(enemy, (POS[0] + Urchin.ALARM_RANGE * 0.4, POS[1]))
        assert enemy.urchin.alarm > 0.95

    def test_spines_facing_player_reach_further(self):
        enemy = make_urchin()
        enemy.urchin.roll = 0.0
        calm = [enemy.urchin.spine_reach(i) for i in range(Urchin.SPINE_COUNT)]
        settle(enemy, (POS[0] + Urchin.ALARM_RANGE * 0.4, POS[1]))
        enemy.urchin.roll = 0.0
        alarmed = [enemy.urchin.spine_reach(i) for i in range(Urchin.SPINE_COUNT)]
        # Spine 0 points along +x at zero roll, straight at the player
        assert alarmed[0] > calm[0] * 1.15
        opposite = Urchin.SPINE_COUNT // 2
        assert alarmed[opposite] == pytest.approx(calm[opposite], rel=0.02)


class TestKnocks:
    """It rolls when knocked and squashes on impact."""

    def test_still_urchin_does_not_roll(self):
        enemy = make_urchin()
        roll = enemy.urchin.roll
        settle(enemy, frames=10)
        assert enemy.urchin.roll == roll

    def test_rolls_with_distance_and_direction(self):
        enemy = make_urchin()
        settle(enemy, frames=1)
        roll = enemy.urchin.roll
        enemy.x += 4.0
        settle(enemy, frames=1)
        right = enemy.urchin.roll - roll
        enemy.x -= 4.0
        settle(enemy, frames=1)
        assert right != 0.0
        assert enemy.urchin.roll == pytest.approx(roll)

    def test_squashes_when_velocity_jumps(self):
        enemy = make_urchin()
        settle(enemy, frames=2)
        assert enemy.urchin.squash == 0.0
        enemy.apply_momentum(3.0, 0.0)
        settle(enemy, frames=1)
        assert enemy.urchin.squash > 0.3
        settle(enemy, frames=60)
        assert enemy.urchin.squash < 0.01

    def test_friction_alone_does_not_squash(self):
        enemy = make_urchin()
        enemy.vx = 3.0
        settle(enemy, frames=1)
        enemy.urchin.squash = 0.0
        for _ in range(30):
            enemy.vx *= 0.95
            settle(enemy, frames=1)
        assert enemy.urchin.squash == 0.0


class TestDrawing:
    """Smoke tests for drawing."""

    def test_spines_reach_past_the_body(self):
        enemy = make_urchin()
        settle(enemy, frames=5)
        screen = blank_screen()
        enemy.draw(screen, None)
        bounds = solid_bounds(screen)
        assert bounds.width > enemy.radius * 2
        assert bounds.height > enemy.radius * 2

    def test_draws_in_every_state(self):
        enemy = make_urchin()
        screen = blank_screen()
        enemy.draw(screen, None)  # Before any update
        settle(enemy, (POS[0] + 30, POS[1]))
        enemy.take_damage()
        enemy.apply_momentum(2.0, 1.0)
        for _ in range(5):
            enemy.update(1.0, (POS[0] + 30, POS[1]), None)
            enemy.draw(screen, None)
        assert solid_bounds(screen).width > 0

    def test_inactive_draws_nothing(self):
        enemy = make_urchin()
        enemy.active = False
        screen = blank_screen()
        enemy.draw(screen, None)
        assert screen.get_bounding_rect().width == 0


class TestDeath:
    """The spines burst outward and the shell cracks apart."""

    def test_has_death_animation(self):
        enemy = make_urchin()
        enemy.die()
        assert enemy.is_dying
        assert enemy.DEATH_DURATION == Urchin.DEATH_DURATION

    def test_remaining_spines_burst_outward(self):
        enemy = make_urchin()
        settle(enemy, frames=1)
        remaining = enemy.urchin.intact_spines
        enemy.die()
        enemy.update_death(1.0)
        assert enemy.urchin.intact_spines == 0
        assert len(enemy.urchin.shards) == remaining
        before = [math.hypot(s.x - enemy.x, s.y - enemy.y) for s in enemy.urchin.shards]
        enemy.update_death(1.0)
        after = [math.hypot(s.x - enemy.x, s.y - enemy.y) for s in enemy.urchin.shards]
        assert all(b > a for a, b in zip(before, after))

    def test_shell_pieces_drift_apart(self):
        urchin = make_urchin().urchin
        assert urchin.shell_spread(0.0) == 0.0
        assert urchin.shell_spread(1.0) > urchin.shell_spread(0.5) > 0.0

    def test_fades_out(self):
        enemy = make_urchin()
        settle(enemy, frames=3)
        enemy.die()
        visible = []
        for _ in range(int(enemy.DEATH_DURATION)):
            screen = blank_screen()
            enemy.draw_death(screen)
            visible.append(screen.get_bounding_rect().width > 0)
            enemy.update_death(1.0)
        assert visible[0] and visible[len(visible) // 2]
        assert not enemy.is_dying
        screen = blank_screen()
        enemy.draw_death(screen)
        assert screen.get_bounding_rect().width == 0
