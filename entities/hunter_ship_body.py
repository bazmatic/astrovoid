"""The look of a creature shaped like a hunter ship: the arrowhead, its engine and plume in its kind's colours, a bar of
the hits it has left if its kind shows one, and an expanding ring when it dies."""
import pygame

import config
from entities.hunter_ship import HunterShip

_COLOURS = (('COLOR', 'color'), ('FILL', 'fill'), ('NOSE_COLOR', 'noseColor'), ('COCKPIT_COLOR', 'cockpitColor'),
            ('ENGINE_COLOR', 'engineColor'), ('ENGINE_LIT_COLOR', 'engineLitColor'))


class HunterShipBody:
    """Draws through a puppet HunterShip set where the creature is. A creature with a craft (see the pilot trait)
    shows its craft's plume."""

    DEATH_DURATION = HunterShip.DEATH_DURATION
    DEATH_FRICTION = 0.0   # the wreck stays where it was hit
    BAR_WIDTH = 40         # px across, for a ship of the player's size
    BAR_HEIGHT = 4

    def __init__(self, creature):
        self._puppet = HunterShip(creature.get_pos())
        for attribute, key in _COLOURS:
            setattr(self._puppet, attribute, tuple(creature.kind.tuning.get(key, getattr(HunterShip, attribute))))
        self._shows_hit_points = creature.kind.tuning.get('showsHitPoints', False)

    def on_event(self, creature, name: str) -> None:
        """Its look follows its craft, so events change nothing."""

    def update(self, creature, dt: float, target=None) -> None:
        """Nothing moves on its own: the craft carries the plume."""

    def update_death(self, creature, dt: float) -> None:
        """The ring grows with the death timer."""

    def _place(self, creature) -> HunterShip:
        puppet = self._puppet
        puppet.x, puppet.y, puppet.vx, puppet.vy = creature.x, creature.y, creature.vx, creature.vy
        puppet.angle, puppet.radius = creature.angle, creature.radius
        puppet.pilot_thrusting = getattr(creature, 'pilot_thrusting', False)
        craft = getattr(creature, 'craft', None)
        puppet.thrusting = craft.thrusting if craft is not None else False
        puppet.thrust_particles = craft.thrust_particles if craft is not None else []
        return puppet

    def draw(self, screen: pygame.Surface, creature) -> None:
        self._place(creature).draw(screen)
        if self._shows_hit_points:
            self._draw_hit_points(screen, creature)

    def draw_death(self, screen: pygame.Surface, creature) -> None:
        puppet = self._place(creature)
        puppet.active, puppet.death_timer = False, creature.death_timer
        puppet.draw_death(screen)
        puppet.active = True

    def _draw_hit_points(self, screen, creature):
        """A bar above it, as wide as the ship is big, that drains as it is hit."""
        bar = pygame.Rect(0, 0, round(self.BAR_WIDTH * creature.radius / config.SHIP_SIZE), self.BAR_HEIGHT)
        bar.midbottom = (round(creature.x), round(creature.y - creature.radius * 2.2))
        pygame.draw.rect(screen, (60, 20, 20), bar)
        fill = bar.copy()
        fill.width = round(bar.width * max(0, creature.hit_points) / creature.max_hit_points)
        if fill.width:
            pygame.draw.rect(screen, self._puppet.COLOR, fill)
        pygame.draw.rect(screen, (150, 70, 70), bar, 1)
