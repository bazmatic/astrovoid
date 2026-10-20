"""The Belemnite: a spiky squid in a pointed shell that chases the player as a Jelly does. It has no guns, and it
explodes when it dies, hurting everything near it: the player, the hunter, walls and other enemies, so one Belemnite
can set off the next."""
import math

import pygame

from entities.enemy import Enemy
from entities.explosion import Blast


class Belemnite(Enemy):
    """A Jelly's brain (the aggressive strategy) in a Belemnite's body; it takes HIT_POINTS hits and leaves a blast."""
    HIT_POINTS = 3
    COLOR = (240, 120, 60)              # what its shock ring and the editor chip take after
    # Its blast: its reach in multiples of its radius, the hits it deals each enemy (enough to set off another
    # Belemnite), and the frames between being killed and going off, which make a chain ripple
    BLAST_REACH = 7.0
    BLAST_DAMAGE = HIT_POINTS
    BLAST_PUSH = 7.0
    BLAST_FUSE = 8.0

    def __init__(self, pos, level=1):
        super().__init__(pos, 'aggressive', level)
        self.type = 'belemnite'
        self.jellyfish = None
        self._body = BelemniteBody()
        self.hit_points = self.max_hit_points = self.HIT_POINTS

    def take_damage(self) -> bool:
        """A hit; True when it destroyed it."""
        self.hit_points -= 1
        return self.hit_points <= 0

    def apply_momentum(self, vx: float, vy: float) -> None:
        """A shove: it swims on, but drifts with it."""
        self.vx += vx
        self.vy += vy

    def blast(self, source='enemy'):
        """The blast it makes when it dies; its kills count for `source`, whoever killed it."""
        return Blast((self.x, self.y), self.radius * self.BLAST_REACH, damage=self.BLAST_DAMAGE, push=self.BLAST_PUSH,
                     wall_hits=1, source=source, fuse=self.BLAST_FUSE, color=self.COLOR)


class BelemniteBody:
    """Animation and drawing for a Belemnite: it swims point first, the way its brain faces it."""
    SHELL = (226, 204, 160)
    SHELL_DARK = (150, 120, 85)
    SHELL_RIDGE = (120, 92, 62)
    SPIKE = (250, 236, 205)
    MANTLE = (196, 52, 64)
    MANTLE_DARK = (110, 24, 40)
    EYE = (255, 225, 90)
    FUSE = (255, 150, 50)               # the glow at its heart that says it will explode
    # The shell, in multiples of the radius along the heading
    SHELL_TIP_X = 1.6
    SHELL_BACK_X = 0.05
    SHELL_HALF_WIDTH = 0.55
    SPIKES_X = (0.35, 0.75, 1.1)
    TENTACLES = 6
    DEATH_DURATION = 0.0                # the fireball is its death
    DEATH_FRICTION = 0.9

    def __init__(self):
        self.swim = 0.0                 # the tentacles' stroke, in radians

    @staticmethod
    def _pace(enemy):
        """How hard it is swimming, as a share of its top speed."""
        return min(1.5, math.hypot(enemy.vx, enemy.vy) / max(enemy.speed, 1e-6))

    def update(self, enemy, dt, player_pos=None):
        self.swim += dt * (0.1 + 0.25 * self._pace(enemy))      # the faster it swims, the faster it strokes

    def update_death(self, enemy, dt):
        pass

    def draw_death(self, screen, enemy):
        pass

    def draw(self, screen, enemy):
        place = self._placer(enemy)
        self._draw_tentacles(screen, enemy, place)
        self._draw_mantle(screen, enemy, place)
        self._draw_shell(screen, place)

    @staticmethod
    def _placer(enemy):
        """Converts a point in its own frame (radius units, x along its heading) to the screen."""
        heading = math.radians(enemy.angle)
        cos_h, sin_h, r = math.cos(heading), math.sin(heading), enemy.radius
        return lambda x, y: (enemy.x + (x * cos_h - y * sin_h) * r, enemy.y + (x * sin_h + y * cos_h) * r)

    def _draw_tentacles(self, screen, enemy, place):
        # Trailing behind, waving; drawn in tighter the harder it swims
        spread = 0.42 - 0.14 * min(1.0, self._pace(enemy))
        for i in range(self.TENTACLES):
            across = (i / (self.TENTACLES - 1) - 0.5) * 2.0 * spread
            points = []
            for step in range(5):
                along = step / 4
                wave = math.sin(self.swim * 6.0 - along * 4.0 + i * 1.3) * 0.18 * along
                points.append(place(-0.55 - along * 1.1, across * (1.0 + 0.6 * along) + wave))
            pygame.draw.lines(screen, self.MANTLE_DARK if i % 2 else self.MANTLE, False, points,
                              max(1, round(enemy.radius * 0.18)))

    def _draw_mantle(self, screen, enemy, place):
        # An oval from just under the shell back to where the tentacles start
        body = [place(0.25 - 0.95 * (1 - math.cos(t)) / 2, 0.5 * math.sin(t))
                for t in (k * 2 * math.pi / 16 for k in range(16))]
        pygame.draw.polygon(screen, self.MANTLE, body)
        pygame.draw.lines(screen, self.MANTLE_DARK, True, body, 1)
        # Its heart glows like a lit fuse, faster and brighter the closer it is to going off
        hurt = 1.0 - enemy.hit_points / enemy.max_hit_points
        pulse = 0.5 + 0.5 * math.sin(self.swim * (8.0 + 16.0 * hurt))
        heat = 0.35 + 0.65 * max(hurt, 0.3) * pulse
        heart = place(-0.25, 0.0)
        glow = tuple(round(m + (f - m) * heat) for m, f in zip(self.MANTLE, self.FUSE))
        pygame.draw.circle(screen, glow, (round(heart[0]), round(heart[1])), max(2, round(enemy.radius * 0.24)))
        for side in (-1, 1):
            eye = place(0.0, side * 0.33)
            pygame.draw.circle(screen, self.EYE, (round(eye[0]), round(eye[1])), max(1, round(enemy.radius * 0.13)))

    def _shell_half_width(self, x):
        return self.SHELL_HALF_WIDTH * (self.SHELL_TIP_X - x) / (self.SHELL_TIP_X - self.SHELL_BACK_X)

    def _draw_shell(self, screen, place):
        tip, back, half = self.SHELL_TIP_X, self.SHELL_BACK_X, self.SHELL_HALF_WIDTH
        # Spikes first, so the shell's edge covers their roots: each leans back from the point
        for x in self.SPIKES_X:
            width = self._shell_half_width(x)
            for side in (-1, 1):
                spike = [place(x + 0.12, side * width * 0.8), place(x - 0.12, side * width * 0.8),
                         place(x - 0.3, side * (width + 0.38))]
                pygame.draw.polygon(screen, self.SPIKE, spike)
        shell = [place(tip, 0.0), place(back, half), place(back - 0.12, 0.0), place(back, -half)]
        pygame.draw.polygon(screen, self.SHELL_DARK, shell)
        # Lighter along the top, so it reads as a cone
        pygame.draw.polygon(screen, self.SHELL, [place(tip, 0.0), place(back, half * 0.75), place(back, -half * 0.2)])
        for x in self.SPIKES_X:
            width = self._shell_half_width(x)
            pygame.draw.line(screen, self.SHELL_RIDGE, place(x, width), place(x, -width), 1)
        pygame.draw.lines(screen, self.SPIKE, True, shell, 1)
