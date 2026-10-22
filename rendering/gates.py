"""Drawing for gates: a plank as a filled capsule with an outline, on a pin; a motor gate in its own colour.
Takes plain values so the level editor can draw gates too."""
import math
from typing import Optional, Tuple

import pygame

Point = Tuple[float, float]
Color = Tuple[int, int, int]

FREE_FILL: Color = (70, 120, 130)
FREE_EDGE: Color = (120, 235, 245)
MOTOR_FILL: Color = (130, 85, 40)
MOTOR_EDGE: Color = (255, 190, 80)
PIN_COLOR: Color = (235, 245, 250)


def _capsule(a: Point, b: Point, radius: float) -> list:
    """Outline points of a capsule round the segment a-b."""
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    points = []
    steps = 10
    for i in range(steps + 1):
        t = angle - math.pi / 2 + math.pi * i / steps
        points.append((b[0] + math.cos(t) * radius, b[1] + math.sin(t) * radius))
    for i in range(steps + 1):
        t = angle + math.pi / 2 + math.pi * i / steps
        points.append((a[0] + math.cos(t) * radius, a[1] + math.sin(t) * radius))
    return points


def draw_gate(screen: pygame.Surface, pin: Point, angle: float, half_length: float, thickness: float,
              motor: Optional[str]) -> None:
    """Draw a plank on its pin. `angle` is in radians (increasing is clockwise on screen); `motor` is None, 'cw' or 'ccw'."""
    fill, edge = (MOTOR_FILL, MOTOR_EDGE) if motor else (FREE_FILL, FREE_EDGE)
    dx, dy = math.cos(angle) * half_length, math.sin(angle) * half_length
    a, b = (pin[0] - dx, pin[1] - dy), (pin[0] + dx, pin[1] + dy)
    outline = _capsule(a, b, thickness / 2)
    pygame.draw.polygon(screen, fill, outline)
    pygame.draw.polygon(screen, edge, outline, 2)
    pygame.draw.circle(screen, PIN_COLOR, (int(pin[0]), int(pin[1])), max(3, int(thickness / 3)))
    pygame.draw.circle(screen, edge, (int(pin[0]), int(pin[1])), max(3, int(thickness / 3)), 1)
