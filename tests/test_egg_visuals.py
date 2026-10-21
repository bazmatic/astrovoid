"""Unit tests for the egg sac's rendering, embryos and endings."""

import math
import pygame
import pytest
import creatures
import enemy_kinds
from entities.command_recorder import CommandRecorder
from tests.creature_parts import encounter, world

POS = (400.0, 300.0)
GROWS = dict(enemy_kinds.kind('egg').traits)['grows']
HATCHES = dict(enemy_kinds.kind('egg').traits)['hatches']


def laid_egg():
    """An egg as on its first frame: its growth rate and hatch count rolled."""
    egg = creatures.build('egg', POS, 1, CommandRecorder())
    for trait in egg.traits:
        trait.on_spawn(egg, None)
    egg.has_spawned = True
    return egg


def make_egg(growth=0.0, babies=None):
    """An egg at a given growth progress (0.0 just laid, 1.0 about to hatch), not growing any more."""
    egg = laid_egg()
    egg.radius = egg.start_radius + (GROWS['to'] - egg.start_radius) * growth
    egg.growth = growth
    egg.growth_rate = 0.0
    if babies is not None:
        egg.hatch_count = babies
    return egg


def hatch(egg):
    """Run the egg's frame at full size: it hatches onto an Encounter's roster, whose newcomers are returned."""
    egg.radius = GROWS['to']
    enc = encounter(egg, world_=world(command_recorder=CommandRecorder()))
    enc.step(1.0)
    return [e for e in enc.roster.all() if e is not egg]


def blank_screen():
    # Transparent surface so get_bounding_rect() reports only drawn pixels
    return pygame.Surface((800, 600), pygame.SRCALPHA)


def solid_bounds(screen):
    rects = pygame.mask.from_surface(screen, 200).get_bounding_rects()
    return rects[0].unionall(rects) if rects else pygame.Rect(0, 0, 0, 0)


class TestHonestCount:
    """The sac shows exactly the babies that will hatch."""

    def test_count_is_rolled_when_laid(self):
        counts = {laid_egg().body.baby_count for _ in range(200)}
        assert counts == set(range(HATCHES['countMin'], HATCHES['countMax'] + 1))

    @pytest.mark.parametrize("babies", [1, 2, 3])
    def test_hatches_the_babies_it_showed(self, babies):
        egg = make_egg(1.0, babies)
        assert len(egg.body.embryo_positions()) == babies
        assert len(hatch(egg)) == babies

    @pytest.mark.parametrize("babies", [1, 2, 3])
    def test_embryos_stay_inside_the_sac(self, babies):
        egg = make_egg(1.0, babies)
        for x, y in egg.body.embryo_positions():
            assert math.hypot(x, y) < 0.6


class TestDevelopment:
    """Embryos develop as the egg grows, so you can read how close it is."""

    def test_growth_progress(self):
        assert make_egg(0.0).body.growth_progress == pytest.approx(0.0)
        assert make_egg(0.5).body.growth_progress == pytest.approx(0.5)
        assert make_egg(1.0).body.growth_progress == pytest.approx(1.0)

    def test_stages_arrive_in_order(self):
        newly_laid, eyed, limbed = make_egg(0.1), make_egg(0.45), make_egg(0.8)
        assert newly_laid.body.eye_development == 0.0 and newly_laid.body.tentacle_development == 0.0
        assert eyed.body.eye_development > 0.0 and eyed.body.tentacle_development == 0.0
        assert limbed.body.eye_development == 1.0 and limbed.body.tentacle_development > 0.0

    def test_urgency_only_near_hatching(self):
        assert make_egg(0.5).body.urgency == 0.0
        assert 0.0 < make_egg(0.85).body.urgency < 1.0
        assert make_egg(1.0).body.urgency == pytest.approx(1.0)

    def test_pulses_faster_when_urgent(self):
        calm, urgent = make_egg(0.2), make_egg(0.99)
        calm.body.wobble_phase = urgent.body.wobble_phase = 0.0
        for _ in range(30):
            calm.body.update(calm, 1.0)
            urgent.body.update(urgent, 1.0)
        assert urgent.body.wobble_phase > calm.body.wobble_phase * 1.5


