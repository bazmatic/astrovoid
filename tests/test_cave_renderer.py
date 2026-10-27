"""Curved cave rock drawn: the rock fills its territory, wounds stay in it, steel stays square, weed and joints
are as sparse as on square walls."""
import math
import random

import cv2
import numpy as np
import pygame
import pytest

import config
from maze.config import MazeComplexity
from maze.generator import Maze
from rendering.wall_renderer import WallRenderer
from tests.test_strong_walls import STRONG, maze as strong_maze, render as render_maze

REACH = WallRenderer.MAX_REACH


@pytest.fixture(autouse=True)
def display():
    pygame.init()


def curved_maze(curved=True):
    random.seed(125)
    return Maze(1, complexity=MazeComplexity.COMPLEX, grid_size=18, seed=125, curved=curved)


def paint(m, renderer=None):
    """The walls alone, on a transparent surface: (surface, renderer)."""
    renderer = renderer or WallRenderer()
    screen = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
    renderer.draw(screen, m.walls, animate=False, blocks=m.block_fills, wounds=m.block_wounds,
                  unbreakable=m.unbreakable_blocks, strong=m.strong_blocks, territories=m.block_territories,
                  strong_cells=m.strong_cells)
    return screen, renderer


def alpha(screen):
    """Alpha as an array indexed [y, x]."""
    return pygame.surfarray.array_alpha(screen).T.copy()


def rgba(screen):
    return np.dstack([pygame.surfarray.array3d(screen).transpose(1, 0, 2), alpha(screen)])


def grid_area(m):
    left, top, _, _ = m.converter.cell_rect(0, 0)
    x, y, width, height = m.converter.cell_rect(m.grid_width - 1, m.grid_height - 1)
    return pygame.Rect(left, top, x + width - left, y + height - top)


def distance_to_walls(m):
    """Distance from every screen pixel to the nearest active segment, indexed [y, x]."""
    lines = np.full((config.SCREEN_HEIGHT, config.SCREEN_WIDTH), 255, np.uint8)
    for wall in m.walls:
        if wall.active:
            start = tuple(int(round(v)) for v in wall.start)
            end = tuple(int(round(v)) for v in wall.end)
            cv2.line(lines, start, end, 0, 1)
    return cv2.distanceTransform(lines, cv2.DIST_L2, 5)


def in_mask(territory, x, y):
    area, mask = territory
    return area.collidepoint(x, y) and mask.get_at((x - area.x, y - area.y))


def grown(territory, by):
    """A territory's mask grown by `by` pixels, as a boolean array over the screen [y, x]."""
    area, mask = territory
    out = np.zeros((config.SCREEN_HEIGHT, config.SCREEN_WIDTH), np.uint8)
    bits = pygame.surfarray.array_alpha(mask.to_surface(setcolor=(255, 255, 255, 255),
                                                        unsetcolor=(0, 0, 0, 0))).T
    out[area.y:area.y + area.height, area.x:area.x + area.width] = bits > 0
    size = 2 * int(math.ceil(by)) + 1
    return cv2.dilate(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))) > 0


def inner_block(m):
    """A destructible block away from the rim, with plenty of rock and open space beside it."""
    for cell in sorted(m.blocks):
        if m.converter.on_perimeter(m.grid, *cell):
            continue
        faces = [w for w in m.walls if w.cell == cell and w.destructible]
        territory = m.block_territories.get(m.converter.cell_rect(*cell))
        if len(faces) >= 6 and territory is not None and territory[1].count() > 2000:
            return cell, faces
    raise AssertionError('no inner block')


def middle(wall):
    return ((wall.start[0] + wall.end[0]) / 2, (wall.start[1] + wall.end[1]) / 2)


def test_rock_pixels_filled():
    m = curved_maze()
    screen, _ = paint(m)
    seen = alpha(screen)
    distance = distance_to_walls(m)
    area = grid_area(m)
    holes, ghosts = [], []
    for y in range(area.top, area.bottom, 3):
        for x in range(area.left, area.right, 3):
            if m.cave.is_rock((x + 0.5, y + 0.5)):
                if not seen[y, x]:
                    holes.append((x, y))
            elif distance[y, x] > REACH + 2 and seen[y, x]:
                ghosts.append((x, y))
    assert not holes, holes[:10]
    assert not ghosts, ghosts[:10]


