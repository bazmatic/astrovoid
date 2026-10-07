"""Unit tests for the rough, reef-like wall drawing."""

import math
import pygame
import pytest
import config
from maze.wall_segment import WallSegment
from rendering.wall_renderer import WallRenderer

SIZE = (400, 300)


def wall(start, end, hit_points=None):
    return WallSegment(start, end, config.WALL_HIT_POINTS if hit_points is None else hit_points)


def render(walls, renderer=None):
    """Draw walls onto a transparent surface and return it."""
    screen = pygame.Surface(SIZE, pygame.SRCALPHA)
    (renderer or WallRenderer()).draw(screen, walls, animate=False)
    return screen


def drawn_pixels(screen):
    mask = pygame.mask.from_surface(screen, 1)
    width, height = screen.get_size()
    return {(x, y) for x in range(width) for y in range(height) if mask.get_at((x, y))}


def distance_to_segment(point, start, end):
    px, py = point
    (ax, ay), (bx, by) = start, end
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


class TestHonestShape:
    """The drawing wanders, but never far from the line things collide with."""

    @pytest.mark.parametrize("start,end", [
        ((60, 150), (340, 150)), ((200, 30), (200, 270)), ((70, 60), (310, 240)),
    ])
    def test_stays_close_to_the_true_line(self, start, end):
        pixels = drawn_pixels(render([wall(start, end)]))
        assert pixels
        furthest = max(distance_to_segment(p, start, end) for p in pixels)
        assert furthest <= WallRenderer.MAX_REACH

    @pytest.mark.parametrize("start,end", [
        ((60, 150), (340, 150)), ((200, 30), (200, 270)), ((70, 60), (310, 240)),
    ])
    def test_covers_the_whole_true_line(self, start, end):
        """No gaps: every point on the collision line is painted."""
        pixels = drawn_pixels(render([wall(start, end)]))
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        for step in range(int(length) + 1):
            t = step / length
            point = (int(start[0] + (end[0] - start[0]) * t), int(start[1] + (end[1] - start[1]) * t))
            assert point in pixels

    def test_is_irregular(self):
        """Thickness varies along the wall instead of being a ruled line."""
        screen = render([wall((60, 150), (340, 150))])
        mask = pygame.mask.from_surface(screen, 1)
        thickness = {sum(mask.get_at((x, y)) for y in range(130, 171)) for x in range(80, 320)}
        assert len(thickness) >= 3

    def test_uses_more_than_one_color(self):
        screen = render([wall((60, 150), (340, 150))])
        colors = {tuple(screen.get_at(p))[:3] for p in drawn_pixels(screen)}
        assert len(colors) >= 6


class TestStability:
    """Walls look the same every frame and from either direction."""

    def test_same_wall_always_looks_the_same(self):
        first = render([wall((60, 150), (340, 150))])
        second = render([wall((60, 150), (340, 150))])
        assert pygame.image.tostring(first, "RGBA") == pygame.image.tostring(second, "RGBA")

    def test_direction_does_not_matter(self):
        """Neighbouring cells share an edge drawn in opposite directions."""
        forward = render([wall((60, 150), (340, 150))])
        backward = render([wall((340, 150), (60, 150))])
        assert pygame.image.tostring(forward, "RGBA") == pygame.image.tostring(backward, "RGBA")

    def test_different_walls_look_different(self):
        upper = render([wall((60, 100), (340, 100))])
        lower = render([wall((60, 200), (340, 200))])
        shifted = {(x, y + 100) for x, y in drawn_pixels(upper)}
        assert shifted != drawn_pixels(lower)

    def test_unchanged_walls_are_not_repainted(self):
        renderer = WallRenderer()
        walls = [wall((60, 150), (340, 150))]
        render(walls, renderer)
        cached = renderer._surface
        render(walls, renderer)
        assert renderer._surface is cached
        assert renderer.repaint_count == 1


