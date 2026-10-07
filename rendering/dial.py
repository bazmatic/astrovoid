"""Neon instrument dials for the HUD.

A dial is a dark glass face inside a glowing rim, with a segmented arc that
fills clockwise from bottom-left to bottom-right. The gap at the bottom holds
the label. Everything that does not change frame to frame is drawn once at
several times its final size, scaled down for smooth edges, and cached.
"""

import math
from typing import Callable, Dict, List, Optional, Tuple

import pygame
from rendering.fonts import get_font

Color = Tuple[int, int, int]

SEGMENTS = 30
SWEEP_START = 135.0  # Degrees on screen (y down), so this is bottom-left
SWEEP_DEGREES = 270.0
SEGMENT_GAP_DEGREES = 2.4
ALERT_PERIOD = 0.9  # Seconds per rim pulse

_SUPERSAMPLE = 3
_FACE_COLOR = (6, 6, 14)
_ALERT_LEVELS = 12

_static_layers: Dict[Tuple[int, Color], pygame.Surface] = {}
_segment_sprites: Dict[Tuple[int, Color], List[Tuple[pygame.Surface, Tuple[int, int]]]] = {}
_alert_layers: Dict[Tuple[int, Color, int], pygame.Surface] = {}
_infinity_symbols: Dict[Tuple[int, Color], pygame.Surface] = {}
_glyphs: Dict[Tuple[int, str, Color], pygame.Surface] = {}
_clock: Optional[Callable[[], float]] = None


def set_clock(clock: Optional[Callable[[], float]]) -> None:
    """Replace the time source for the alert pulse (None restores the real clock)."""
    global _clock
    _clock = clock


def rim_radius(radius: int) -> float:
    """Radius of the glowing rim for a dial of the given nominal radius."""
    return radius * 1.2


def arc_radii(radius: int) -> Tuple[float, float]:
    """Inner and outer radius of the segmented arc."""
    return radius * 0.9, radius * 1.06


def _mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _lit_color(color: Color) -> Color:
    return _mix(color, (255, 255, 255), 0.35)


def _half_size(radius: int) -> int:
    """Half the side of the square a dial and its glow fit in."""
    return int(math.ceil(rim_radius(radius) * 1.3))


def _clear_surface(size: Tuple[int, int], color: Color) -> pygame.Surface:
    """Transparent surface pre-tinted so scaled and blurred edges keep their hue."""
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((*color, 0))
    return surface


def _blurred(surface: pygame.Surface, amount: int) -> pygame.Surface:
    width, height = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, width // amount), max(1, height // amount)))
    return pygame.transform.smoothscale(small, (width, height))


def _segment_points(index: int, inner: float, outer: float, scale: float) -> List[Tuple[float, float]]:
    """Outline of one arc segment around the origin."""
    step = SWEEP_DEGREES / SEGMENTS
    start = SWEEP_START + index * step + SEGMENT_GAP_DEGREES / 2
    end = SWEEP_START + (index + 1) * step - SEGMENT_GAP_DEGREES / 2
    angles = [math.radians(start + (end - start) * i / 4) for i in range(5)]
    outer_edge = [(outer * scale * math.cos(a), outer * scale * math.sin(a)) for a in angles]
    inner_edge = [(inner * scale * math.cos(a), inner * scale * math.sin(a)) for a in reversed(angles)]
    return outer_edge + inner_edge


