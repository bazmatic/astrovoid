"""The HUD dials are neon instruments: a segmented arc that fills clockwise around a dark face."""
import math

import pygame
import pytest
import config
from entities.ship import Ship
from rendering import dial
from rendering.ui_elements import UIElementRenderer

CENTER = (150, 150)
RADIUS = 60
COLOR = (100, 200, 255)
BACKGROUND = (5, 0, 15)


def draw(percentage, color=COLOR, text="42", label=None, **kwargs):
    screen = pygame.Surface((300, 300), pygame.SRCALPHA)
    screen.fill((*BACKGROUND, 255))
    UIElementRenderer.draw_circular_gauge(
        screen, CENTER[0], CENTER[1], RADIUS, percentage, text, color, label_text=label, **kwargs
    )
    return screen


def arc_pixels(screen):
    """Colours of the pixels inside the band the segments occupy, with their sweep angle."""
    inner, outer = dial.arc_radii(RADIUS)
    pixels = []
    for x in range(screen.get_width()):
        for y in range(screen.get_height()):
            dx, dy = x - CENTER[0], y - CENTER[1]
            if inner + 1 <= math.hypot(dx, dy) <= outer - 1:
                pixels.append((math.degrees(math.atan2(dy, dx)) % 360, tuple(screen.get_at((x, y)))[:3]))
    return pixels


def lit(screen):
    return sum(1 for _, rgb in arc_pixels(screen) if max(rgb) >= 180)


