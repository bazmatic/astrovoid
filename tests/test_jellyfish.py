"""Unit tests for the Jelly's jellyfish Body: rendering and animation."""

import math
import pygame
import pytest
import creatures
from entities.jellyfish import Jellyfish
from entities.tentacle_chain import drag_chain

POS = (400.0, 300.0)


def make_jelly(angle=0.0):
    """A jelly heading in a known direction, set up as on its first frame."""
    enemy = creatures.build("aggressive", POS)
    for trait in enemy.traits:
        trait.on_spawn(enemy, None)
    enemy.has_spawned = True
    enemy.angle = angle
    enemy.body.reset(enemy)
    return enemy


def settle(enemy, frames=90):
    for _ in range(frames):
        enemy.body.update(enemy, 1.0, None)


def angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


class TestRig:
    """The Jelly is drawn as a jellyfish."""

    def test_aggressive_has_jellyfish(self):
        assert isinstance(make_jelly().body, Jellyfish)

    def test_jellyfish_is_pale_blue(self):
        red, green, blue = Jellyfish.COLOR
        assert blue > green > red > 100


class TestDragChain:
    """The trailing-chain helper shared with the squid."""

    def rest(self, angle):
        return lambda i, t: angle

    def test_segments_keep_their_length(self):
        chain = [(0.0, 0.0)] * 6
        for step in range(50):
            drag_chain(chain, (step * 3.0, step * 1.0), 4.0, self.rest(math.pi), 0.4, 0.2)
        for a, b in zip(chain, chain[1:]):
            assert math.hypot(b[0] - a[0], b[1] - a[1]) == pytest.approx(4.0)

    def test_root_follows_anchor(self):
        chain = [(0.0, 0.0)] * 4
        drag_chain(chain, (7.0, 9.0), 2.0, self.rest(0.0), 0.4, 0.2)
        assert chain[0] == (7.0, 9.0)

    def test_settles_on_rest_pose(self):
        chain = [(0.0, 0.0)] * 5
        for _ in range(200):
            drag_chain(chain, (10.0, 10.0), 3.0, self.rest(math.pi / 2), 0.4, 0.2)
        assert chain[-1][0] == pytest.approx(10.0, abs=0.01)
        assert chain[-1][1] == pytest.approx(22.0, abs=0.01)

    def test_snap_jumps_to_rest_pose(self):
        chain = [(500.0, 500.0)] * 5
        drag_chain(chain, (0.0, 0.0), 3.0, self.rest(0.0), 0.4, 0.2, snap=True)
        assert chain[-1] == pytest.approx((12.0, 0.0))


class TestSwimming:
    """Pulse, heading and tentacles."""

    def test_heading_turns_smoothly(self):
        enemy = make_jelly(angle=0.0)
        enemy.angle = 180.0
        enemy.body.update(enemy, 1.0, None)
        assert 0 < angle_gap(enemy.body.heading, 0.0) < 45
        settle(enemy)
        assert angle_gap(enemy.body.heading, 180.0) < 0.5

    def test_pulses_faster_when_chasing(self):
        idle = make_jelly()
        chasing = make_jelly()
        chasing.is_alert = True
        chasing.backing_off = False
        idle.body.pulse_phase = chasing.body.pulse_phase = 0.0
        settle(idle, 60)
        settle(chasing, 60)
        assert chasing.body.pulse_phase > idle.body.pulse_phase * 1.5

    def test_contraction_stays_in_range(self):
        enemy = make_jelly()
        values = []
        for _ in range(200):
            enemy.body.update(enemy, 1.0, None)
            values.append(enemy.body.contraction)
        assert min(values) >= 0.0 and max(values) <= 1.0
        assert max(values) - min(values) > 0.8

    @pytest.mark.parametrize("angle", [0.0, 120.0, 250.0])
    def test_tentacles_trail_behind(self, angle):
        enemy = make_jelly(angle)
        settle(enemy)
        forward = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        assert len(enemy.body.tentacles) == Jellyfish.TENTACLE_COUNT
        for chain in enemy.body.tentacles:
            tip = chain[-1]
            assert (tip[0] - enemy.x) * forward[0] + (tip[1] - enemy.y) * forward[1] < 0


class TestMood:
    """Chasing is bright and sparking; backing off a wall flutters."""

    def test_calm_without_a_target(self):
        enemy = make_jelly()
        settle(enemy)
        assert enemy.body.agitation < 0.05
        assert enemy.body.flutter < 0.05

    def test_agitated_when_chasing(self):
        enemy = make_jelly()
        enemy.is_alert = True
        enemy.backing_off = False
        settle(enemy)
        assert enemy.body.agitation > 0.95
        assert enemy.body.flutter < 0.05

    def test_flutters_when_backing_off(self):
        enemy = make_jelly()
        enemy.is_alert = True
        enemy.backing_off = True
        settle(enemy)
        assert enemy.body.flutter > 0.95
        assert enemy.body.agitation < 0.05


class TestDrawing:
    """Smoke tests for drawing."""

    @pytest.mark.parametrize("angle", [0.0, 73.0, 180.0, 291.0])
    def test_draws_in_every_mood(self, angle):
        enemy = make_jelly(angle)
        settle(enemy, 20)
        screen = blank_screen()
        enemy.draw(screen)
        assert screen.get_bounding_rect().width > enemy.radius * 2
        enemy.body.agitation = 1.0
        enemy.draw(screen)
        enemy.body.agitation = 0.0
        enemy.body.flutter = 1.0
        enemy.draw(screen)

    def test_draws_before_first_update(self):
        screen = blank_screen()
        creatures.build("aggressive", POS).draw(screen)
        assert screen.get_bounding_rect().width > 0

    def test_bell_is_translucent(self):
        enemy = make_jelly()
        settle(enemy, 20)
        screen = blank_screen()
        enemy.draw(screen)
        alpha = screen.get_at((int(enemy.x + enemy.radius * 0.75), int(enemy.y + enemy.radius * 0.45))).a
        assert 0 < alpha < 255

    def test_inactive_draws_nothing(self):
        enemy = make_jelly()
        enemy.active = False
        screen = blank_screen()
        enemy.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestDeath:
    """The bell collapses and the jellyfish dissolves."""

    def test_has_death_animation(self):
        enemy = make_jelly()
        enemy.die()
        assert not enemy.active
        assert enemy.is_dying
        assert enemy.DEATH_DURATION == Jellyfish.DEATH_DURATION

    def test_bell_collapses(self):
        jelly = make_jelly().body
        assert jelly.bell_length_scale(0.0) == pytest.approx(1.0)
        assert jelly.bell_length_scale(0.6) < 0.4

    def test_fades_out(self):
        enemy = make_jelly()
        settle(enemy, 20)
        enemy.die()
        alphas = []
        for _ in range(int(enemy.DEATH_DURATION)):
            screen = blank_screen()
            enemy.draw_death(screen)
            alphas.append(max(screen.get_at((x, y)).a for x in range(370, 431, 2) for y in range(270, 331, 2)))
            enemy.update_death(1.0)
        assert alphas[0] > 200
        assert 0 < alphas[-2] < alphas[len(alphas) // 2] <= alphas[0]
        assert not enemy.is_dying
        screen = blank_screen()
        enemy.draw_death(screen)
        assert screen.get_bounding_rect().width == 0
