"""An enemy hunter: a hunter ship flown by a pilot as an enemy that hunts only its protagonist.

It is a HunterShip flown by a HunterFlight, and a game enemy: shots damage it, it takes ENEMY_HUNTER_HIT_POINTS of
them, and its shots are enemy shots. What it hunts comes from its surroundings (see
hunter.surroundings.ProtagonistSurroundings), so it never sees or fires at anything else. The Rules hunter and the
Neural hunter differ only in their pilot and colour.
"""
import copy
from dataclasses import replace

import pygame

from entities.hunter_ship import HunterShip
from hunter.flight import HunterFlight

ENEMY_HUNTER_HIT_POINTS = 12
_LIVE = ('flight', '_worker', 'surroundings')       # what a copy for a death portrait must not carry


class EnemyHunter(HunterShip):
    SHOT_SOURCE = 'enemy'
    HIT_POINTS = ENEMY_HUNTER_HIT_POINTS
    SIZE_SCALE = 1.0  # its radius (and so its drawing and collisions) as a share of a normal ship's
    SHOWS_HIT_POINTS = False  # only the big ones carry a bar of the hits they have left
    BAR_WIDTH = 40
    BAR_HEIGHT = 4

    def __init__(self, start_pos, settings, pilot, surroundings, worker=None):
        """`pilot` flies it (None: it is only drawn, as in the level editor); `worker` is closed with it."""
        # Hit points, not the hunter's health, are what a hit costs it: the ship itself is indestructible.
        super().__init__(start_pos, replace(settings, indestructible=True))
        self.radius *= self.SIZE_SCALE
        self.hit_points = self.max_hit_points = self.HIT_POINTS
        self.surroundings = surroundings
        self._worker = worker
        self.flight = HunterFlight(self, pilot, surroundings) if pilot is not None else None

    def fly(self, dt):
        """Fly one frame; returns the shots fired, for the game to place."""
        if not self.active or self.flight is None:
            return []
        return self.flight.fly(dt)

    def take_damage(self):
        """A shot hit it. Returns True when that destroyed it."""
        self.hit_points -= 1
        return self.hit_points <= 0

    def die(self):
        super().die()
        self.close()

    def close(self):
        """Stop its pilot and any worker it has."""
        if self.flight is not None:
            self.flight.close()
        close = getattr(self._worker, 'close', None)     # no worker, or the lab's synchronous one: nothing to close
        if close is not None:
            close()

    def draw(self, screen):
        if not self.active:
            return
        super().draw(screen)
        if self.SHOWS_HIT_POINTS:
            self._draw_hit_points(screen)

    def _draw_hit_points(self, screen):
        """A bar above it, as wide as the ship is big, that drains as it is hit."""
        bar = pygame.Rect(0, 0, round(self.BAR_WIDTH * self.SIZE_SCALE), self.BAR_HEIGHT)
        bar.midbottom = (round(self.x), round(self.y - self.radius * 2.2))
        pygame.draw.rect(screen, (60, 20, 20), bar)
        fill = bar.copy()
        fill.width = round(bar.width * max(0, self.hit_points) / self.max_hit_points)
        if fill.width:
            pygame.draw.rect(screen, self.COLOR, fill)
        pygame.draw.rect(screen, (150, 70, 70), bar, 1)

    def __deepcopy__(self, memo):
        """A copy for a death portrait: the ship as it was, without its pilot, worker or view of the game."""
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(copy.deepcopy({k: v for k, v in self.__dict__.items() if k not in _LIVE}, memo))
        for name in _LIVE:
            clone.__dict__[name] = None
        return clone
