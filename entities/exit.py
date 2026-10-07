"""Exit portal entity implementation.

This module implements the ExitPortal class for the maze exit portal that the player
must reach to complete a level.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from rendering import visual_effects
from utils import circle_circle_collision, distance


class ExitPortal(GameEntity, Collidable, Drawable):
    """Represents the maze exit portal, drawn as a whirlpool.
    
    The exit portal is a stationary object that the player must reach to complete a level.
    Bands of water spiral into a dark mouth and specks are drawn in from the
    edge of its pull, so the pull is visible before it is felt. While locked
    (eggs or a boss remain) it slows, dims and its mouth irises shut.
    
    Attributes:
        base_radius: Base radius of the exit portal (used for collision and display).
        animation_time: Internal time counter for animations.
        player_nearby: Whether the player is within attraction radius.
        activation: 0.0 locked shut, 1.0 fully open. Eases between the two.
        nearness: 0.0 player far away, 1.0 player within the pull. Eases too.
        spin: Rotation of the whirlpool in radians.
        unlock_ripple: 1.0 the moment the portal unlocks, fading to 0.0.
        specks: Specks being drawn in, each as [angle in radians, distance
            from 1.0 at the edge of their range to 0.0 at the mouth].
    """
    
    OPEN_SECONDS = 0.5  # Time to ease fully open or shut
    NEAR_SECONDS = 0.4  # Time to react to the player arriving or leaving
    SPIN_SPEED_LOCKED = 0.6  # Radians per second
    SPIN_SPEED_OPEN = 3.2  # Extra spin when open
    SPIN_SPEED_NEAR = 3.0  # Extra spin when the player is near
    NEAR_GROWTH = 0.2  # How much the whirlpool widens when the player is near
    MOUTH_RADIUS = 0.2  # Mouth size as a multiple of the radius
    MOUTH_NEAR_GROWTH = 0.14
    EDGE_ALPHA = 45  # Water at the rim is nearly clear ...
    CORE_ALPHA = 240  # ... and thickens to almost solid by the mouth
    CORE_REACH = 0.4  # Share of the radius that is fully thick
    WATER_RINGS = 10  # Steps in the fade between the two
    RIM_ALPHA = 150
    ARM_COUNT = 3
    ARM_POINTS = 12
    SPECK_COUNT = 22
    SPECK_REACH = 0.5  # Where specks appear, as a share of the attraction radius
    SPECK_FALL_SPEED = (0.25, 1.1)  # Inward speed at the edge, plus extra gained by the mouth
    SPECK_ORBIT_SPEED = (1.2, 4.5)  # Radians per second at the edge, plus extra by the mouth
    RIPPLE_SECONDS = 2.4  # Time between ripples leaving the rim
    UNLOCK_RIPPLE_SECONDS = 0.8
    LOCKED_COLOR = (45, 75, 60)
    DEPTH_COLOR = (0, 12, 8)
    
    def __init__(self, pos: Tuple[float, float], radius: float):
        """Initialize exit at position.
        
        Args:
            pos: Starting position as (x, y) tuple.
            radius: Base radius of the exit.
        """
        super().__init__(pos, radius)
        self.base_radius = radius
        self.animation_time = 0.0
        self.player_nearby = False
        self.is_activated = True  # Portal is active by default
        self.previous_activated = True  # Track previous state to detect changes
        self.activation = 1.0
        self.nearness = 0.0
        self.spin = 0.0
        self.unlock_ripple = 0.0
        self.specks: List[List[float]] = [
            [random.uniform(0, 2 * math.pi), random.uniform(0.1, 1.0)] for _ in range(self.SPECK_COUNT)
        ]
        self._was_open = True
    
    @property
    def mouth_radius(self) -> float:
        """Radius in pixels of the dark mouth; zero when the portal is locked shut."""
        return self.base_radius * (self.MOUTH_RADIUS + self.MOUTH_NEAR_GROWTH * self.nearness) * self.activation
    
    def speck_distance(self, speck: List[float]) -> float:
        """Distance in pixels of a speck from the centre of the portal."""
        inner = self.base_radius * self.MOUTH_RADIUS
        outer = max(self.base_radius * 2.0, config.EXIT_PORTAL_ATTRACTION_RADIUS * self.SPECK_REACH)
        return inner + (outer - inner) * speck[1]
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update exit animation state and check player proximity.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
            player_pos: Optional player position (x, y) to check attraction radius.
        """
        if not self.active:
            return
        
        # Update animation time (convert dt to seconds)
        dt_seconds = dt / 60.0
        self.animation_time += dt_seconds
        
        # Check if player is within attraction radius
        if player_pos is not None:
            dist = distance((self.x, self.y), player_pos)
            self.player_nearby = dist <= config.EXIT_PORTAL_ATTRACTION_RADIUS
        else:
            self.player_nearby = False
        
        # Ease open or shut, and towards or away from the excited state
        step = dt_seconds / self.OPEN_SECONDS
        if self.is_activated:
            if not self._was_open:
                self.unlock_ripple = 1.0
            else:
                self.unlock_ripple = max(0.0, self.unlock_ripple - dt_seconds / self.UNLOCK_RIPPLE_SECONDS)
            self.activation = min(1.0, self.activation + step)
        else:
            self.unlock_ripple = 0.0
            self.activation = max(0.0, self.activation - step)
        self._was_open = self.is_activated
        
        step = dt_seconds / self.NEAR_SECONDS
        if self.player_nearby and self.is_activated:
            self.nearness = min(1.0, self.nearness + step)
        else:
            self.nearness = max(0.0, self.nearness - step)
        
        self.spin += dt_seconds * (
            self.SPIN_SPEED_LOCKED + self.SPIN_SPEED_OPEN * self.activation + self.SPIN_SPEED_NEAR * self.nearness
        )
        
        # Specks circle inward, faster the closer they get; a locked portal holds them still
        pull = dt_seconds * self.activation
        for speck in self.specks:
            closeness = 1.0 - speck[1]
            speck[0] += pull * (self.SPECK_ORBIT_SPEED[0] + self.SPECK_ORBIT_SPEED[1] * closeness)
            speck[1] -= pull * (self.SPECK_FALL_SPEED[0] + self.SPECK_FALL_SPEED[1] * closeness)
            if speck[1] < 0.05:
                speck[0] = random.uniform(0, 2 * math.pi)
                speck[1] = random.uniform(0.85, 1.0)
    
    def check_wall_collision(self, walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> bool:
        """Check collision with walls (exit doesn't collide with walls).
        
        Args:
            walls: List of wall line segments, each as ((x1, y1), (x2, y2)).
            
        Returns:
            Always False (exit doesn't collide with walls).
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
        # Portal doesn't work when not activated (eggs still present)
        if not self.is_activated:
            return False
        
        return circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        )
    
    def get_attraction_force(
        self,
        player_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Get attraction force vector towards the portal.
        
        Args:
            player_pos: Player position (x, y).
            
        Returns:
            Force vector (fx, fy) if player is within attraction radius, None otherwise.
        """
        if not self.active or not self.is_activated:
            return None
        
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dist = math.sqrt(dx * dx + dy * dy)
        
        if dist > config.EXIT_PORTAL_ATTRACTION_RADIUS or dist == 0:
            return None
        
        # Normalize direction and apply force
        dir_x = dx / dist
        dir_y = dy / dist
        
        # Force strength is 0.5 of ship thruster force, decreases with distance (stronger when closer)
        base_force = config.SHIP_THRUST_FORCE * config.EXIT_PORTAL_ATTRACTION_FORCE_MULTIPLIER
        force_strength = base_force * (1.0 - dist / config.EXIT_PORTAL_ATTRACTION_RADIUS)
        
        return (dir_x * force_strength, dir_y * force_strength)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the exit as a whirlpool.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        activation = self.activation
        base = visual_effects.interpolate_color(self.LOCKED_COLOR, config.COLOR_EXIT, activation)
        bright = visual_effects.interpolate_color(base, (255, 255, 255), 0.55)
        deep = visual_effects.interpolate_color(base, self.DEPTH_COLOR, 0.85)
        outer = self.base_radius * (1.0 + self.NEAR_GROWTH * self.nearness)
        screen_center = (int(self.x), int(self.y))
        
        # Stepped alpha keeps the glow cache small
        glow_alpha = int(40 + 50 * activation + 30 * self.nearness) // 10 * 10
        glow_radius = self.base_radius * (1.6 + 0.3 * config.EXIT_PORTAL_GLOW_MULTIPLIER)
        glow = visual_effects.create_soft_glow_surface(glow_radius, config.COLOR_EXIT, glow_alpha)
        screen.blit(glow, glow.get_rect(center=screen_center))
        
        # Drawn on its own layer so specks and ripples can fade
        reach = max(outer * 2.7, self.speck_distance([0.0, 1.0])) + 4
        size = int(reach * 2)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        middle = size // 2
        center = (middle, middle)
        
        def at(angle: float, distance_px: float) -> Tuple[float, float]:
            return (middle + math.cos(angle) * distance_px, middle + math.sin(angle) * distance_px)
        
        # Specks brighten as they are drawn in, each with a short tail
        if activation > 0.0:
            for angle, edge in self.specks:
                strength = (1.0 - edge) ** 0.6 * activation
                if strength <= 0.02:
                    continue
                distance_px = self.speck_distance([angle, edge])
                color = (*bright, int(230 * strength))
                head = at(angle, distance_px)
                pygame.draw.line(layer, color, at(angle - 0.22, distance_px + 2), head, 1)
                pygame.draw.circle(layer, color, (int(head[0]), int(head[1])), 2 if edge < 0.35 else 1)
        
        # A ripple leaves the rim now and then, and a strong one when it unlocks.
        # Drawn first so it passes under the whirlpool instead of over its rim
        ripple = (self.animation_time % self.RIPPLE_SECONDS) / self.RIPPLE_SECONDS
        ripple_alpha = int(90 * (1.0 - ripple) * activation)
        if ripple_alpha > 0:
            pygame.draw.circle(layer, (*base, ripple_alpha), center, int(outer * (1.0 + 0.6 * ripple)), 1)
        if self.unlock_ripple > 0.0:
            pygame.draw.circle(
                layer, (*bright, int(230 * self.unlock_ripple)), center,
                int(outer * (1.0 + 1.6 * (1.0 - self.unlock_ripple))), 3
            )
        
        # Water thickens from a clear edge to a dark core, so whatever is
        # behind the outer whirlpool shows through
        for ring in range(self.WATER_RINGS + 1):
            depth = ring / self.WATER_RINGS
            ring_radius = outer * (1.0 - (1.0 - self.CORE_REACH) * depth)
            alpha = int(self.EDGE_ALPHA + (self.CORE_ALPHA - self.EDGE_ALPHA) * depth ** 1.5)
            pygame.draw.circle(layer, (*deep, alpha), center, int(ring_radius))
        
        # Two layers of spiral bands; the inner one turns faster, which gives the depth
        mouth = self.mouth_radius
        bands = (
            (0.88, 0.5, 0.5, 1.0, base, 3.0, 70),  # Starts inside the rim so thick lines never poke past it
            (0.62, max(mouth / outer, 0.08), 0.7, 1.9, bright, 2.0, 200),
        )
        for start, end, turns, speed, color, width, edge_alpha in bands:
            for arm in range(self.ARM_COUNT):
                points = []
                for step in range(self.ARM_POINTS + 1):
                    t = step / self.ARM_POINTS
                    angle = self.spin * speed + arm * 2 * math.pi / self.ARM_COUNT + t * turns * 2 * math.pi
                    points.append(at(angle, outer * (start + (end - start) * t)))
                for step in range(self.ARM_POINTS):
                    t = step / self.ARM_POINTS
                    # Bands thin out and sink into the dark as they near the mouth
                    shade = visual_effects.interpolate_color(color, deep, t * 0.75)
                    # ... and are faint at their outer end, solid further in
                    alpha = int(edge_alpha + (255 - edge_alpha) * min(1.0, t * 1.6))
                    pygame.draw.line(
                        layer, (*shade, alpha), points[step], points[step + 1],
                        max(1, int(round(width * (1.0 - 0.6 * t))))
                    )
        
        if mouth >= 1.0:
            pygame.draw.circle(layer, (*self.DEPTH_COLOR, 255), center, int(mouth))
            pygame.draw.circle(layer, (*base, 255), center, int(mouth), 1)
        
        # The iris that closes over the mouth while the portal is locked
        shut = 1.0 - activation
        if shut > 0.0:
            lid_alpha = int(235 * shut)
            lid_turn = activation * math.pi / 3
            lid = [at(lid_turn + blade * math.pi / 3, outer * 0.6) for blade in range(6)]
            pygame.draw.polygon(layer, (*visual_effects.interpolate_color(self.LOCKED_COLOR, (0, 0, 0), 0.45), lid_alpha), lid)
            for corner in lid:
                pygame.draw.line(layer, (*self.LOCKED_COLOR, lid_alpha), center, corner, 1)
            pygame.draw.lines(layer, (*self.LOCKED_COLOR, lid_alpha), True, lid, 1)
        
        # Foam riding just inside the rim
        if activation > 0.0:
            for fleck in range(9):
                foam = at(fleck * 2 * math.pi / 9 - self.spin * 0.3, outer * 0.9)
                pygame.draw.circle(
                    layer, (*bright, int(170 * activation)), (int(foam[0]), int(foam[1])), 1 + fleck % 2
                )
        pygame.draw.circle(layer, (*bright, self.RIM_ALPHA), center, int(outer), 1)
        
        screen.blit(layer, layer.get_rect(center=screen_center))
    
    def set_activated(self, activated: bool, sound_manager=None) -> None:
        """Set the activation state of the exit portal.
        
        When deactivated (eggs or a boss present), the portal is dimmed and non-functional.
        When activated (none left), the portal is fully functional.
        
        Args:
            activated: True to activate portal, False to deactivate.
            sound_manager: Optional sound manager to play activation/deactivation sounds.
        """
        # Only play sound if state actually changed
        if self.previous_activated != activated:
            if sound_manager:
                if activated:
                    sound_manager.play_portal_power_up()
                else:
                    sound_manager.play_portal_power_down()
        
        self.previous_activated = self.is_activated
        self.is_activated = activated