def test_bites_stay_in_territory():
    m = curved_maze()
    cell, faces = inner_block(m)
    rect = m.converter.cell_rect(*cell)
    before, renderer = paint(m)
    before = rgba(before)
    for face in faces[::max(1, len(faces) // (config.WALL_HIT_POINTS - 1))][:config.WALL_HIT_POINTS - 1]:
        assert not m.damage_wall(face, middle(face))
    after, _ = paint(m, renderer)
    changed = np.any(rgba(after) != before, axis=2)
    assert changed.any()
    allowed = grown(m.block_territories[rect], REACH + 1)
    outside = np.argwhere(changed & ~allowed)
    assert not len(outside), outside[:10]
    # The repaint matches painting the damaged maze afresh
    fresh, _ = paint(m)
    assert np.array_equal(rgba(fresh)[allowed], rgba(after)[allowed])


def test_wound_opens_a_bite_in_the_rock():
    m = curved_maze()
    cell, faces = inner_block(m)
    face = faces[len(faces) // 2]
    before, renderer = paint(m)
    before = rgba(before)
    m.damage_wall(face, middle(face))
    after = rgba(paint(m, renderer)[0])
    territory = m.block_territories[m.converter.cell_rect(*cell)]
    x, y = (int(v) for v in middle(face))
    darkened = 0
    for py in range(y - 12, y + 13):
        for px in range(x - 12, x + 13):
            if in_mask(territory, px, py) and after[py, px, :3].sum() < before[py, px, :3].sum() - 30:
                darkened += 1
    assert darkened > 20


def test_destroyed_block_cleared():
    m = curved_maze()
    cell, faces = inner_block(m)
    old = m.block_territories[m.converter.cell_rect(*cell)]
    _, renderer = paint(m)
    for _ in range(config.WALL_HIT_POINTS):
        m.damage_wall(next(w for w in m.walls if w.cell == cell), None)
    assert cell not in m.blocks
    seen = alpha(paint(m, renderer)[0])
    distance = distance_to_walls(m)
    area, mask = old
    left = []
    for y in range(area.top, area.bottom, 2):
        for x in range(area.left, area.right, 2):
            if (mask.get_at((x - area.x, y - area.y)) and not m.cave.is_rock((x + 0.5, y + 0.5))
                    and distance[y, x] > REACH + 3 and seen[y, x]):
                left.append((x, y))
    assert not left, left[:10]


def test_territories_after_destroy_match_a_fresh_build():
    m = curved_maze()
    cell, _ = inner_block(m)
    for _ in range(config.WALL_HIT_POINTS):
        m.damage_wall(next(w for w in m.walls if w.cell == cell), None)
    fresh = {m.converter.cell_rect(*c): m.cave.territory(c) for c in m.blocks}
    fresh = {rect: value for rect, value in fresh.items() if value is not None}
    assert fresh.keys() == m.block_territories.keys()
    for rect, (area, mask) in fresh.items():
        kept_area, kept_mask = m.block_territories[rect]
        assert kept_area == area
        assert WallRenderer._same_mask(kept_mask, mask)


def test_steel_still_plates():
    m = strong_maze()
    assert m.curved
    screen = render_maze(m)
    left, top, width, height = m.converter.cell_rect(*STRONG)
    plate = pygame.Rect(left, top, width, height)
    steel = pygame.transform.average_color(screen, plate.inflate(-8, -8))[:3]
    assert sum((a - b) ** 2 for a, b in zip(steel, WallRenderer.STEEL_COLOR)) < 25 ** 2
    assert not any(plate.inflate(4, 4).collidepoint(weed.base) for weed in m.wall_renderer.weeds)


def ridge_length(renderer):
    return sum(math.dist(*key) for key in renderer._segments if key not in renderer._strong_edges)


def test_weed_density_matches_square():
    densities = []
    for curved in (True, False):
        _, renderer = paint(curved_maze(curved))
        densities.append(len(renderer.weeds) / ridge_length(renderer) * 1000)
    curved_density, square_density = densities
    assert 0.5 * square_density <= curved_density <= 2 * square_density, densities


def test_joints_only_at_sharp_turns(monkeypatch):
    m = curved_maze()
    joints = []
    real = WallRenderer._paint_joint
    monkeypatch.setattr(WallRenderer, '_paint_joint',
                        lambda self, surface, corner: (joints.append(corner), real(self, surface, corner)))
    _, renderer = paint(m)
    ends = {}
    for start, end in renderer._segments:
        ends.setdefault(start, []).append(end)
        ends.setdefault(end, []).append(start)
    allowed = 0
    for (x, y), others in ends.items():
        if len(others) != 2:
            allowed += 1
            continue
        (ax, ay), (bx, by) = others
        turn = abs((math.atan2(by - y, bx - x) - math.atan2(y - ay, x - ax) + math.pi) % (2 * math.pi) - math.pi)
        allowed += math.degrees(turn) > 35
    assert 0 < len(set(joints)) <= allowed
    assert len(set(joints)) < len(ends) / 3
