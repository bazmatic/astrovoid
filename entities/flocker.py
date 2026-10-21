"""The Flocker's Body: a swallow, with sickle-moon wings that curve back, a straight tail, a streamlined body, darker
on top and lighter underneath. Its wings flap as it flies; when it dies they fold and the bird tumbles away, shrinking
to nothing."""

import math
from typing import Tuple

import pygame

import config
from utils import angle_to_radians


class FlockerBody:
    """The look of a Flocker.

    Attributes:
        wing_phase: Phase of the wing flap.
    """

    DEATH_DURATION = 48.0  # Frames: wings fold, then the bird tumbles away
    DEATH_FRICTION = 0.94
    WING_SPEED = 3.0       # Wing flap, radians per frame

    def __init__(self, creature):
        self._creature = creature
        self.wing_phase: float = 0.0

    x = property(lambda self: self._creature.x)
    y = property(lambda self: self._creature.y)
    radius = property(lambda self: self._creature.radius)
    angle = property(lambda self: self._creature.angle)

    def on_event(self, creature, name: str) -> None:
        """Its look follows its heading, so events change nothing."""

    def update(self, creature, dt: float, target=None) -> None:
        """The wings flap."""
        self.wing_phase += dt * self.WING_SPEED

    def update_death(self, creature, dt: float) -> None:
        """The wings stop; the remains coast to a stop (the Creature moves them)."""

    def draw(self, screen: pygame.Surface, creature) -> None:
        """Draw the swallow in flight."""
        self._draw_bird(screen)

    def draw_death(self, screen: pygame.Surface, creature) -> None:
        """Fold the wings and tumble into a shrinking silhouette."""
        self._draw_bird(screen, creature.death_progress)

    def _draw_bird(self, screen: pygame.Surface, death_progress: float = 0.0) -> None:
        """Draw the same bird geometry in its flying or folded pose."""
        progress = death_progress
        fold = min(1.0, progress / 0.45)
        fold = fold * fold * (3.0 - 2.0 * fold)
        radius = self.radius * (1.0 - progress ** 2)
        if radius < 1.0:
            return
        angle = self.angle + 240.0 * progress ** 1.5
        angle_rad = angle_to_radians(angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        base_color = config.FLOCKER_ENEMY_COLOR
        darker_color = tuple(max(0, c - 40) for c in base_color)
        body_radius = radius * 0.5
        
        # Draw glow effect
        from rendering import visual_effects
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, base_color,
            glow_radius=body_radius * 0.3, intensity=0.2
        )
        
        # Calculate wing animation (subtle flapping)
        wing_angle_offset = math.sin(self.wing_phase) * 3.0 * (1.0 - fold)  # 3 degree wing movement
        
        # Draw body (small oval shape, streamlined)
        body_length = radius * 0.8
        body_width = radius * 0.5
        
        # Create surface for rotated body
        surface_size = int(max(body_length, body_width) * 2) + 4
        body_surface = pygame.Surface((surface_size, surface_size), pygame.SRCALPHA)
        surface_center = surface_size // 2
        
        # Draw body oval
        body_rect = pygame.Rect(
            surface_center - int(body_length // 2),
            surface_center - int(body_width // 2),
            int(body_length),
            int(body_width)
        )
        pygame.draw.ellipse(body_surface, base_color, body_rect)
        
        # Draw darker top (for swallow appearance)
        top_rect = pygame.Rect(
            surface_center - int(body_length // 2),
            surface_center - int(body_width // 2),
            int(body_length),
            int(body_width // 2)
        )
        pygame.draw.ellipse(body_surface, darker_color, top_rect)
        
        # Rotate and blit body
        rotated_body = pygame.transform.rotate(body_surface, -angle)
        body_rect = rotated_body.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_body, body_rect)
        
        # Draw sickle-moon-like, backwards-curving wings
        wing_span = radius * 1.4  # Wing span
        wing_curve_radius = radius * 1.2  # Radius of the curved wing
        wing_base_offset = radius * 0.2  # How far forward the wing attaches
        
        # Wing attachment point on body
        wing_attach_x = self.x + math.cos(angle_rad) * wing_base_offset
        wing_attach_y = self.y + math.sin(angle_rad) * wing_base_offset
        
        # Create curved wing shape (sickle-moon)
        # Left wing - curves backward and upward
        left_wing_points = []
        num_points = 20
        for i in range(num_points + 1):
            # Progress along the curve (0.0 to 1.0)
            t = i / num_points
            
            # Angle starts perpendicular to body, curves backward
            # Start angle: 90 degrees from body direction
            # End angle: curves backward (more than 90 degrees)
            start_angle = angle_rad + math.radians(90 + 80 * fold + wing_angle_offset)
            end_angle = angle_rad + math.radians(135 + 40 * fold + wing_angle_offset)  # Curves backward
            
            # Interpolate angle
            wing_angle = start_angle + (end_angle - start_angle) * t
            
            # Distance from attachment point increases along curve
            # Creates the curved sickle shape
            distance = wing_curve_radius * (0.3 + 0.7 * t)  # Starts closer, extends further
            
            point_x = wing_attach_x + math.cos(wing_angle) * distance
            point_y = wing_attach_y + math.sin(wing_angle) * distance
            left_wing_points.append((int(point_x), int(point_y)))
        
        # Close the wing shape by adding attachment point
        left_wing_points.append((int(wing_attach_x), int(wing_attach_y)))
        
        # Right wing - curves backward and downward
        right_wing_points = []
        for i in range(num_points + 1):
            t = i / num_points
            
            # Start angle: -90 degrees from body direction
            # End angle: curves backward (more than -90 degrees)
            start_angle = angle_rad - math.radians(90 + 80 * fold - wing_angle_offset)
            end_angle = angle_rad - math.radians(135 + 40 * fold - wing_angle_offset)  # Curves backward
            
            wing_angle = start_angle + (end_angle - start_angle) * t
            distance = wing_curve_radius * (0.3 + 0.7 * t)
            
            point_x = wing_attach_x + math.cos(wing_angle) * distance
            point_y = wing_attach_y + math.sin(wing_angle) * distance
            right_wing_points.append((int(point_x), int(point_y)))
        
        right_wing_points.append((int(wing_attach_x), int(wing_attach_y)))
        
        # Draw wings
        if len(left_wing_points) > 2:
            pygame.draw.polygon(screen, darker_color, left_wing_points)
        if len(right_wing_points) > 2:
            pygame.draw.polygon(screen, darker_color, right_wing_points)
        
        # Draw straight tail extending backward
        tail_length = radius * 0.9
        tail_width = radius * 0.15
        
        # Tail base (at rear of body)
        tail_base_x = self.x - math.cos(angle_rad) * body_radius * 0.6
        tail_base_y = self.y - math.sin(angle_rad) * body_radius * 0.6
        
        # Tail tip (straight backward)
        tail_tip_x = self.x - math.cos(angle_rad) * (body_radius * 0.6 + tail_length)
        tail_tip_y = self.y - math.sin(angle_rad) * (body_radius * 0.6 + tail_length)
        
        # Perpendicular vector for tail width
        perp_angle = angle_rad + math.pi / 2
        perp_x = math.cos(perp_angle) * tail_width / 2
        perp_y = math.sin(perp_angle) * tail_width / 2
        
        # Draw tail as rectangle
        tail_points = [
            (int(tail_base_x + perp_x), int(tail_base_y + perp_y)),
            (int(tail_base_x - perp_x), int(tail_base_y - perp_y)),
            (int(tail_tip_x - perp_x), int(tail_tip_y - perp_y)),
            (int(tail_tip_x + perp_x), int(tail_tip_y + perp_y))
        ]
        pygame.draw.polygon(screen, base_color, tail_points)
