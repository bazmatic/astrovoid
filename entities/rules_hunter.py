"""The Rules hunter: the Rules pilot's hunter ship, flown as an enemy that hunts only its protagonist.

It is a HunterShip flown by a HunterFlight and the Rules pilot, and a game enemy: shots damage it, it takes
RULES_HUNTER_HIT_POINTS of them, and its shots are enemy shots. What it hunts comes from its surroundings
(see hunter.surroundings.ProtagonistSurroundings), so it never sees or fires at anything else.
"""
import copy
import time
from dataclasses import replace

import pygame

from entities.hunter_ship import HunterShip
from hunter.flight import HunterFlight, WorkerPilot
from hunter.settings_for import hunter_settings_for

RULES_HUNTER_HIT_POINTS = 12
_LIVE = ('flight', '_worker', 'surroundings')       # what a copy for a death portrait must not carry


class RulesHunter(HunterShip):
    # The enemy colour: red, where the allied hunter is green and the Vibes hunter pink.
    COLOR = (255, 90, 90)
    FILL = (110, 25, 25)
    NOSE_COLOR = (255, 215, 200)
    COCKPIT_COLOR = (60, 10, 10)
    ENGINE_COLOR = (170, 60, 20)
    ENGINE_LIT_COLOR = (255, 150, 80)
    SHOT_SOURCE = 'enemy'
    BAR_WIDTH = 40
    BAR_HEIGHT = 4

    def __init__(self, start_pos, worker, surroundings, clock=time.monotonic):
        # Hit points, not the hunter's health, are what a hit costs it: the ship itself is indestructible.
        super().__init__(start_pos, replace(hunter_settings_for('rules'), indestructible=True))
        self.hit_points = self.max_hit_points = RULES_HUNTER_HIT_POINTS
        self.surroundings = surroundings
        self._worker = worker
        self.flight = HunterFlight(self, WorkerPilot(worker, clock), surroundings)

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
        """Stop its pilot and its worker."""
        if self.flight is not None:
            self.flight.close()
        close = getattr(self._worker, 'close', None)     # the lab's synchronous worker has nothing to close
        if close is not None:
            close()

    def draw(self, screen):
        if not self.active:
            return
        super().draw(screen)
        bar = pygame.Rect(0, 0, self.BAR_WIDTH, self.BAR_HEIGHT)
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
