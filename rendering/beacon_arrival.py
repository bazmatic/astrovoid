"""Light streams from the playfield boundary into an allied beacon. No simulation state or random draws."""
import math

import pygame

import config
from rendering.fonts import get_font


def light_paths(bounds, target):
    """Quadratic paths, starting at evenly spaced points on all four edges and ending at the beacon."""
    for edge in range(4):
        for i, fraction in enumerate((0.12, 0.37, 0.63, 0.88)):
            if edge == 0:
                start = (bounds.left + fraction * bounds.width, bounds.top)
            elif edge == 1:
                start = (bounds.right - 1, bounds.top + fraction * bounds.height)
            elif edge == 2:
                start = (bounds.left + fraction * bounds.width, bounds.bottom - 1)
            else:
                start = (bounds.left, bounds.top + fraction * bounds.height)
            dx, dy = target[0] - start[0], target[1] - start[1]
            distance = max(1, math.hypot(dx, dy))
            bend = min(150, distance * 0.18) * (1 if (edge + i) % 2 else -1)
            control = ((start[0] + target[0]) / 2 - dy / distance * bend,
                       (start[1] + target[1]) / 2 + dx / distance * bend)
            yield start, control, target


def _point(path, t):
    a, b, c = path
    return tuple((1-t)**2*a[i] + 2*(1-t)*t*b[i] + t*t*c[i] for i in (0, 1))


def draw_arrival(screen, layer, target, age, formation_frames, arrival_frames, emblem):
    layer.fill((0, 0, 0, 0))
    left = config.UI_ZONE_WIDTH if screen.get_width() > config.UI_ZONE_WIDTH * 2 else 0
    bounds = pygame.Rect(left, 0, screen.get_width() - left, screen.get_height())
    layer.set_clip(bounds)
    progress = age / formation_frames
    amber, green = (255, 200, 80), (120, 255, 190)
    for index, path in enumerate(light_paths(bounds, target)):
        delay = (index % 4) * 3
        t = max(0, min(1, (age-delay) / (formation_frames-delay))) ** 1.35
        if age < delay or progress > 1.12:
            continue
        tail = max(0, t - 0.24)
        points = [_point(path, tail + (t-tail)*j/12) for j in range(13)]
        colour = amber if index % 2 else green
        fade = max(0, min(1, (1.12-progress)/0.12))
        for width, alpha in ((15, 16), (7, 55), (3, 180), (1, 255)):
            pygame.draw.lines(layer, (*colour, round(alpha*fade)), False, points, width)
        tip = points[-1]
        pygame.draw.circle(layer, (255, 255, 230, round(255*fade)), (round(tip[0]), round(tip[1])), 3)
        # Streaks along the path make the movement legible even at long distances.
        for j in range(3):
            p = _point(path, max(0, t-j*0.035))
            pygame.draw.circle(layer, (*colour, round((150-j*40)*fade)), (round(p[0]), round(p[1])), 2)
    centre = (round(target[0]), round(target[1]))
    charge = min(1, max(0, progress))
    if progress < 1:
        # A contracting magic seal and the emerging emblem await the incoming light.
        radius = round(12 + 48*(1-charge))
        pygame.draw.circle(layer, (*amber, round(60+130*charge)), centre, radius, 1)
        points = emblem(target, 11)
        for index in range(len(points)):
            end = min(1, max(0, charge*len(points)-index))
            if end > 0:
                a, b = points[index], points[(index+1) % len(points)]
                pygame.draw.line(layer, (200, 255, 200, round(255*charge)), a,
                                 (a[0]+(b[0]-a[0])*end, a[1]+(b[1]-a[1])*end), 2)
    else:
        burst = min(1, (age-formation_frames)/(arrival_frames-formation_frames))
        fade = 1-burst
        for width, alpha in ((8, 35), (3, 220)):
            pygame.draw.circle(layer, (*amber, round(alpha*fade)), centre, round(18+145*burst), width)
        for i in range(20):
            angle = math.tau*i/20 + burst*0.4
            r = 14+105*burst
            a = (target[0]+math.cos(angle)*r, target[1]+math.sin(angle)*r)
            b = (a[0]+math.cos(angle)*16*fade, a[1]+math.sin(angle)*16*fade)
            pygame.draw.line(layer, (*green, round(255*fade)), a, b, 2)
        if burst < 0.35:
            flash = 1-burst/0.35
            for radius, alpha in ((65, 25), (38, 75), (18, 255)):
                pygame.draw.circle(layer, (255, 255, 225, round(alpha*flash)), centre, max(1, round(radius*flash)))
    screen.blit(layer, (0, 0))
    if progress >= 1:
        text = get_font(22).render('ALLY BEACON', True, amber)
        text.set_alpha(round(255*min(1, (arrival_frames-age)/24)))
        x = max(bounds.left+text.get_width()/2+8, min(bounds.right-text.get_width()/2-8, target[0]))
        screen.blit(text, text.get_rect(midbottom=(round(x), max(24, round(target[1]-35)))))