def test_more_of_the_arc_lights_as_the_value_rises():
    counts = [lit(draw(p)) for p in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert counts[0] == 0
    assert counts == sorted(counts)
    assert len(set(counts)) == len(counts)


def test_a_partly_spent_segment_is_dimmer_than_a_full_one():
    one_segment = 1.0 / dial.SEGMENTS
    full = max(max(rgb) for _, rgb in arc_pixels(draw(one_segment)))
    partial = max(max(rgb) for _, rgb in arc_pixels(draw(one_segment * 0.4)))
    empty = max(max(rgb) for _, rgb in arc_pixels(draw(0.0)))
    assert empty < partial < full


def test_unlit_segments_stay_visible_as_a_dim_track():
    track = [rgb for _, rgb in arc_pixels(draw(0.0)) if max(rgb) >= 40]
    assert len(track) > 500
    # Tinted with the dial colour, not grey
    r, g, b = (sum(c[i] for c in track) / len(track) for i in range(3))
    assert b > g > r


def test_arc_leaves_a_gap_at_the_bottom_for_the_label():
    # Straight down is 90 degrees on screen; the sweep runs clockwise from 135 round to 45
    pixels = arc_pixels(draw(1.0, text="", label=None))
    in_gap = [rgb for angle, rgb in pixels if 60 <= angle <= 120]
    in_sweep = [rgb for angle, rgb in pixels if angle >= 150 or angle <= 30]
    assert max(max(rgb) for rgb in in_gap) < 40
    assert max(max(rgb) for rgb in in_sweep) >= 180


def test_arc_fills_clockwise_from_bottom_left():
    lit_angles = [angle for angle, rgb in arc_pixels(draw(0.3)) if max(rgb) >= 180]
    assert min(lit_angles) >= dial.SWEEP_START - 2
    assert max(lit_angles) <= dial.SWEEP_START + 0.3 * dial.SWEEP_DEGREES + 2


def test_screen_stays_opaque():
    screen = draw(0.6, label="AMMO", alert=True)
    assert pygame.mask.from_surface(screen, 254).count() == 300 * 300


def test_value_and_label_are_drawn_on_the_face():
    blank = draw(0.5, text="", label=None)
    with_text = draw(0.5, label="AMMO")
    inner, _ = dial.arc_radii(RADIUS)
    changed = [
        (x, y)
        for x in range(300) for y in range(300)
        if with_text.get_at((x, y)) != blank.get_at((x, y))
    ]
    assert changed
    value = [p for p in changed if p[1] < CENTER[1] + inner * 0.4]
    label = [p for p in changed if p[1] > CENTER[1] + inner * 0.6]
    assert value and label
    # The label sits in the gap, inside the rim
    assert all(math.hypot(x - CENTER[0], y - CENTER[1]) < dial.rim_radius(RADIUS) for x, y in label)


def value_ink_columns(text):
    """Leftmost and rightmost screen column the reading puts ink in."""
    blank = draw(0.5, text="", label=None)
    screen = draw(0.5, text=text, label=None)
    columns = [x for x in range(300) for y in range(300) if screen.get_at((x, y)) != blank.get_at((x, y))]
    return min(columns), max(columns)


def test_reading_does_not_shift_as_its_digits_change():
    # The font kerns pairs like "1." and "7.", which used to move the whole reading
    rights = {value_ink_columns(text)[1] for text in ("11.1s", "47.4s", "20.0s", "29.4s", "17.7s")}
    assert len(rights) == 1
    lefts = {value_ink_columns(text)[0] for text in ("40.0s", "41.1s", "47.7s", "48.8s")}
    assert len(lefts) == 1


def test_narrow_and_wide_digits_take_the_same_room():
    # "1" is narrower than "8" in the game font, but each sits in the same cell
    narrow, wide = value_ink_columns("11.1s"), value_ink_columns("88.8s")
    assert narrow[1] == wide[1]
    assert 0 <= narrow[0] - wide[0] <= 6


def test_reading_is_centred():
    left, right = value_ink_columns("88.8s")
    assert abs((left + right) / 2 - CENTER[0]) <= 1.5


def test_infinity_is_drawn_as_two_loops_not_a_missing_glyph():
    blank = draw(1.0, text="", label=None)
    screen = draw(1.0, text="∞", label=None, text_color=(255, 255, 255))
    inked = pygame.mask.from_threshold(screen, (255, 255, 255), (60, 60, 60, 255))
    inked.erase(pygame.mask.from_threshold(blank, (255, 255, 255), (60, 60, 60, 255)), (0, 0))
    box = inked.get_bounding_rects()[0].unionall(inked.get_bounding_rects())
    assert box.width > box.height * 1.6
    # Both loops are open and the strokes cross in the middle
    row = box.centery
    assert inked.get_at((box.centerx, row))
    assert not inked.get_at((box.left + box.width // 4, row))
    assert not inked.get_at((box.right - box.width // 4, row))


def test_static_layers_are_built_once_per_size_and_colour():
    draw(0.5)
    first = dial.static_layer(RADIUS, COLOR)
    draw(0.9)
    assert dial.static_layer(RADIUS, COLOR) is first
    assert dial.static_layer(RADIUS, (255, 215, 0)) is not first


def test_alert_only_brightens_the_rim():
    dial.set_clock(lambda: 0.0)
    try:
        calm = draw(0.1, color=(255, 100, 100))
        dial.set_clock(lambda: dial.ALERT_PERIOD / 4)  # peak of the pulse
        alarmed = draw(0.1, color=(255, 100, 100), alert=True)
    finally:
        dial.set_clock(None)
    rim = dial.rim_radius(RADIUS)
    brighter = 0
    for x in range(300):
        for y in range(300):
            a, c = alarmed.get_at((x, y)), calm.get_at((x, y))
            if a != c:
                assert abs(math.hypot(x - CENTER[0], y - CENTER[1]) - rim) < rim * 0.3
                assert sum(a[:3]) > sum(c[:3])
                brighter += 1
    assert brighter > 100


class TestShipDials:
    def time_dial_lit(self, seconds):
        screen = pygame.Surface((320, 700), pygame.SRCALPHA)
        screen.fill((*BACKGROUND, 255))
        ship = Ship((0.0, 0.0))
        ship.draw_ui(screen, pygame.font.Font(None, 24), level=None, time_seconds=seconds)
        # Time dial is the top one
        center_x = config.UI_ZONE_WIDTH // 2
        inner, outer = dial.arc_radii(60)
        count = 0
        for x in range(0, 320):
            for y in range(80, 280):
                if inner + 1 <= math.hypot(x - center_x, y - 180) <= outer - 1 and max(screen.get_at((x, y))[:3]) >= 180:
                    count += 1
        return count

    def test_time_dial_sweeps_once_a_minute(self):
        pygame.font.init()
        assert self.time_dial_lit(0.0) == 0
        assert self.time_dial_lit(15.0) < self.time_dial_lit(30.0) < self.time_dial_lit(59.0)
        assert self.time_dial_lit(61.0) < self.time_dial_lit(15.0)


class TestHudColumn:
    """The dials hug the left edge so the maze gets as much of the screen as possible."""

    def drawn_columns(self):
        screen = pygame.Surface((400, 700), pygame.SRCALPHA)
        screen.fill((*BACKGROUND, 255))
        ship = Ship((0.0, 0.0))
        ship.gun_upgrade_level = 2
        ship.draw_ui(screen, pygame.font.Font(None, 24), potential_score=50, level=12, time_seconds=58.9)
        return [x for x in range(400) if any(screen.get_at((x, y))[:3] != BACKGROUND for y in range(700))]

    def test_maze_starts_where_the_hud_column_ends(self):
        from maze.positioning import MazePositionCalculator
        calculator = MazePositionCalculator(20, 15)
        assert calculator.offset_x == config.UI_ZONE_WIDTH
        right_edge = calculator.offset_x + calculator.cell_size_x * 20
        assert right_edge == pytest.approx(config.SCREEN_WIDTH - 30)

    def test_hud_stays_inside_its_column(self):
        pygame.font.init()
        columns = self.drawn_columns()
        assert min(columns) >= 0
        assert max(columns) < config.UI_ZONE_WIDTH

    def test_level_number_images_are_not_reloaded_every_frame(self, monkeypatch):
        pygame.font.init()
        loads = []
        load = pygame.image.load
        monkeypatch.setattr(pygame.image, "load", lambda *args: loads.append(args) or load(*args))
        screen = pygame.Surface((400, 700), pygame.SRCALPHA)
        ship = Ship((0.0, 0.0))
        for _ in range(5):
            ship.draw_ui(screen, pygame.font.Font(None, 24), level=12, time_seconds=1.0)
        assert 0 < len(loads) <= 10

    def test_column_is_no_wider_than_the_dials_need(self):
        rim = dial.rim_radius(60)
        center_x = config.UI_ZONE_WIDTH // 2
        # A modest margin either side of the rim, not the old 88px
        assert 20 <= center_x - rim <= 40
        assert 20 <= config.UI_ZONE_WIDTH - (center_x + rim) <= 40
