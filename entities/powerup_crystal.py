"""Powerup crystal entity implementation.

This module implements the PowerupCrystal class for collectible powerup items
that drop from destroyed enemies.
"""

import pygame
import math
import random
from typing import List, Tuple, Optional
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from rendering import visual_effects
from utils import circle_circle_collision


class PowerupCrystal(GameEntity, Collidable, Drawable):
    """Represents a collectible powerup crystal that upgrades the player's guns.
    
    It is drawn as a cut gem turning on its vertical axis: a hard, geometric
    shape that stands apart from the creatures and reads as safe to grab.
    
    Attributes:
        rotation_angle: Current rotation angle in degrees.
        pulse_phase: Phase for pulsing animation (in radians).
        age: Frames since the crystal was dropped.
        trail: Recent positions, kept while it is being pulled to the player.
        motes: Number of bright motes orbiting it.
        sparks: Sparks from the burst when collected, as (x, y, vx, vy).
    """
    
    # Drawing constants (lengths are multiples of the radius)
    GEM_HALF_WIDTH = 0.85
    GEM_SHOULDER = 0.45  # Half-height of the straight sides
    GEM_HALF_HEIGHT = 1.35  # Centre to the top and bottom points
    GEM_SIDES = 6  # Faces round the gem; half are visible at once
    LIGHT_ANGLE = -35.0  # Degrees - where the light sits as the gem turns
    SHADOW_COLOR = (10, 80, 40)
    HIGHLIGHT_COLOR = (225, 255, 225)
    BOB_HEIGHT = 1.5  # Pixels
    SPAWN_FRAMES = 14.0  # Frames to pop into view
    SPAWN_OVERSHOOT = 1.35  # Above 1.0 it swells past full size before settling
    GLINT_PERIOD = 70.0  # Frames between glints
    GLINT_FRAMES = 14.0
    MOTE_COUNT = 3
    MOTE_ORBIT = (1.9, 0.75)  # Orbit radius across and down; flattened to look tilted
    TRAIL_LENGTH = 8
    # Collect burst
    DEATH_DURATION = 18.0  # Frames (0.3 seconds at 60 FPS)
    SPARK_COUNT = 8
    SPARK_FRICTION = 0.88
    
    def __init__(self, pos: Tuple[float, float]):
        """Initialize powerup crystal at position.
        
        Args:
            pos: Starting position as (x, y) tuple.
        """
        super().__init__(pos, config.POWERUP_CRYSTAL_SIZE)
        self.rotation_angle = random.uniform(0.0, 360.0)
        self.pulse_phase = random.uniform(0.0, 2 * math.pi)
        self.age = 0.0
        self.trail: List[Tuple[float, float]] = []
        self.motes = self.MOTE_COUNT
        self.sparks: List[Tuple[float, float, float, float]] = []
    
    @property
    def spawn_scale(self) -> float:
        """Size relative to normal while popping into view: 0.0, a swell past 1.0, then 1.0."""
        if self.age >= self.SPAWN_FRAMES:
            return 1.0
        swing = math.pi / 2 * self.SPAWN_OVERSHOOT
        return math.sin(self.age / self.SPAWN_FRAMES * swing) / math.sin(swing)
    
    def visible_faces(self) -> List[Tuple[float, float, float]]:
        """The gem's faces that currently point at the viewer.
        
        The gem is a six-sided prism turning on its vertical axis, so its
        faces slide across from one edge to the other.
        
        Returns:
            (left, right, brightness) for each face: its horizontal extent in
            multiples of the radius, and how much light it catches (0.0 to 1.0).
        """
        faces = []
        step = 360.0 / self.GEM_SIDES
        for side in range(self.GEM_SIDES):
            start = (self.rotation_angle + side * step + 180.0) % 360.0 - 180.0
            # Only the part of the face on the near half of the gem shows
            near_start = max(start, -90.0)
            near_end = min(start + step, 90.0)
            if near_end - near_start < 1e-9:
                continue
            facing = math.cos(math.radians(start + step / 2 - self.LIGHT_ANGLE))
            faces.append((
                self.GEM_HALF_WIDTH * math.sin(math.radians(near_start)),
                self.GEM_HALF_WIDTH * math.sin(math.radians(near_end)),
                0.3 + 0.7 * max(0.0, facing),
            ))
        return faces
    
    def die(self) -> None:
        """Collect the crystal: it bursts into a ring and a spray of sparks."""
        super().die()
        for index in range(self.SPARK_COUNT):
            angle = 2 * math.pi * (index + random.uniform(-0.3, 0.3)) / self.SPARK_COUNT
            speed = random.uniform(2.5, 4.5)
            self.sparks.append((self.x, self.y, math.cos(angle) * speed, math.sin(angle) * speed))
    
    def update_death(self, dt: float) -> None:
        """Advance the collect burst."""
        super().update_death(dt)
        self.sparks = [
            (x + vx * dt, y + vy * dt, vx * self.SPARK_FRICTION, vy * self.SPARK_FRICTION)
            for x, y, vx, vy in self.sparks
        ]
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update crystal rotation, animation, and movement towards player.
        
        Args:
            dt: Delta time since last update.
            player_pos: Optional player position (x, y) for attraction behavior.
        """
        if not self.active:
            return
        
        # Check if player is within attraction radius and move towards player
        if player_pos is not None:
            dx = player_pos[0] - self.x
            dy = player_pos[1] - self.y
            distance = math.sqrt(dx * dx + dy * dy)
            
            if distance <= config.POWERUP_CRYSTAL_ATTRACTION_RADIUS and distance > 0:
                # Normalize direction vector
                dir_x = dx / distance
                dir_y = dy / distance
                
                # Apply attraction velocity towards player
                self.vx = dir_x * config.POWERUP_CRYSTAL_ATTRACTION_SPEED
                self.vy = dir_y * config.POWERUP_CRYSTAL_ATTRACTION_SPEED
            else:
                # Stop moving if outside attraction radius
                self.vx = 0.0
                self.vy = 0.0
        
        # Update position based on velocity
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        self.age += dt
        # Leave a trail while being pulled in; let it run out once at rest
        if self.vx != 0.0 or self.vy != 0.0:
            self.trail.append((self.x, self.y))
            del self.trail[:-self.TRAIL_LENGTH]
        elif self.trail:
            del self.trail[0]
        
        # Rotate crystal
        self.rotation_angle += config.POWERUP_CRYSTAL_ROTATION_SPEED * dt
        if self.rotation_angle >= 360.0:
            self.rotation_angle -= 360.0
        
        # Update pulse animation
        self.pulse_phase += 0.1 * dt
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
    def check_wall_collision(self, walls: list, spatial_grid=None) -> bool:
        """Check collision with walls (crystals don't collide with walls).
        
        Args:
            walls: List of wall segments (unused).
            spatial_grid: Optional spatial grid (unused).
            
        Returns:
            Always False (crystals don't collide with walls).
        """
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float
    ) -> bool:
        """Check collision with another circular entity (ship).
        
        Args:
            other_pos: Position of the other entity (x, y).
            other_radius: Radius of the other entity.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        if circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        ):
            self.die()
            return True
        return False
    
    def _draw_gem(self, target: pygame.Surface, center: Tuple[float, float], size: float) -> None:
        """Draw the faceted gem with its centre at center; size is the pixel length of one unit."""
        base = config.COLOR_POWERUP_CRYSTAL
        
        def shade(brightness: float) -> Tuple[int, int, int]:
            brightness = max(0.0, min(1.0, brightness))
            if brightness < 0.6:
                return visual_effects.interpolate_color(self.SHADOW_COLOR, base, brightness / 0.6)
            return visual_effects.interpolate_color(base, self.HIGHLIGHT_COLOR, (brightness - 0.6) / 0.4)
        
        def place(x: float, y: float) -> Tuple[float, float]:
            return (center[0] + x * size, center[1] + y * size)
        
        top, bottom = place(0.0, -self.GEM_HALF_HEIGHT), place(0.0, self.GEM_HALF_HEIGHT)
        for left, right, brightness in self.visible_faces():
            upper_left, upper_right = place(left, -self.GEM_SHOULDER), place(right, -self.GEM_SHOULDER)
            lower_left, lower_right = place(left, self.GEM_SHOULDER), place(right, self.GEM_SHOULDER)
            pygame.draw.polygon(target, shade(brightness), [upper_left, upper_right, lower_right, lower_left])
            # The crown catches more light than the body, the base less
            pygame.draw.polygon(target, shade(brightness + 0.2), [upper_left, upper_right, top])
            pygame.draw.polygon(target, shade(brightness - 0.25), [lower_left, lower_right, bottom])
            pygame.draw.line(target, shade(brightness + 0.35), upper_left, lower_left, 1)
        
        outline = [
            top, place(self.GEM_HALF_WIDTH, -self.GEM_SHOULDER), place(self.GEM_HALF_WIDTH, self.GEM_SHOULDER),
            bottom, place(-self.GEM_HALF_WIDTH, self.GEM_SHOULDER), place(-self.GEM_HALF_WIDTH, -self.GEM_SHOULDER),
        ]
        pygame.draw.aalines(target, self.HIGHLIGHT_COLOR, True, outline)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the crystal as a turning gem with a halo, glints and orbiting motes.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        scale = self.spawn_scale
        if scale <= 0.0:
            return
        
        base = config.COLOR_POWERUP_CRYSTAL
        size = self.radius * scale * (1.0 + 0.06 * math.sin(self.pulse_phase))
        center = (self.x, self.y + math.sin(self.pulse_phase * 0.7) * self.BOB_HEIGHT)
        
        # Sparkling trail left while it is pulled to the player
        for index, (trail_x, trail_y) in enumerate(self.trail[:-1]):
            strength = (index + 1) / len(self.trail)
            color = visual_effects.interpolate_color(self.SHADOW_COLOR, self.HIGHLIGHT_COLOR, strength * 0.8)
            pygame.draw.circle(screen, color, (int(trail_x), int(trail_y)), max(1, int(round(self.radius * 0.35 * strength))))
        
        # Stepped alpha keeps the glow cache small
        glow_alpha = int(85 + 35 * math.sin(self.pulse_phase * 2.0)) // 10 * 10
        glow = visual_effects.create_soft_glow_surface(self.radius * 3.2, base, glow_alpha)
        screen.blit(glow, glow.get_rect(center=(int(center[0]), int(center[1]))))
        
        # A ring of light as it pops into view
        if self.age < self.SPAWN_FRAMES:
            arrival = self.age / self.SPAWN_FRAMES
            pygame.draw.circle(
                screen, visual_effects.interpolate_color(self.HIGHLIGHT_COLOR, self.SHADOW_COLOR, arrival),
                (int(center[0]), int(center[1])), int(self.radius * (1.0 + 2.5 * arrival)), 1
            )
        
        # Motes circle the gem, passing behind it and then in front
        mote_positions = []
        for mote in range(self.motes):
            angle = self.pulse_phase * 1.3 + mote * 2 * math.pi / max(1, self.motes)
            mote_positions.append((
                center[0] + math.cos(angle) * self.MOTE_ORBIT[0] * size,
                center[1] + math.sin(angle) * self.MOTE_ORBIT[1] * size,
                math.sin(angle) > 0.0,
            ))
        for mote_x, mote_y, in_front in mote_positions:
            if not in_front:
                screen.set_at((int(mote_x), int(mote_y)), base)
        
        self._draw_gem(screen, center, size)
        
        for mote_x, mote_y, in_front in mote_positions:
            if in_front:
                pygame.draw.circle(screen, self.HIGHLIGHT_COLOR, (int(mote_x), int(mote_y)), 1)
        
        # A four-point glint flares on the shoulder now and then
        into_cycle = self.age % self.GLINT_PERIOD - (self.GLINT_PERIOD - self.GLINT_FRAMES)
        if into_cycle > 0.0:
            flare = math.sin(math.pi * into_cycle / self.GLINT_FRAMES)
            glint_x = center[0] - self.GEM_HALF_WIDTH * size
            glint_y = center[1] - self.GEM_SHOULDER * size
            reach = self.radius * 1.5 * flare
            pygame.draw.line(screen, (255, 255, 255), (glint_x - reach, glint_y), (glint_x + reach, glint_y), 1)
            pygame.draw.line(screen, (255, 255, 255), (glint_x, glint_y - reach), (glint_x, glint_y + reach), 1)
    
    def draw_death(self, screen: pygame.Surface) -> None:
        """Draw the collect burst: a flash, an expanding ring and flying sparks.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.is_dying:
            return
        progress = self.death_progress
        visibility = 1.0 - progress
        base = config.COLOR_POWERUP_CRYSTAL
        # Drawn off-screen so the burst can fade
        size = int(self.radius * 14)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        middle = size / 2
        
        ring_color = visual_effects.interpolate_color((255, 255, 255), base, progress)
        pygame.draw.circle(
            layer, (*ring_color, int(255 * visibility)), (int(middle), int(middle)),
            int(self.radius * (1.0 + 3.5 * progress)), max(1, int(round(3 * visibility)))
        )
        # The gem itself flares white and shrinks away
        if progress < 0.4:
            flash_radius = self.radius * 1.4 * (1.0 - progress / 0.4)
            pygame.draw.circle(layer, (255, 255, 255, 255), (int(middle), int(middle)), max(1, int(flash_radius)))
        for x, y, vx, vy in self.sparks:
            head = (middle + x - self.x, middle + y - self.y)
            tail = (head[0] - vx * 2.5, head[1] - vy * 2.5)
            pygame.draw.line(layer, (*self.HIGHLIGHT_COLOR, int(255 * visibility)), tail, head, 1)
        
        screen.blit(layer, layer.get_rect(center=(int(self.x), int(self.y))))