class TestHits:
    """The sac jiggles when shot."""

    def test_jiggles_on_hit(self):
        egg = make_egg(0.5)
        assert egg.body.jiggle == 0.0
        egg.body.on_event(egg, 'hit')
        assert egg.body.jiggle == 1.0

    def test_jiggle_settles(self):
        egg = make_egg(0.5)
        egg.body.on_event(egg, 'hit')
        for _ in range(90):
            egg.body.update(egg, 1.0)
        assert egg.body.jiggle < 0.01

    def test_tears_follow_damage(self):
        egg = make_egg(1.0)
        egg.max_hit_points = egg.hit_points = 4
        assert egg.body.tear_count == 0
        egg.hit_points = 2
        some = egg.body.tear_count
        egg.hit_points = 1
        assert 0 < some < egg.body.tear_count


class TestDrawing:
    """Smoke tests for drawing."""

    @pytest.mark.parametrize("growth", [0.0, 0.3, 0.7, 1.0])
    @pytest.mark.parametrize("babies", [1, 3])
    def test_draws_at_every_stage(self, growth, babies):
        egg = make_egg(growth, babies)
        screen = blank_screen()
        egg.draw(screen)
        egg.body.on_event(egg, 'hit')
        egg.body.update(egg, 1.0)
        egg.draw(screen)
        assert screen.get_bounding_rect().width > 0

    @pytest.mark.parametrize("growth", [0.0, 1.0])
    def test_sac_matches_its_collision_size(self, growth):
        egg = make_egg(growth)
        screen = blank_screen()
        egg.draw(screen)
        bounds = solid_bounds(screen)
        assert egg.radius * 1.6 < bounds.width < egg.radius * 2.4
        assert egg.radius * 1.6 < bounds.height < egg.radius * 2.4

    def test_sac_is_see_through(self):
        egg = make_egg(1.0, babies=1)
        screen = blank_screen()
        egg.draw(screen)
        # Between the centre embryo and the rim there is only jelly
        alpha = screen.get_at((int(egg.x), int(egg.y + egg.radius * 0.72))).a
        assert 0 < alpha < 255

    def test_inactive_draws_nothing(self):
        egg = make_egg(0.5)
        egg.active = False
        screen = blank_screen()
        egg.draw(screen)
        assert screen.get_bounding_rect().width == 0


class TestEndings:
    """Hatching and being shot each get their own animation."""

    def run_ending(self, egg):
        shown = []
        for _ in range(int(egg.DEATH_DURATION)):
            screen = blank_screen()
            egg.draw_death(screen)
            shown.append(screen.get_bounding_rect().width > 0)
            egg.update_death(1.0)
        screen = blank_screen()
        egg.draw_death(screen)
        return shown, screen.get_bounding_rect().width

    def test_hatching_splits_open(self):
        egg = make_egg(1.0)
        hatch(egg)
        assert not egg.active
        assert egg.is_dying
        assert egg.body.ending == "hatched"
        shown, leftover = self.run_ending(egg)
        assert shown[0] and shown[len(shown) // 2]
        assert leftover == 0
        assert not egg.is_dying

    def test_shot_egg_bursts_into_blobs(self):
        egg = make_egg(0.6)
        egg.die()
        assert egg.is_dying
        assert egg.body.ending == "burst"
        egg.update_death(1.0)
        before = [math.hypot(b.x - egg.x, b.y - egg.y) for b in egg.body.blobs]
        egg.update_death(1.0)
        after = [math.hypot(b.x - egg.x, b.y - egg.y) for b in egg.body.blobs]
        assert len(before) >= 5
        assert all(b > a for a, b in zip(before, after))

    def test_burst_fades_out(self):
        egg = make_egg(0.6)
        egg.die()
        shown, leftover = self.run_ending(egg)
        assert shown[0] and shown[len(shown) // 2]
        assert leftover == 0

    def test_shot_egg_hatches_nothing(self):
        egg = make_egg(1.0, babies=3)
        egg.die()
        enc = encounter(egg, world_=world(command_recorder=CommandRecorder()))
        for _ in range(int(egg.DEATH_DURATION) + 5):
            egg.update_death(1.0)
            enc.step(1.0)
        assert enc.roster.all() == [egg]
