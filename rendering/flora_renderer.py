"""Draws living weed: each plant at its stage, swaying like the rock's painted weed, and the spores drifting from it.

A seed is a dot. A growing plant is a tuft of blades that lengthen as it grows. A fruiting plant puts stalks up past
its blades, each with a pod that swells and pales as it ripens. A withering plant browns and shrinks. Spores are
pale specks that fade as they die.
"""
import math
from typing import Optional

import pygame

import config
from flora.plants import Flora
from rendering.visual_effects import interpolate_color
from rendering.wall_renderer import WallRenderer

WITHERED = (120, 95, 60)
RIPE_POD = (205, 220, 95)
SPORE = (200, 230, 170)
STALK_FAN = 3.0  # px between neighbouring stalks' tips
LEAF_SIZE = 4.0  # px from where a leaf joins its blade to its tip, on a grown plant


def draw_flora(screen: pygame.Surface, flora, time_seconds: Optional[float] = None) -> None:
    """Draw every plant and spore in a flora."""
    if time_seconds is None:
        time_seconds = pygame.time.get_ticks() / 1000.0
    for plant in flora.plants:
        _draw_plant(screen, plant, time_seconds)
    background = config.COLOR_BACKGROUND
    for spore in flora.spores:
        left = spore.life - spore.age
        fade = min(1.0, left / (spore.life * 0.25)) if spore.life > 0 else 0.0
        screen.set_at((int(spore.x), int(spore.y)), interpolate_color(background, SPORE, fade))


def _draw_plant(screen: pygame.Surface, plant, time_seconds: float) -> None:
    color = interpolate_color(plant.color, WITHERED, plant.withered)
    base_x, base_y = plant.base
    out_x, out_y = plant.direction
    if plant.stage == 'seed':
        pygame.draw.circle(screen, color, (int(base_x + out_x), int(base_y + out_y)), 1)
        return
    # A withering plant browns and droops a little, but keeps most of its leaves to the end
    scale = max(0.2, plant.growth) * (1.0 - 0.3 * plant.withered)
    sway_at = time_seconds * WallRenderer.WEED_SWAY_SPEED + plant.phase

    def bent(length: float, fan: float, sway: float):
        """A blade or stalk of this length, leaning `fan` px sideways at its tip, swaying by `sway`."""
        middle = (base_x + out_x * length * 0.5 - out_y * (fan * 0.5 + sway * 0.35),
                  base_y + out_y * length * 0.5 + out_x * (fan * 0.5 + sway * 0.35))
        tip = (base_x + out_x * length - out_y * (fan + sway), base_y + out_y * length + out_x * (fan + sway))
        return middle, tip

    # The same tuft every frame: its blades and leaves are fixed by its phase
    blades = 3 + int(plant.phase * 10) % 2
    leaves_kept = 1.0 - 0.6 * plant.withered
    for blade in range(blades):
        length = (7.0 + 5.0 * ((plant.phase * (blade + 1) * 7.3) % 1.0)) * scale
        sway = math.sin(sway_at + blade * 0.9) * WallRenderer.WEED_SWAY
        middle, tip = bent(length, (blade - (blades - 1) / 2) * 3.5, sway)
        pygame.draw.lines(screen, color, False, [plant.base, middle, tip], 1)
        for leaf, (start, end) in enumerate(((plant.base, middle), (middle, tip))):
            if (blade * 2 + leaf + 1) / (blades * 2) > leaves_kept:
                continue
            side = 1.0 if (blade + leaf) % 2 else -1.0
            _draw_leaf(screen, color, start, end, side, LEAF_SIZE * scale)

    if plant.stage != 'fruiting':
        return
    ripeness = plant.pod_ripeness
    pod_color = interpolate_color(color, RIPE_POD, ripeness)
    for stalk in range(plant.stalks):
        sway = math.sin(sway_at * 0.8 + stalk * 1.7) * WallRenderer.WEED_SWAY
        middle, tip = bent(Flora.STALK, (stalk - (plant.stalks - 1) / 2) * STALK_FAN, sway)
        pygame.draw.lines(screen, color, False, [plant.base, middle, tip], 1)
        pygame.draw.circle(screen, pod_color, (int(tip[0]), int(tip[1])), int(round(1 + 2 * ripeness)))


def _draw_leaf(screen: pygame.Surface, color, start, end, side: float, size: float) -> None:
    """A small leaf growing from the middle of a blade's segment, angled out to one side and up the blade."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6 or size < 1.0:
        return
    along_x, along_y = dx / length, dy / length
    out_x, out_y = -along_y * side, along_x * side
    joint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

    def at(up: float, out: float):
        return (joint[0] + along_x * up + out_x * out, joint[1] + along_y * up + out_y * out)

    pygame.draw.polygon(screen, color, [joint, at(size * 0.25, size * 0.45), at(size * 0.7, size * 0.75),
                                        at(size * 0.55, size * 0.15)])
