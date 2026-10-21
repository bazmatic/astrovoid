"""The Egg's Body: a jelly egg sac with the baby squid visible inside.

The embryos develop as the egg grows, so the sac shows both how many babies will hatch and how soon. When the egg is
gone, the sac splits open if it hatched, or bursts into blobs of jelly if it was shot.

Its traits (`grows`, `hatches`) keep `growth` and `hatch_count`; before its first frame it draws as just laid, with one
embryo. Events: `hit` jiggles the sac.
"""

import pygame
import math
import random
from dataclasses import dataclass
from typing import Tuple, List, Optional, TYPE_CHECKING
import config
from rendering import visual_effects

if TYPE_CHECKING:
    from creatures.creature import Creature


@dataclass
class JellyBlob:
    """A lump of jelly flung from a burst egg."""
    x: float
    y: float
    vx: float
    vy: float
    radius: float


class EggBody:
    """The look of an egg.

    Attributes:
        wobble_phase: Phase of the sac's wobble, which quickens near hatching.
        jiggle: 1.0 the moment the sac is hit, settling to 0.0.
        ending: "hatched" or "burst" once the egg is gone, None while it lives.
        blobs: Lumps of jelly flung out when the egg is burst.
    """

    # Drawing constants (lengths are multiples of the current radius)
    SAC_POINTS = 28  # Points around the sac's outline
    SAC_RIM_ALPHA = 200
    SAC_CORE_ALPHA = 120  # The middle is thinner, so the embryos show through
    WOBBLE_SPEED = 0.05  # Radians per frame
    URGENT_WOBBLE_SPEED = 0.12  # Extra wobble speed just before hatching
    JIGGLE_DECAY = 0.93  # Jiggle kept per frame
    EMBRYO_ORBIT = 0.36  # Distance of each embryo from the centre when there are several
    EMBRYO_LENGTH = (0.25, 0.55)  # Embryo length when laid and when ready to hatch
    EYES_DEVELOP = (0.3, 0.5)  # Growth progress over which the eyes appear
    TENTACLES_DEVELOP = (0.6, 0.85)  # ... and the tentacles
    URGENCY_START = 0.7  # Growth progress at which the embryos start to squirm
    MAX_TEARS = 4
    SHADOW_COLOR = (20, 10, 50)
    EYE_COLOR = (255, 40, 40)
    # Death animation: the sac splits open on hatching, or bursts when shot
    DEATH_DURATION = 30.0  # Frames (0.5 seconds at 60 FPS)
    BLOB_COUNT = 8
    BLOB_FRICTION = 0.9
    DEATH_FRICTION = BLOB_FRICTION  # The remains drift to a stop like the jelly

    def __init__(self, creature: 'Creature'):
        self._creature = creature
        self.wobble_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.jiggle = 0.0
        self.ending: Optional[str] = None
        self.blobs: List[JellyBlob] = []
        self._jiggle_angle = 0.0
        self._tear_angles = [random.uniform(0, 2 * math.pi) for _ in range(self.MAX_TEARS)]
        self._split_angle = random.uniform(0, math.pi)

    x = property(lambda self: self._creature.x)
    y = property(lambda self: self._creature.y)
    current_radius = property(lambda self: self._creature.radius)
    hit_points = property(lambda self: self._creature.hit_points)
    max_hit_points = property(lambda self: self._creature.max_hit_points)
    death_progress = property(lambda self: self._creature.death_progress)
    is_dying = property(lambda self: self._creature.is_dying)

    @property
    def growth_progress(self) -> float:
        """Growth from 0.0 (just laid) to 1.0 (about to hatch)."""
        return getattr(self._creature, 'growth', 0.0)

    @property
    def baby_count(self) -> int:
        """Babies that will hatch, rolled when the egg is laid so the sac can show them."""
        return getattr(self._creature, 'hatch_count', 1)

    def on_event(self, creature: 'Creature', name: str) -> None:
        """A hit jiggles the sac; its death splits it open if it hatched, or bursts it if not."""
        if name == 'hit':
            self.jiggle = 1.0
            self._jiggle_angle = random.uniform(0, math.pi)
        elif name == 'died':
            self.ending = "hatched" if getattr(creature, 'hatched', False) else "burst"
            if self.ending == "burst":
                for index in range(self.BLOB_COUNT):
                    angle = 2 * math.pi * (index + random.uniform(-0.3, 0.3)) / self.BLOB_COUNT
                    speed = random.uniform(1.0, 2.8)
                    start = self.current_radius * random.uniform(0.3, 0.8)
                    self.blobs.append(JellyBlob(
                        x=creature.x + math.cos(angle) * start,
                        y=creature.y + math.sin(angle) * start,
                        vx=creature.vx + math.cos(angle) * speed,
                        vy=creature.vy + math.sin(angle) * speed,
                        radius=self.current_radius * random.uniform(0.16, 0.32),
                    ))

    def update(self, creature: 'Creature', dt: float, target=None) -> None:
        """The sac wobbles, faster near hatching, and a jiggle settles."""
        self.wobble_phase += dt * (self.WOBBLE_SPEED + self.URGENT_WOBBLE_SPEED * self.urgency)
        self.jiggle *= self.JIGGLE_DECAY ** dt

    def update_death(self, creature: 'Creature', dt: float) -> None:
        """The jelly flies apart."""
        self.wobble_phase += dt * self.WOBBLE_SPEED
        for blob in self.blobs:
            blob.x += blob.vx * dt
            blob.y += blob.vy * dt
            blob.vx *= self.BLOB_FRICTION
            blob.vy *= self.BLOB_FRICTION

    @staticmethod
    def _progress(value: float, span: Tuple[float, float]) -> float:
        """How far value is through a (start, end) span, clamped to 0.0-1.0."""
        return max(0.0, min(1.0, (value - span[0]) / (span[1] - span[0])))

    @property
    def eye_development(self) -> float:
        """How developed the embryos' eyes are (0.0 none, 1.0 complete)."""
        return self._progress(self.growth_progress, self.EYES_DEVELOP)

    @property
    def tentacle_development(self) -> float:
        """How developed the embryos' tentacles are (0.0 none, 1.0 complete)."""
        return self._progress(self.growth_progress, self.TENTACLES_DEVELOP)

    @property
    def urgency(self) -> float:
        """How close the egg is to hatching (0.0 until late on, 1.0 at hatching)."""
        return self._progress(self.growth_progress, (self.URGENCY_START, 1.0))

    @property
    def tear_count(self) -> int:
        """Tears in the sac, growing with the share of hit points lost."""
        if self.max_hit_points <= 0:
            return 0
        lost = 1.0 - max(0.0, min(1.0, self.hit_points / self.max_hit_points))
        return math.ceil(self.MAX_TEARS * lost)

    def embryo_positions(self) -> List[Tuple[float, float]]:
        """Where each embryo sits in the sac, in multiples of the radius.

        A lone embryo floats in the middle; several circle each other slowly.
        """
        if self.baby_count == 1:
            return [(0.0, 0.0)]
        positions = []
        for index in range(self.baby_count):
            angle = self.wobble_phase * 0.4 + index * 2 * math.pi / self.baby_count
            positions.append((math.cos(angle) * self.EMBRYO_ORBIT, math.sin(angle) * self.EMBRYO_ORBIT))
        return positions

    def _sac_outline(self, center: Tuple[float, float], scale: float = 1.0) -> List[Tuple[float, float]]:
        """Outline of the jelly sac: a circle that wobbles, pulses and jiggles."""
        urgency = self.urgency
        points = []
        for index in range(self.SAC_POINTS):
            theta = 2 * math.pi * index / self.SAC_POINTS
            ripple = 0.035 * math.sin(3 * theta + self.wobble_phase)
            ripple += 0.025 * math.sin(5 * theta - self.wobble_phase * 1.3)
            # The sac strains in and out as hatching nears
            ripple += 0.04 * urgency * math.sin(self.wobble_phase * 4.0)
            # A hit squashes it one way then the other
            ripple -= 0.2 * self.jiggle * math.cos(2 * (theta - self._jiggle_angle)) * math.cos(self.jiggle * 14.0)
            reach = self.current_radius * (1.0 + ripple) * scale
            points.append((center[0] + math.cos(theta) * reach, center[1] + math.sin(theta) * reach))
        return points
    
    def _draw_embryo(
        self,
        layer: pygame.Surface,
        center: Tuple[float, float],
        heading: float,
        length: float,
        index: int,
        strength: float = 1.0
    ) -> None:
        """Draw one baby squid curled in the sac.
        
        Args:
            layer: Surface to draw on.
            center: Middle of the embryo, in pixels.
            heading: Direction its mantle points, in radians.
            length: Mantle length in pixels.
            index: Which embryo this is, so they don't move in step.
            strength: Opacity from 0.0 to 1.0.
        """
        body = visual_effects.interpolate_color(config.REPLAY_ENEMY_COLOR, self.SHADOW_COLOR, 0.35)
        alpha = int(235 * strength)
        if alpha <= 0:
            return
        if length < 4.0:
            # Too young to have a shape yet
            pygame.draw.circle(layer, (*body, alpha), (int(center[0]), int(center[1])), max(1, int(round(length / 2))))
            return
        
        cos_heading, sin_heading = math.cos(heading), math.sin(heading)
        
        def place(along: float, across: float) -> Tuple[float, float]:
            return (
                center[0] + (along * cos_heading - across * sin_heading) * length,
                center[1] + (along * sin_heading + across * cos_heading) * length,
            )
        
        urgency = self.urgency
        tentacles = self.tentacle_development
        if tentacles > 0.0:
            for nub, across in enumerate((-0.12, 0.0, 0.12)):
                wiggle = math.sin(self.wobble_phase * 3.0 + nub + index * 2.0) * 0.08 * (1.0 + 2.0 * urgency)
                pygame.draw.line(
                    layer, (*body, alpha), place(-0.45, across),
                    place(-0.45 - 0.32 * tentacles, across * 1.8 + wiggle), 1
                )
        
        left, right = [], []
        for step in range(9):
            u = step / 8
            half_width = 0.3 * math.sin(math.pi * u ** 0.8) ** 0.7
            left.append(place(u - 0.5, -half_width))
            right.append(place(u - 0.5, half_width))
        pygame.draw.polygon(layer, (*body, alpha), left + right[::-1])
        pygame.draw.line(layer, (*config.REPLAY_ENEMY_COLOR, alpha), place(-0.25, 0.0), place(0.35, 0.0), 1)
        
        eyes = self.eye_development
        if eyes > 0.0:
            eye_radius = max(1, int(round(length * 0.11)))
            # Eyes brighten and throb as hatching nears
            throb = 0.6 + 0.4 * math.sin(self.wobble_phase * 5.0 + index)
            eye_color = visual_effects.interpolate_color(self.EYE_COLOR, (255, 170, 150), urgency * throb)
            for across in (-0.26, 0.26):
                eye = place(-0.3, across)
                eye_px = (int(eye[0]), int(eye[1]))
                if urgency > 0.0:
                    pygame.draw.circle(layer, (*self.EYE_COLOR, int(90 * urgency * throb * strength)), eye_px, eye_radius * 2)
                pygame.draw.circle(layer, (*eye_color, int(255 * eyes * strength)), eye_px, eye_radius)
    
    def _draw_embryos(self, layer: pygame.Surface, center: Tuple[float, float], strength: float = 1.0) -> None:
        """Draw every embryo, grown to match the egg."""
        shortest, longest = self.EMBRYO_LENGTH
        length = self.current_radius * (shortest + (longest - shortest) * self.growth_progress)
        # A lone embryo has the sac to itself
        length *= 1.15 if self.baby_count == 1 else 0.85
        squirm = 0.1 + 0.5 * self.urgency
        for index, (x, y) in enumerate(self.embryo_positions()):
            # Curled round the middle of the sac, nose to tail
            heading = math.atan2(y, x) + math.pi / 2 if self.baby_count > 1 else self.wobble_phase * 0.3
            heading += math.sin(self.wobble_phase * 2.3 + index * 2.0) * squirm
            position = (center[0] + x * self.current_radius, center[1] + y * self.current_radius)
            self._draw_embryo(layer, position, heading, length, index, strength)
    
    def draw(self, screen: pygame.Surface, creature: 'Creature') -> None:
        """Draw the egg as a jelly sac with the baby squid visible inside."""
        color = config.COLOR_EGG
        radius = self.current_radius
        screen_center = (int(self.x), int(self.y))
        # Even sizes only, so a growing egg doesn't fill the glow cache
        glow = visual_effects.create_soft_glow_surface(int(radius * 0.85) * 2, color, 50)
        screen.blit(glow, glow.get_rect(center=screen_center))
        
        # Drawn on its own layer so the jelly is see-through
        size = int(radius * 2.6) + 4
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size / 2, size / 2)
        light = visual_effects.interpolate_color(color, (255, 255, 255), 0.55)
        
        outline = self._sac_outline(center)
        pygame.draw.polygon(layer, (*color, self.SAC_RIM_ALPHA), outline)
        core = visual_effects.interpolate_color(color, (255, 255, 255), 0.2)
        pygame.draw.polygon(layer, (*core, self.SAC_CORE_ALPHA), self._sac_outline(center, 0.84))
        self._draw_embryos(layer, center)
        
        # Tears in the membrane where it has been hit
        tear_color = visual_effects.interpolate_color(color, self.SHADOW_COLOR, 0.75)
        for tear_angle in self._tear_angles[:self.tear_count]:
            rim = (center[0] + math.cos(tear_angle) * radius, center[1] + math.sin(tear_angle) * radius)
            jag = (
                center[0] + math.cos(tear_angle + 0.18) * radius * 0.82,
                center[1] + math.sin(tear_angle + 0.18) * radius * 0.82,
            )
            inner = (center[0] + math.cos(tear_angle) * radius * 0.62, center[1] + math.sin(tear_angle) * radius * 0.62)
            pygame.draw.lines(layer, (*tear_color, 255), False, [rim, jag, inner], max(1, int(radius * 0.08)))
        
        pygame.draw.lines(layer, (*light, 255), True, outline, max(1, int(round(radius * 0.08))))
        # A fixed glint at the top left
        glint = (int(center[0] - radius * 0.42), int(center[1] - radius * 0.42))
        pygame.draw.circle(layer, (255, 255, 255, 225), glint, max(1, int(round(radius * 0.13))))
        
        screen.blit(layer, layer.get_rect(center=screen_center))
    
    def draw_death(self, screen: pygame.Surface, creature: 'Creature') -> None:
        """Draw the egg's ending: the sac splitting open, or bursting into blobs."""
        progress = self.death_progress
        visibility = 1.0 - progress
        color = config.COLOR_EGG
        light = visual_effects.interpolate_color(color, (255, 255, 255), 0.55)
        radius = self.current_radius
        size = int(radius * 5) + 64  # Room for blobs flung from even a small egg
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size / 2, size / 2)
        
        if self.ending == "hatched":
            # The two halves of the membrane peel apart
            outline = self._sac_outline(center)
            half = self.SAC_POINTS // 2
            start = int(self._split_angle / (2 * math.pi) * self.SAC_POINTS)
            gap = radius * 0.7 * progress * (2.0 - progress)
            normal_angle = self._split_angle + math.pi / 2
            for side in (1.0, -1.0):
                first = start if side > 0 else start + half
                shift = (math.cos(normal_angle) * gap * side, math.sin(normal_angle) * gap * side)
                points = [
                    (outline[(first + step) % self.SAC_POINTS][0] + shift[0],
                     outline[(first + step) % self.SAC_POINTS][1] + shift[1])
                    for step in range(half + 1)
                ]
                # Empty shells: a faint film with a bright torn rim
                pygame.draw.polygon(layer, (*color, int(self.SAC_CORE_ALPHA * 0.6 * visibility)), points)
                pygame.draw.lines(layer, (*light, int(255 * visibility)), False, points, max(2, int(radius * 0.12)))
        else:
            # Jelly flies outward and the embryos dissolve
            self._draw_embryos(layer, center, strength=max(0.0, 1.0 - progress * 2.5))
            offset = (center[0] - self.x, center[1] - self.y)
            for blob in self.blobs:
                position = (int(blob.x + offset[0]), int(blob.y + offset[1]))
                blob_radius = max(1, int(round(blob.radius * (1.0 - 0.5 * progress))))
                pygame.draw.circle(layer, (*color, int(self.SAC_RIM_ALPHA * visibility)), position, blob_radius)
                pygame.draw.circle(layer, (*light, int(255 * visibility)), position, blob_radius, 1)
        
        # A ring of fluid splashes outward either way
        ring_radius = int(radius * (1.0 + 1.1 * progress))
        pygame.draw.circle(
            layer, (*light, int(200 * visibility * visibility)),
            (int(center[0]), int(center[1])), ring_radius, max(1, int(round(3 * visibility)))
        )
        screen.blit(layer, layer.get_rect(center=(int(self.x), int(self.y))))
