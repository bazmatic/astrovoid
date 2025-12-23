"""Flocker enemy ship with flocking behavior.

This module implements a FlockerEnemyShip that inherits from RotatingThrusterShip
and exhibits classic flocking behavior: separation, alignment, cohesion, and player seeking.
The ship is visually designed to look like a swallow (bird).
"""

import pygame
import math
import random
from typing import Tuple, Optional, List
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.projectile import Projectile
from utils import (
    angle_to_radians,
    get_angle_to_point,
    normalize_angle,
    distance,
    distance_squared
)


class FlockerEnemyShip(RotatingThrusterShip):
    """Enemy ship that exhibits flocking behavior.
    
    Implements three classic flocking rules:
    1. Separation: Steer away from nearby neighbors to avoid crowding
    2. Alignment: Steer toward average heading of nearby neighbors
    3. Cohesion: Steer toward average position of nearby neighbors
    
    Also seeks the player ship.
    
    Attributes:
        All attributes inherited from RotatingThrusterShip.
    """
    
    def __init__(self, start_pos: Tuple[float, float]):
        """Initialize flocker enemy ship."""
        super().__init__(start_pos, config.FLOCKER_ENEMY_SIZE)
        self.angle = random.uniform(0, 360)  # Random starting orientation
        self.wing_phase: float = 0.0  # Animation phase for wing movement
        self.tweet_cooldown: float = 0.0  # Cooldown timer for tweeting
        # Cooldown timer for firing (seconds expressed in frame-normalized units; dt ~= 1 per frame)
        self.fire_cooldown: float = random.uniform(2.0, 5.0) * config.FPS
        self.is_about_to_fire: bool = False  # Flag indicating this flocker is about to fire (for synchronization)
        self.just_fired: bool = False  # Flag indicating this flocker just fired (for synchronization)
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the flocker enemy ship."""
        return config.SHIP_MAX_SPEED * config.FLOCKER_ENEMY_SPEED_MULTIPLIER
    
    def update(
        self,
        dt: float,
        player_pos: Optional[Tuple[float, float]] = None,
        all_flockers: Optional[List['FlockerEnemyShip']] = None,
        neighbor_cache: Optional[object] = None,
        flocker_idx: Optional[int] = None,
        sound_manager: Optional[object] = None
    ) -> None:
        """Update flocker enemy ship with flocking behavior.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position.
            all_flockers: List of all other flocker ships (excluding self).
            neighbor_cache: Optional shared neighbor cache for efficient queries.
            flocker_idx: Optional index of this flocker in the list.
            sound_manager: Optional sound manager for playing tweet sounds.
        """
        if not self.active:
            return
        
        # Reset just_fired flag at start of update (after neighbors have seen it)
        self.just_fired = False
        
        # Update wing animation
        self.wing_phase += dt * 3.0  # Wing flapping speed
        
        # Update tweet cooldown and randomly tweet
        if self.tweet_cooldown > 0:
            self.tweet_cooldown -= dt
        elif sound_manager and random.random() < 0.01:  # 1% chance per frame when cooldown is ready
            # Play tweet sound
            if hasattr(sound_manager, 'play_tweet'):
                sound_manager.play_tweet()
            # Reset cooldown with random interval (3-8 seconds)
            self.tweet_cooldown = random.uniform(3.0, 8.0)  # 3-8 seconds
        
        # Update fire cooldown
        # Note: just_fired is reset in get_fired_projectile after neighbors can see it
        if self.fire_cooldown > 0:
            # Clamp to zero to avoid going negative and spamming shots
            self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
            # Set is_about_to_fire flag when cooldown is almost ready (within ~0.2 seconds)
            self.is_about_to_fire = self.fire_cooldown <= (0.2 * config.FPS)
        else:
            self.is_about_to_fire = False
        
        # Use neighbor cache if available, otherwise fall back to full list
        if neighbor_cache is not None and flocker_idx is not None:
            separation_force = self._calculate_separation_cached(neighbor_cache, flocker_idx)
            alignment_force = self._calculate_alignment_cached(neighbor_cache, flocker_idx)
            cohesion_force = self._calculate_cohesion_cached(neighbor_cache, flocker_idx)
        else:
            # Fallback to original method
            separation_force = self._calculate_separation(all_flockers or [])
            alignment_force = self._calculate_alignment(all_flockers or [])
            cohesion_force = self._calculate_cohesion(all_flockers or [])
        
        seek_force = self._calculate_seek(player_pos) if player_pos else (0.0, 0.0)
        
        # Combine forces with weights
        total_force_x = (
            separation_force[0] * config.FLOCKER_ENEMY_SEPARATION_WEIGHT +
            alignment_force[0] * config.FLOCKER_ENEMY_ALIGNMENT_WEIGHT +
            cohesion_force[0] * config.FLOCKER_ENEMY_COHESION_WEIGHT +
            seek_force[0] * config.FLOCKER_ENEMY_SEEK_WEIGHT
        )
        total_force_y = (
            separation_force[1] * config.FLOCKER_ENEMY_SEPARATION_WEIGHT +
            alignment_force[1] * config.FLOCKER_ENEMY_ALIGNMENT_WEIGHT +
            cohesion_force[1] * config.FLOCKER_ENEMY_COHESION_WEIGHT +
            seek_force[1] * config.FLOCKER_ENEMY_SEEK_WEIGHT
        )
        
        # Normalize combined force
        force_magnitude = math.sqrt(total_force_x * total_force_x + total_force_y * total_force_y)
        if force_magnitude > 0.0:
            total_force_x /= force_magnitude
            total_force_y /= force_magnitude
        
        # Calculate desired angle
        desired_angle = get_angle_to_point((self.x, self.y), 
                                            (self.x + total_force_x, self.y + total_force_y))
        
        # Rotate toward desired angle
        angle_diff = self._normalize_angle_diff(desired_angle - self.angle)
        rotation_threshold = config.SHIP_ROTATION_SPEED * 2.0  # Allow some tolerance
        
        if abs(angle_diff) > rotation_threshold:
            if angle_diff > 0:
                self.rotate_right()
            else:
                self.rotate_left()
        
        # Apply thrust if roughly aligned with desired direction
        if abs(angle_diff) < 45.0:  # Within 45 degrees
            self.apply_thrust()
        
        # Call parent update for physics
        super().update(dt)
    
    def _normalize_angle_diff(self, angle_diff: float) -> float:
        """Normalize angle difference to -180 to 180 range."""
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        return angle_diff
    
    def _calculate_separation(self, all_flockers: List['FlockerEnemyShip']) -> Tuple[float, float]:
        """Calculate separation force (steer away from nearby neighbors).
        
        Args:
            all_flockers: List of all other flocker ships.
            
        Returns:
            Separation force vector (x, y).
        """
        separation_x = 0.0
        separation_y = 0.0
        separation_radius_sq = config.FLOCKER_ENEMY_SEPARATION_RADIUS * config.FLOCKER_ENEMY_SEPARATION_RADIUS
        
        for flocker in all_flockers:
            if not flocker.active:
                continue
            
            dist_sq = distance_squared((self.x, self.y), (flocker.x, flocker.y))
            
            if dist_sq > 0.0 and dist_sq < separation_radius_sq:
                # Calculate vector away from neighbor, weighted by inverse distance
                dx = self.x - flocker.x
                dy = self.y - flocker.y
                dist = math.sqrt(dist_sq)
                
                # Normalize and weight by inverse distance (closer = stronger)
                weight = 1.0 / dist
                separation_x += (dx / dist) * weight
                separation_y += (dy / dist) * weight
        
        # Normalize separation force
        magnitude = math.sqrt(separation_x * separation_x + separation_y * separation_y)
        if magnitude > 0.0:
            separation_x /= magnitude
            separation_y /= magnitude
        
        return (separation_x, separation_y)
    
    def _calculate_separation_cached(
        self,
        neighbor_cache: object,
        flocker_idx: int
    ) -> Tuple[float, float]:
        """Calculate separation force using cached neighbors (optimized).
        
        Args:
            neighbor_cache: Shared neighbor cache instance.
            flocker_idx: Index of this flocker.
            
        Returns:
            Separation force vector (x, y).
        """
        separation_x = 0.0
        separation_y = 0.0
        separation_radius = config.FLOCKER_ENEMY_SEPARATION_RADIUS
        
        neighbors = neighbor_cache.get_neighbors(flocker_idx, separation_radius)
        
        for neighbor, dist in neighbors:
            # Calculate vector away from neighbor, weighted by inverse distance
            dx = self.x - neighbor.x
            dy = self.y - neighbor.y
            
            # Normalize and weight by inverse distance (closer = stronger)
            weight = 1.0 / dist
            separation_x += (dx / dist) * weight
            separation_y += (dy / dist) * weight
        
        # Normalize separation force
        magnitude = math.sqrt(separation_x * separation_x + separation_y * separation_y)
        if magnitude > 0.0:
            separation_x /= magnitude
            separation_y /= magnitude
        
        return (separation_x, separation_y)
    
    def _calculate_alignment(self, all_flockers: List['FlockerEnemyShip']) -> Tuple[float, float]:
        """Calculate alignment force (steer toward average heading of neighbors).
        
        Args:
            all_flockers: List of all other flocker ships.
            
        Returns:
            Alignment force vector (x, y).
        """
        alignment_x = 0.0
        alignment_y = 0.0
        neighbor_count = 0
        alignment_radius_sq = config.FLOCKER_ENEMY_ALIGNMENT_RADIUS * config.FLOCKER_ENEMY_ALIGNMENT_RADIUS
        
        for flocker in all_flockers:
            if not flocker.active:
                continue
            
            dist_sq = distance_squared((self.x, self.y), (flocker.x, flocker.y))
            
            if dist_sq > 0.0 and dist_sq < alignment_radius_sq:
                # Get velocity direction from neighbor's angle
                angle_rad = angle_to_radians(flocker.angle)
                alignment_x += math.cos(angle_rad)
                alignment_y += math.sin(angle_rad)
                neighbor_count += 1
        
        if neighbor_count > 0:
            alignment_x /= neighbor_count
            alignment_y /= neighbor_count
            
            # Normalize
            magnitude = math.sqrt(alignment_x * alignment_x + alignment_y * alignment_y)
            if magnitude > 0.0:
                alignment_x /= magnitude
                alignment_y /= magnitude
        
        return (alignment_x, alignment_y)
    
    def _calculate_alignment_cached(
        self,
        neighbor_cache: object,
        flocker_idx: int
    ) -> Tuple[float, float]:
        """Calculate alignment force using cached neighbors (optimized).
        
        Args:
            neighbor_cache: Shared neighbor cache instance.
            flocker_idx: Index of this flocker.
            
        Returns:
            Alignment force vector (x, y).
        """
        alignment_x = 0.0
        alignment_y = 0.0
        neighbor_count = 0
        alignment_radius = config.FLOCKER_ENEMY_ALIGNMENT_RADIUS
        
        neighbors = neighbor_cache.get_neighbors(flocker_idx, alignment_radius)
        
        for neighbor, _ in neighbors:
            # Get velocity direction from neighbor's angle
            angle_rad = angle_to_radians(neighbor.angle)
            alignment_x += math.cos(angle_rad)
            alignment_y += math.sin(angle_rad)
            neighbor_count += 1
        
        if neighbor_count > 0:
            alignment_x /= neighbor_count
            alignment_y /= neighbor_count
            
            # Normalize
            magnitude = math.sqrt(alignment_x * alignment_x + alignment_y * alignment_y)
            if magnitude > 0.0:
                alignment_x /= magnitude
                alignment_y /= magnitude
        
        return (alignment_x, alignment_y)
    
    def _calculate_cohesion(self, all_flockers: List['FlockerEnemyShip']) -> Tuple[float, float]:
        """Calculate cohesion force (steer toward average position of neighbors).
        
        Args:
            all_flockers: List of all other flocker ships.
            
        Returns:
            Cohesion force vector (x, y).
        """
        center_x = 0.0
        center_y = 0.0
        neighbor_count = 0
        cohesion_radius_sq = config.FLOCKER_ENEMY_COHESION_RADIUS * config.FLOCKER_ENEMY_COHESION_RADIUS
        
        for flocker in all_flockers:
            if not flocker.active:
                continue
            
            dist_sq = distance_squared((self.x, self.y), (flocker.x, flocker.y))
            
            if dist_sq > 0.0 and dist_sq < cohesion_radius_sq:
                center_x += flocker.x
                center_y += flocker.y
                neighbor_count += 1
        
        if neighbor_count > 0:
            center_x /= neighbor_count
            center_y /= neighbor_count
            
            # Calculate vector toward center
            cohesion_x = center_x - self.x
            cohesion_y = center_y - self.y
            
            # Normalize
            magnitude = math.sqrt(cohesion_x * cohesion_x + cohesion_y * cohesion_y)
            if magnitude > 0.0:
                cohesion_x /= magnitude
                cohesion_y /= magnitude
        
        return (cohesion_x, cohesion_y)
    
    def _calculate_cohesion_cached(
        self,
        neighbor_cache: object,
        flocker_idx: int
    ) -> Tuple[float, float]:
        """Calculate cohesion force using cached neighbors (optimized).
        
        Args:
            neighbor_cache: Shared neighbor cache instance.
            flocker_idx: Index of this flocker.
            
        Returns:
            Cohesion force vector (x, y).
        """
        center_x = 0.0
        center_y = 0.0
        neighbor_count = 0
        cohesion_radius = config.FLOCKER_ENEMY_COHESION_RADIUS
        cohesion_x = 0.0
        cohesion_y = 0.0
        
        neighbors = neighbor_cache.get_neighbors(flocker_idx, cohesion_radius)
        
        for neighbor, _ in neighbors:
            center_x += neighbor.x
            center_y += neighbor.y
            neighbor_count += 1
        
        if neighbor_count > 0:
            center_x /= neighbor_count
            center_y /= neighbor_count
            
            # Calculate vector toward center
            cohesion_x = center_x - self.x
            cohesion_y = center_y - self.y
            
            # Normalize
            magnitude = math.sqrt(cohesion_x * cohesion_x + cohesion_y * cohesion_y)
            if magnitude > 0.0:
                cohesion_x /= magnitude
                cohesion_y /= magnitude
        
        return (cohesion_x, cohesion_y)
    
    def _calculate_seek(self, player_pos: Optional[Tuple[float, float]]) -> Tuple[float, float]:
        """Calculate seek force (steer toward player).
        
        Args:
            player_pos: Current player position.
            
        Returns:
            Seek force vector (x, y).
        """
        if not player_pos:
            return (0.0, 0.0)
        
        seek_x = player_pos[0] - self.x
        seek_y = player_pos[1] - self.y
        
        # Normalize
        magnitude = math.sqrt(seek_x * seek_x + seek_y * seek_y)
        if magnitude > 0.0:
            seek_x /= magnitude
            seek_y /= magnitude
        
        return (seek_x, seek_y)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the flocker enemy ship as a swallow (bird).
        
        Features:
        - Sickle-moon-like, backwards-curving wings
        - Straight tail
        - Streamlined body
        - Darker color on top, lighter underneath
        """
        if not self.active:
            return
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        base_color = config.FLOCKER_ENEMY_COLOR
        darker_color = tuple(max(0, c - 40) for c in base_color)
        body_radius = self.radius * 0.5
        
        # Draw glow effect
        from rendering import visual_effects
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, base_color,
            glow_radius=body_radius * 0.3, intensity=0.2
        )
        
        # Calculate wing animation (subtle flapping)
        wing_angle_offset = math.sin(self.wing_phase) * 3.0  # 3 degree wing movement
        
        # Draw body (small oval shape, streamlined)
        body_length = self.radius * 0.8
        body_width = self.radius * 0.5
        
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
        rotated_body = pygame.transform.rotate(body_surface, -self.angle)
        body_rect = rotated_body.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_body, body_rect)
        
        # Draw sickle-moon-like, backwards-curving wings
        wing_span = self.radius * 1.4  # Wing span
        wing_curve_radius = self.radius * 1.2  # Radius of the curved wing
        wing_base_offset = self.radius * 0.2  # How far forward the wing attaches
        
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
            start_angle = angle_rad + math.radians(90 + wing_angle_offset)
            end_angle = angle_rad + math.radians(135 + wing_angle_offset)  # Curves backward
            
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
            start_angle = angle_rad - math.radians(90 - wing_angle_offset)
            end_angle = angle_rad - math.radians(135 - wing_angle_offset)  # Curves backward
            
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
        tail_length = self.radius * 0.9
        tail_width = self.radius * 0.15
        
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
    
    def _check_neighbor_firing(
        self,
        neighbor_cache: Optional[object],
        flocker_idx: Optional[int],
        all_flockers: Optional[List['FlockerEnemyShip']],
        sync_radius: float
    ) -> bool:
        """Check if any neighbors are firing or about to fire (for synchronization).
        
        Args:
            neighbor_cache: Optional shared neighbor cache.
            flocker_idx: Optional index of this flocker.
            all_flockers: List of all other flocker ships.
            sync_radius: Radius to check for neighbors.
            
        Returns:
            True if any neighbor is firing or about to fire.
        """
        # Use neighbor cache if available
        if neighbor_cache is not None and flocker_idx is not None:
            neighbors = neighbor_cache.get_neighbors(flocker_idx, sync_radius)
            for neighbor, _ in neighbors:
                if neighbor.just_fired or neighbor.is_about_to_fire:
                    return True
        elif all_flockers:
            # Fallback: check all flockers within sync radius
            sync_radius_sq = sync_radius * sync_radius
            for flocker in all_flockers:
                if not flocker.active or flocker is self:
                    continue
                
                dist_sq = distance_squared((self.x, self.y), (flocker.x, flocker.y))
                if dist_sq <= sync_radius_sq:
                    if flocker.just_fired or flocker.is_about_to_fire:
                        return True
        
        return False
    
    def get_fired_projectile(
        self,
        player_pos: Optional[Tuple[float, float]],
        neighbor_cache: Optional[object] = None,
        flocker_idx: Optional[int] = None,
        all_flockers: Optional[List['FlockerEnemyShip']] = None
    ) -> Optional[Projectile]:
        """Get a projectile fired by this flocker if applicable.
        
        Flockers fire when:
        1. Fire cooldown has expired
        2. Player is within firing range
        3. Either this flocker randomly decides to fire, OR a neighbor is firing/about to fire (synchronization)
        
        Args:
            player_pos: Current player position.
            neighbor_cache: Optional shared neighbor cache.
            flocker_idx: Optional index of this flocker.
            all_flockers: List of all other flocker ships.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        if not self.active or not player_pos:
            return None
        
        # Check if player is within firing range
        dist_to_player = distance((self.x, self.y), player_pos)
        if dist_to_player > config.ENEMY_FIRE_RANGE:
            return None
        
        # Check if fire cooldown has expired
        if self.fire_cooldown > 0.0:
            return None
        
        # Check if flocker is close to player and pointing roughly at it (definite fire)
        close_range = config.FLOCKER_ENEMY_CLOSE_RANGE_FIRE_DISTANCE
        angle_tolerance = config.FLOCKER_ENEMY_CLOSE_RANGE_FIRE_ANGLE_TOLERANCE
        
        is_close = dist_to_player <= close_range
        if is_close:
            # Calculate angle to player
            angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
            angle_diff = self._normalize_angle_diff(angle_to_player - self.angle)
            
            # If pointing roughly at player, definitely fire
            if abs(angle_diff) <= angle_tolerance:
                should_fire = True
            else:
                should_fire = False
        else:
            should_fire = False
        
        # If not in close range or not pointing at player, check for synchronization
        if not should_fire:
            # Check if neighbors are firing (synchronization)
            sync_radius = config.FLOCKER_ENEMY_COHESION_RADIUS  # Use cohesion radius for sync
            neighbor_firing = self._check_neighbor_firing(
                neighbor_cache, flocker_idx, all_flockers, sync_radius
            )
            
            # Fire if neighbor is firing (synchronization)
            if neighbor_firing:
                # High chance to fire when neighbor is firing (synchronization)
                should_fire = random.random() < 0.8
        
        if not should_fire:
            return None
        
        # Calculate angle to player (if not already calculated in close range check)
        if not is_close:
            angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        
        # Create projectile
        projectile = Projectile((self.x, self.y), angle_to_player, is_enemy=True)
        
        # Mark as just fired for synchronization (neighbors will see this in their get_fired_projectile call)
        self.just_fired = True
        
        # Reset fire cooldown to ~1 second (frame-normalized)
        self.fire_cooldown = 1.0 * config.FPS
        
        # Reset just_fired flag after a tiny delay so neighbors can see it this frame
        # We'll reset it at the start of next update cycle
        return projectile