def _rim_glow(radius: int, color: Color) -> pygame.Surface:
    """Soft halo around the rim, at supersampled size."""
    big = _half_size(radius) * 2 * _SUPERSAMPLE
    glow = _clear_surface((big, big), color)
    pygame.draw.circle(
        glow, (*color, 255), (big // 2, big // 2),
        int(rim_radius(radius) * _SUPERSAMPLE), max(1, int(radius * 0.12 * _SUPERSAMPLE))
    )
    return _blurred(_blurred(glow, 12), 6)


def static_layer(radius: int, color: Color) -> pygame.Surface:
    """Face, rim, tick marks and the unlit track for one dial size and colour."""
    key = (radius, color)
    if key in _static_layers:
        return _static_layers[key]

    scale = _SUPERSAMPLE
    half = _half_size(radius)
    big = half * 2 * scale
    center = (big // 2, big // 2)
    rim = rim_radius(radius)
    inner, outer = arc_radii(radius)
    layer = _clear_surface((big, big), color)

    # Glass face: a faint tint of the dial colour at the centre, fading to near black
    steps = 24
    for i in range(steps):
        t = i / (steps - 1)
        shade = _mix(_FACE_COLOR, _mix(_FACE_COLOR, color, 0.16), t)
        pygame.draw.circle(layer, (*shade, 255), center, int(rim * scale * (1 - t * 0.95)))

    layer.blit(_rim_glow(radius, color), (0, 0))
    pygame.draw.circle(layer, (*_lit_color(color), 255), center, int(rim * scale), max(2, int(radius * 0.035 * scale)))

    tick_color = _mix(_FACE_COLOR, color, 0.6)
    for quarter in range(5):
        angle = math.radians(SWEEP_START + SWEEP_DEGREES * quarter / 4)
        direction = (math.cos(angle), math.sin(angle))
        pygame.draw.line(
            layer, tick_color,
            (center[0] + direction[0] * rim * 0.925 * scale, center[1] + direction[1] * rim * 0.925 * scale),
            (center[0] + direction[0] * rim * 0.975 * scale, center[1] + direction[1] * rim * 0.975 * scale),
            scale
        )

    unlit = _mix(_FACE_COLOR, color, 0.22)
    for index in range(SEGMENTS):
        points = [(center[0] + x, center[1] + y) for x, y in _segment_points(index, inner, outer, scale)]
        pygame.draw.polygon(layer, unlit, points)

    result = pygame.transform.smoothscale(layer, (half * 2, half * 2))
    _static_layers[key] = result
    return result


def _lit_segments(radius: int, color: Color) -> List[Tuple[pygame.Surface, Tuple[int, int]]]:
    """A glowing sprite for each segment, with its offset from the dial centre."""
    key = (radius, color)
    if key in _segment_sprites:
        return _segment_sprites[key]

    scale = _SUPERSAMPLE
    inner, outer = arc_radii(radius)
    lit = _lit_color(color)
    pad = max(3, int(radius * 0.1))
    sprites = []
    for index in range(SEGMENTS):
        points = _segment_points(index, inner, outer, 1.0)
        left = math.floor(min(p[0] for p in points)) - pad
        top = math.floor(min(p[1] for p in points)) - pad
        width = math.ceil(max(p[0] for p in points)) + pad - left
        height = math.ceil(max(p[1] for p in points)) + pad - top

        local = [((x - left) * scale, (y - top) * scale) for x, y in points]
        core = _clear_surface((width * scale, height * scale), color)
        pygame.draw.polygon(core, (*color, 255), local)
        sprite = _blurred(core, 4 * scale)
        sprite.blit(_blurred(core, 2 * scale), (0, 0))
        pygame.draw.polygon(sprite, (*lit, 255), local)
        sprites.append((pygame.transform.smoothscale(sprite, (width, height)), (left, top)))

    _segment_sprites[key] = sprites
    return sprites


def _alert_layer(radius: int, color: Color, level: int) -> pygame.Surface:
    """Extra rim glow for one step of the alert pulse, ready to be added to the screen."""
    key = (radius, color, level)
    if key in _alert_layers:
        return _alert_layers[key]

    half = _half_size(radius)
    glow = pygame.transform.smoothscale(_rim_glow(radius, color), (half * 2, half * 2))
    # Flatten onto black so the colour carries the strength; adding it then cannot darken anything
    layer = pygame.Surface((half * 2, half * 2))
    layer.blit(glow, (0, 0))
    strength = int(255 * level / _ALERT_LEVELS)
    layer.fill((strength, strength, strength), special_flags=pygame.BLEND_RGB_MULT)
    _alert_layers[key] = layer
    return layer


def _infinity_symbol(radius: int, color: Color) -> pygame.Surface:
    """The infinity sign, drawn because the default font has no glyph for it."""
    key = (radius, color)
    if key in _infinity_symbols:
        return _infinity_symbols[key]

    scale = _SUPERSAMPLE
    width, height = int(radius * 0.9), int(radius * 0.5)
    stroke = max(2, int(radius * 0.07))
    big = _clear_surface((width * scale, height * scale), color)
    reach = (width / 2 - stroke) * scale
    points = []
    for i in range(65):
        t = 2 * math.pi * i / 64
        # Lemniscate of Bernoulli
        denominator = 1 + math.sin(t) ** 2
        points.append((
            width * scale / 2 + reach * math.cos(t) / denominator,
            height * scale / 2 + reach * math.sin(t) * math.cos(t) / denominator
        ))
    for point in points:
        pygame.draw.circle(big, (*color, 255), point, stroke * scale / 2)
    pygame.draw.lines(big, (*color, 255), True, points, stroke * scale)

    result = pygame.transform.smoothscale(big, (width, height))
    _infinity_symbols[key] = result
    return result


def _draw_reading(screen: pygame.Surface, text: str, size: int, color: Color, center: Tuple[int, int]) -> None:
    """Draw text one character per fixed cell, so a changing digit never moves its neighbours.

    Digits differ in width and the font kerns pairs such as "1." and "7.", so
    rendering the string whole makes a centred reading jitter as it counts.
    """
    font = get_font(size, bold=True)
    digit_cell = max(font.size(digit)[0] for digit in "0123456789")
    cells = []
    for char in text:
        key = (size, char, color)
        if key not in _glyphs:
            _glyphs[key] = font.render(char, True, color)
        glyph = _glyphs[key]
        cells.append((glyph, digit_cell if char.isdigit() else glyph.get_width()))

    x = center[0] - sum(width for _, width in cells) // 2
    y = center[1] - font.get_height() // 2
    for glyph, width in cells:
        screen.blit(glyph, (x + (width - glyph.get_width()) // 2, y))
        x += width


def _now() -> float:
    return _clock() if _clock else pygame.time.get_ticks() / 1000.0


def draw_dial(
    screen: pygame.Surface,
    center_x: int,
    center_y: int,
    radius: int,
    percentage: float,
    value_text: str,
    color: Color,
    text_color: Color = (255, 255, 255),
    label_text: Optional[str] = None,
    alert: bool = False
) -> None:
    """Draw one dial.

    Args:
        screen: The pygame Surface to draw on.
        center_x: X coordinate of dial center.
        center_y: Y coordinate of dial center.
        radius: Nominal radius; the rim sits a little outside it.
        percentage: How much of the arc is lit (0.0 to 1.0).
        value_text: Reading shown in the middle of the face.
        color: RGB colour of the rim and arc.
        text_color: RGB colour of the reading.
        label_text: Optional name shown in the gap at the bottom of the arc.
        alert: Pulse the rim to draw the eye.
    """
    percentage = max(0.0, min(1.0, percentage))
    color = tuple(color)
    half = _half_size(radius)

    screen.blit(static_layer(radius, color), (center_x - half, center_y - half))

    if alert:
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * _now() / ALERT_PERIOD)
        level = int(round(pulse * _ALERT_LEVELS))
        if level > 0:
            screen.blit(
                _alert_layer(radius, color, level), (center_x - half, center_y - half),
                special_flags=pygame.BLEND_RGB_ADD
            )

    progress = percentage * SEGMENTS
    for index, (sprite, (left, top)) in enumerate(_lit_segments(radius, color)):
        strength = min(1.0, progress - index)
        if strength <= 0.01:
            break
        # The segment being spent fades out rather than vanishing at once
        sprite.set_alpha(int(255 * strength))
        screen.blit(sprite, (center_x + left, center_y + top))
        sprite.set_alpha(255)

    value_center = (center_x, center_y - int(radius * 0.06))
    if value_text == "∞":
        symbol = _infinity_symbol(radius, tuple(text_color))
        screen.blit(symbol, symbol.get_rect(center=value_center))
    elif value_text:
        _draw_reading(screen, value_text, max(16, int(radius * 0.6)), tuple(text_color), value_center)

    if label_text:
        label = get_font(max(12, int(radius * 0.3)), bold=True).render(label_text, True, _mix(color, (255, 255, 255), 0.25))
        screen.blit(label, label.get_rect(center=(center_x, center_y + int(radius * 0.8))))
