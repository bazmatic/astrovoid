"""Egg enemy that grows and spawns Baby enemies when it pops.

This module implements an Egg enemy that grows over time and spawns 1-3
Baby enemies when it reaches maximum size, or can be destroyed by bullets
to prevent spawning.

It is drawn as a jelly egg sac with the baby squid visible inside. The
embryos develop as the egg grows, so the sac shows both how many babies will
hatch and how soon.
"""

import pygame
import math
import random
from dataclasses import dataclass
from typing import Tuple, List, Optional, TYPE_CHECKING
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from utils import circle_line_collision, circle_circle_collision
from utils.math_utils import apply_circle_collision_physics, apply_wall_collision_physics
from rendering import visual_effects

if TYPE_CHECKING:
    from entities.baby import Baby
    from entities.command_recorder import CommandRecorder


@dataclass
class JellyBlob:
    """A lump of jelly flung from a burst egg."""
    x: float
    y: float
    vx: float
    vy: float
    radius: float


class Egg(GameEntity, Collidable, Drawable):
    """Egg enemy that grows and spawns Baby enemies when it pops.
    
    The egg grows at a random rate. When it reaches maximum size, it pops
    and spawns 1-3 Baby enemies. If destroyed by bullets before popping,
    no Baby enemies are spawned.
    
    Attributes:
        initial_radius: Starting size.
        current_radius: Current size (grows over time).
        max_radius: Maximum size before popping.
        growth_rate: Growth rate per frame.
        has_popped: Flag to track if egg has already popped.
        pulse_phase: Phase for pulsing animation.
        baby_count: Babies that will hatch, rolled when the egg is laid so the
            sac can show them.
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
    
    def __init__(self, pos: Tuple[float, float]):
        """
        Initialize egg enemy.
        
        Args:
            pos: Starting position as (x, y) tuple.
        """
        # Initialize with initial size
        initial_radius = config.EGG_INITIAL_SIZE
        super().__init__(pos, initial_radius, 0.0, 0.0)
        
        self.initial_radius = initial_radius
        self.current_radius = float(initial_radius)
        self.max_radius = config.EGG_MAX_SIZE
        # Random growth rate between min and max
        self.growth_rate = random.uniform(
            config.EGG_GROWTH_RATE_MIN,
            config.EGG_GROWTH_RATE_MAX
        )
        self.has_popped = False
        self.pulse_phase = 0.0
        self.baby_count = random.randint(config.EGG_BABY_SPAWN_MIN, config.EGG_BABY_SPAWN_MAX)
        self.wobble_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.jiggle = 0.0
        self.ending: Optional[str] = None
        self.blobs: List[JellyBlob] = []
        self._jiggle_angle = 0.0
        self._tear_angles = [random.uniform(0, 2 * math.pi) for _ in range(self.MAX_TEARS)]
        self._split_angle = random.uniform(0, math.pi)
        # Hit points for momentum system - calculated dynamically based on size
        # Start with initial hit points (should be 2 at initial size)
        self.max_hit_points = self._calculate_hit_points_from_size()
        self.hit_points = self.max_hit_points
    
    def update(self, dt: float) -> None:
        """Update egg growth, animation, and momentum physics.
        
        Args:
            dt: Delta time since last update.
        """
        if not self.active or self.has_popped:
            return
        
        # Apply friction and update position using shared method
        self.apply_friction_and_update_position(config.FRICTION_COEFFICIENT, dt)
        
        # Stop if velocity is too small
        if abs(self.vx) < config.MIN_VELOCITY_THRESHOLD:
            self.vx = 0.0
        if abs(self.vy) < config.MIN_VELOCITY_THRESHOLD:
            self.vy = 0.0
        
        # Grow the egg
        self.current_radius += self.growth_rate
        self.radius = self.current_radius
        
        # Recalculate hit points based on new size, preserving damage ratio
        old_max_hit_points = self.max_hit_points
        new_max_hit_points = self._calculate_hit_points_from_size()
        
        if old_max_hit_points > 0:
            # Preserve damage ratio when scaling up
            damage_ratio = self.hit_points / old_max_hit_points
            self.max_hit_points = new_max_hit_points
            self.hit_points = int(round(new_max_hit_points * damage_ratio))
            # Ensure hit_points doesn't exceed max_hit_points
            self.hit_points = min(self.hit_points, self.max_hit_points)
        else:
            # If somehow max_hit_points was 0, just set to new max
            self.max_hit_points = new_max_hit_points
            self.hit_points = new_max_hit_points
        
        # Update pulse phase for animation
        self.pulse_phase += dt * 2.0
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
        
        self.wobble_phase += dt * (self.WOBBLE_SPEED + self.URGENT_WOBBLE_SPEED * self.urgency)
        self.jiggle *= self.JIGGLE_DECAY ** dt
    
    @staticmethod
    def _progress(value: float, span: Tuple[float, float]) -> float:
        """How far value is through a (start, end) span, clamped to 0.0-1.0."""
        return max(0.0, min(1.0, (value - span[0]) / (span[1] - span[0])))
    
    @property
    def growth_progress(self) -> float:
        """Growth from 0.0 (just laid) to 1.0 (about to hatch)."""
        if self.max_radius <= self.initial_radius:
            return 1.0
        return self._progress(self.current_radius, (self.initial_radius, self.max_radius))
    
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
    
    def die(self) -> None:
        """End the egg: it splits open if it hatched, or bursts if it was shot."""
        super().die()
        self.ending = "hatched" if self.has_popped else "burst"
        if self.ending == "burst":
            for index in range(self.BLOB_COUNT):
                angle = 2 * math.pi * (index + random.uniform(-0.3, 0.3)) / self.BLOB_COUNT
                speed = random.uniform(1.0, 2.8)
                start = self.current_radius * random.uniform(0.3, 0.8)
                self.blobs.append(JellyBlob(
                    x=self.x + math.cos(angle) * start,
                    y=self.y + math.sin(angle) * start,
                    vx=self.vx + math.cos(angle) * speed,
                    vy=self.vy + math.sin(angle) * speed,
                    radius=self.current_radius * random.uniform(0.16, 0.32),
                ))
    
    def update_death(self, dt: float) -> None:
        """Advance the ending: the remains drift and the jelly flies apart."""
        super().update_death(dt)
        self.apply_friction_and_update_position(self.BLOB_FRICTION, dt)
        self.wobble_phase += dt * self.WOBBLE_SPEED
        for blob in self.blobs:
            blob.x += blob.vx * dt
            blob.y += blob.vy * dt
            blob.vx *= self.BLOB_FRICTION
            blob.vy *= self.BLOB_FRICTION
    
    def _calculate_hit_points_from_size(self) -> int:
        """Calculate max hit points based on current radius.
        
        Hit points scale linearly from 2 (at initial size) to 4 (at max size).
        
        Returns:
            Max hit points as integer, clamped between 2 and 4.
        """
        if self.max_radius <= self.initial_radius:
            return 2
        
        # Calculate growth progress (0.0 at initial, 1.0 at max)
        growth_progress = (self.current_radius - self.initial_radius) / (self.max_radius - self.initial_radius)
        growth_progress = max(0.0, min(1.0, growth_progress))
        
        # Scale from 2 to 4 hit points
        max_hit_points = 2 + growth_progress * 2
        
        return int(round(max_hit_points))
    
    def should_pop(self) -> bool:
        """Check if egg should pop (reached maximum size).
        
        Returns:
            True if egg has reached maximum size, False otherwise.
        """
        return self.current_radius >= self.max_radius and not self.has_popped
    
    def pop(self, command_recorder: 'CommandRecorder', babies: List['Baby']) -> None:
        """Pop the egg and spawn Baby enemies.
        
        Args:
            command_recorder: CommandRecorder instance for spawning Baby enemies.
            babies: List to add spawned Baby enemies to.
        """
        if self.has_popped:
            return
        
        self.has_popped = True
        
        for i in range(self.baby_count):
            # Random offset within spawn range
            angle_offset = random.uniform(0, 2 * math.pi)
            distance_offset = random.uniform(
                config.EGG_SPAWN_OFFSET_RANGE * 0.5,
                config.EGG_SPAWN_OFFSET_RANGE
            )
            spawn_x = self.x + math.cos(angle_offset) * distance_offset
            spawn_y = self.y + math.sin(angle_offset) * distance_offset
            
            # Create new Baby enemy
            from entities.baby import Baby
            spawned_baby = Baby((spawn_x, spawn_y), command_recorder)
            spawned_baby.current_replay_index = 0
            babies.append(spawned_baby)
        
        # The egg is gone; die() plays the sac splitting open
        self.die()
    
    def take_damage(self) -> bool:
        """Take damage from a projectile hit.
        
        Returns:
            True if egg is destroyed, False otherwise.
        """
        self.hit_points -= 1
        self.jiggle = 1.0
        self._jiggle_angle = random.uniform(0, math.pi)
        return self.hit_points <= 0
    
    def apply_momentum(self, vx: float, vy: float) -> None:
        """Apply momentum from a projectile impact.
        
        Args:
            vx: X component of velocity to add.
            vy: Y component of velocity to add.
        """
        self.vx += vx
        self.vy += vy
    
    def check_wall_collision(
        self,
        walls: List,
        spatial_grid=None
    ) -> bool:
        """Check collision with walls and bounce if moving.
        
        Args:
            walls: List of wall segments.
            spatial_grid: Optional spatial grid for optimized collision detection.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        # Only check collisions if moving
        if abs(self.vx) < config.MIN_VELOCITY_THRESHOLD and abs(self.vy) < config.MIN_VELOCITY_THRESHOLD:
            return False
        
        # Use spatial grid if available, otherwise check all walls
        walls_to_check = walls
        if spatial_grid is not None:
            walls_to_check = spatial_grid.get_nearby_walls(
                (self.x, self.y), self.radius * 2.0
            )
        
        for wall in walls_to_check:
            # Handle both WallSegment and tuple formats
            if hasattr(wall, 'get_segment'):
                # WallSegment instance
                if not wall.active:
                    continue
                segment = wall.get_segment()
            else:
                # Tuple format (backward compatibility)
                segment = wall
            
            if circle_line_collision(
                (self.x, self.y), self.radius,
                segment[0], segment[1]
            ):
                # Calculate wall direction vector
                wall_start, wall_end = segment
                wall_dx = wall_end[0] - wall_start[0]
                wall_dy = wall_end[1] - wall_start[1]
                wall_length = math.sqrt(wall_dx * wall_dx + wall_dy * wall_dy)
                
                if wall_length > 0:
                    # Normalize wall direction
                    wall_nx = wall_dx / wall_length
                    wall_ny = wall_dy / wall_length
                    
                    # Calculate normal (perpendicular to wall, pointing away from wall)
                    # Choose normal that points away from entity center
                    normal_x = -wall_ny
                    normal_y = wall_nx
                    
                    # Check which side of wall entity is on, flip normal if needed
                    # Vector from wall start to entity
                    to_entity_x = self.x - wall_start[0]
                    to_entity_y = self.y - wall_start[1]
                    # Dot product with normal
                    dot_normal = to_entity_x * normal_x + to_entity_y * normal_y
                    if dot_normal < 0:
                        # Entity is on other side, flip normal
                        normal_x = -normal_x
                        normal_y = -normal_y
                    
                    # Reflect velocity using physics
                    apply_wall_collision_physics(self, (normal_x, normal_y), config.COLLISION_RESTITUTION)
                    
                    # Move entity away from wall to prevent overlap
                    overlap_distance = self.radius + 1.0  # Small buffer
                    self.x += normal_x * overlap_distance
                    self.y += normal_y * overlap_distance
                
                return True
        
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float,
        other_entity: Optional['GameEntity'] = None
    ) -> bool:
        """Check collision with another circular entity.
        
        Uses proper elastic collision physics when other_entity is provided,
        otherwise falls back to simple collision detection for backward compatibility.
        
        Args:
            other_pos: Position of the other entity (x, y).
            other_radius: Radius of the other entity.
            other_entity: Optional GameEntity object. If provided, both objects'
                         velocities will be updated using conservation of momentum.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        if not circle_circle_collision(
            self.get_pos(), self.radius,
            other_pos, other_radius
        ):
            return False
        
        if other_entity is not None:
            # Use proper physics with conservation of momentum
            apply_circle_collision_physics(self, other_entity, config.COLLISION_RESTITUTION)
        
        return True
    
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
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the egg as a jelly sac with the baby squid visible inside.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
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
    
    def draw_death(self, screen: pygame.Surface) -> None:
        """Draw the egg's ending: the sac splitting open, or bursting into blobs.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.is_dying:
            return
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