class TestDamage:
    """Walls crack before they break, and vanish when they do."""

    def test_damaged_wall_looks_cracked(self):
        intact = render([wall((60, 150), (340, 150))])
        damaged = render([wall((60, 150), (340, 150), hit_points=1)])
        assert pygame.image.tostring(intact, "RGBA") != pygame.image.tostring(damaged, "RGBA")

    def test_damage_repaints(self):
        renderer = WallRenderer()
        walls = [wall((60, 150), (340, 150)), wall((60, 250), (340, 250))]
        before = pygame.image.tostring(render(walls, renderer), "RGBA")
        walls[0].damage()
        after = pygame.image.tostring(render(walls, renderer), "RGBA")
        assert before != after

    def test_destroyed_wall_disappears(self):
        renderer = WallRenderer()
        doomed = wall((60, 100), (340, 100), hit_points=1)
        keeper = wall((60, 200), (340, 200))
        walls = [doomed, keeper]
        render(walls, renderer)
        doomed.damage()
        walls = [w for w in walls if w.active]
        pixels = drawn_pixels(render(walls, renderer))
        assert pixels
        assert all(y > 150 for _, y in pixels)

    def test_patched_repaint_matches_a_fresh_one(self):
        """Repainting just the changed area must leave no seams or leftovers."""
        def grid():
            walls = []
            for i in range(5):
                walls.append(wall((40, 40 + i * 50), (360, 40 + i * 50)))
                walls.append(wall((40 + i * 80, 40), (40 + i * 80, 240)))
            return walls

        renderer = WallRenderer()
        walls = grid()
        render(walls, renderer)
        walls[2].damage()
        walls[5].damage()
        walls[5].damage()
        walls[7].damage()
        patched = render([w for w in walls if w.active], renderer)
        assert renderer.repaint_count == 2

        fresh_walls = grid()
        fresh_walls[2].damage()
        fresh_walls[7].damage()
        del fresh_walls[5]
        fresh = render(fresh_walls)
        assert pygame.image.tostring(patched, "RGBA") == pygame.image.tostring(fresh, "RGBA")

    def test_damage_at_the_far_edge_repaints_only_its_patch(self):
        """Hitting the bottom or right boundary must not repaint the whole maze."""
        renderer = WallRenderer()
        walls = [wall((40, 40), (360, 40)), wall((40, 240), (360, 240)),
                 wall((40, 40), (40, 240)), wall((360, 40), (360, 240))]
        render(walls, renderer)
        cache = renderer._surface
        walls[1].damage()
        walls[3].damage()
        patched = render(walls, renderer)
        assert renderer._surface is cache
        assert pygame.image.tostring(patched, "RGBA") == pygame.image.tostring(render(walls), "RGBA")

    def test_inactive_walls_are_not_drawn(self):
        dead = wall((60, 150), (340, 150))
        dead.active = False
        assert not drawn_pixels(render([dead]))

    def test_no_walls_draws_nothing(self):
        assert not drawn_pixels(render([]))


class TestWeed:
    """Weed sways, but only when asked to animate."""

    def many_walls(self):
        return [wall((20, 20 + i * 13), (380, 20 + i * 13)) for i in range(20)]

    def test_some_walls_grow_weed(self):
        renderer = WallRenderer()
        render(self.many_walls(), renderer)
        assert 0 < len(renderer.weeds) < 20 * 4

    def test_weed_sways_over_time(self):
        renderer = WallRenderer()
        walls = self.many_walls()
        first = pygame.Surface(SIZE, pygame.SRCALPHA)
        renderer.draw(first, walls, time_seconds=0.0)
        later = pygame.Surface(SIZE, pygame.SRCALPHA)
        renderer.draw(later, walls, time_seconds=0.8)
        assert pygame.image.tostring(first, "RGBA") != pygame.image.tostring(later, "RGBA")

    def test_weed_goes_with_its_wall(self):
        renderer = WallRenderer()
        walls = self.many_walls()
        render(walls, renderer)
        assert renderer.weeds
        render([], renderer)
        assert renderer.weeds == []
