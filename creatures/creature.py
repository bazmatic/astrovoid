"""The Creature: every enemy and ally, assembled from its kind's Body and Traits.

It holds what every creature has, and the state its traits keep. It does not act on its own: the Encounter runs its
traits every frame and animates its Body.
"""
import copy
import random
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import config
from entities.base import GameEntity
from utils import circle_circle_collision
from utils.math_utils import apply_circle_collision_physics

DRAW_MARGIN = 100   # px: a creature further off screen than this is not drawn


@dataclass
class Controls:
    """What a creature's brain asks of its propulsion and gun this frame."""
    turn: float = 0.0                         # -1 (left) to 1 (right)
    thrust: bool = False
    fire: bool = False
    heading: Optional[float] = None           # degrees: the way it wants to go
    aim: Optional[Tuple[float, float]] = None  # where it wants to shoot
    on_target: bool = False
    gun_enabled: bool = True
    track: bool = False
    course: bool = False
    burn_heading: Optional[float] = None
    burn_frames: Optional[float] = None
    burn_reference: Optional[int] = None
    decision_token: object = None
    lead_degrees: Optional[float] = None


class Creature(GameEntity):

    def __init__(self, kind, pos, body, traits: Sequence, level: int = 1, recorder=None, angle=None):
        super().__init__(pos, kind.tuning['size'])
        from creatures.inflation import Inflation
        self.inflation = Inflation()
        self.kind = kind
        self.type = kind.key
        self.allegiance = kind.allegiance
        self.level = level
        self.recorder = recorder
        self.body = body
        self.traits = tuple(traits)
        from creatures.trait import Trait
        self.after_frame_traits = tuple(t for t in self.traits if type(t).on_after_frame is not Trait.on_after_frame)
        self.controls = Controls()
        self.angle = random.uniform(0, 360) if angle is None else angle
        self.speed = 0.0
        self.hit_points = 1
        self.max_hit_points = 1
        self.has_spawned = False
        self.gun_range = 0.0    # how far it can shoot; 0 without a gun
        self.gun_charge = 0.0   # how far its gun is through reloading, 0 to 1

    @property
    def effective_hit_points(self):
        return 1 if self.inflation.active else self.hit_points

    @property
    def hit_radius(self):
        return self.radius*self.inflation.scale

    def _draw_body(self, screen, draw):
        # Grow the body and shooting target without making it unable to fit its corridor.
        if not self.inflation.active:
            draw(screen,self)
            return
        radius = self.radius
        clip = screen.get_clip()
        try:
            screen.set_clip(clip.clip((config.UI_ZONE_WIDTH,0,
                                      max(0,screen.get_width()-config.UI_ZONE_WIDTH),screen.get_height())))
            self.radius = self.hit_radius
            draw(screen,self)
        finally:
            self.radius = radius
            screen.set_clip(clip)

    @property
    def DEATH_DURATION(self) -> float:
        return self.body.DEATH_DURATION

    def emit(self, name: str, encounter) -> None:
        """Tell the Body and every trait that something happened to this creature."""
        self.body.on_event(self, name)
        for trait in self.traits:
            trait.on_event(self, name, encounter)

    def update(self, dt: float) -> None:
        """Nothing: the Encounter drives creatures."""

    def apply_momentum(self, vx: float, vy: float) -> None:
        """Something shoved it: add to its velocity (an anchored creature is put back on its next frame)."""
        self.vx += vx
        self.vy += vy

    def die(self) -> None:
        """It is gone; its Body hears `died` so it can start its death."""
        super().die()
        self.body.on_event(self, 'died')

    def update_death(self, dt: float) -> None:
        """The remains slide to a stop while the Body plays its death."""
        super().update_death(dt)
        self.apply_friction_and_update_position(self.body.DEATH_FRICTION, dt)
        self.body.update_death(self, dt)

    def draw(self, screen) -> None:
        if not self.active:
            return
        margin = max(DRAW_MARGIN,self.hit_radius*3) if self.inflation.active else DRAW_MARGIN
        if (self.x < -margin or self.x > config.SCREEN_WIDTH + margin or
                self.y < -margin or self.y > config.SCREEN_HEIGHT + margin):
            return
        self._draw_body(screen,self.body.draw)

    def draw_death(self, screen) -> None:
        if self.is_dying:
            self._draw_body(screen,self.body.draw_death)

    def check_circle_collision(self, other_pos, other_radius, other_entity=None) -> bool:
        """Whether it overlaps another circle; with the other entity given, the two bounce apart."""
        if not circle_circle_collision((self.x, self.y), self.radius, other_pos, other_radius):
            return False
        if other_entity is not None:
            apply_circle_collision_physics(self, other_entity, config.COLLISION_RESTITUTION)
        return True

    def __deepcopy__(self, memo):
        """A copy for a death portrait: everything but the Encounter it was in and what its traits keep live."""
        from creatures.encounter import Encounter
        live = {name for trait in self.traits for name in trait.LIVE}
        clone = self.__class__.__new__(self.__class__)
        memo[id(self)] = clone
        for name, value in self.__dict__.items():
            setattr(clone, name, None if name in live or isinstance(value, Encounter) else copy.deepcopy(value, memo))
        return clone
