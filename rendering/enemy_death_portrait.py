"""An isolated replay of a killed enemy's own death animation."""

from copy import deepcopy
import pygame


class EnemyDeathPortrait:
    """Keep world-space animation details local and scale the finished drawing."""

    DURATION = 120.0  # Menu frames (two seconds)

    def __init__(self, enemy, radius: int):
        self.enemy = deepcopy(enemy)
        self.radius = radius
        self.elapsed = 0.0
        scale = radius / self.enemy.radius
        old_x, old_y = self.enemy.x, self.enemy.y
        self.size = max(16, radius * 8)
        center = self.size / 2
        self.enemy.x = self.enemy.y = center
        self.enemy.radius = radius
        self.enemy.vx = self.enemy.vy = 0.0
        self.enemy.active = False
        self.enemy.death_timer = float(self.enemy.DEATH_DURATION)
        # Scale world-space appendages and egg fragments with the creature.
        for owner in (self.enemy, getattr(self.enemy, 'jellyfish', None)):
            for chain in getattr(owner, 'tentacles', ()):
                for index, (x, y) in enumerate(chain):
                    chain[index] = (center + (x - old_x) * scale, center + (y - old_y) * scale)
        for name in ('initial_radius', 'current_radius', 'max_radius'):
            if hasattr(self.enemy, name):
                setattr(self.enemy, name, getattr(self.enemy, name) * scale)
        for blob in getattr(self.enemy, 'blobs', ()):
            blob.x = center + (blob.x - old_x) * scale
            blob.y = center + (blob.y - old_y) * scale
            blob.radius *= scale
            blob.vx *= scale
            blob.vy *= scale
        self.surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)

    def update(self, dt: float) -> None:
        remaining = max(0.0, self.DURATION - self.elapsed)
        step = min(max(0.0, dt), remaining)
        self.elapsed += step
        self.enemy.update_death(step * self.enemy.DEATH_DURATION / self.DURATION)

    def draw(self, screen: pygame.Surface, center) -> None:
        if self.elapsed >= self.DURATION:
            return
        self.surface.fill((0, 0, 0, 0))
        self.enemy.draw_death(self.surface)
        screen.blit(self.surface, self.surface.get_rect(center=center))
