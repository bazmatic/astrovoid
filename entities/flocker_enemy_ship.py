"""Flocker enemy ship with flocking behavior.

This module implements a FlockerEnemyShip that inherits from RotatingThrusterShip
and exhibits classic flocking behavior: separation, alignment, cohesion, and player seeking.
The ship is visually designed to look like a swallow (bird).
"""

import pygame
import math
from typing import Tuple, Optional, List
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
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
        self.wing_phase: float = 0.0  # Animation phase for wing movement
    
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
        flocker_idx: Optional[int] = None
    ) -> None:
        """Update flocker enemy ship with flocking behavior.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position.
            all_flockers: List of all other flocker ships (excluding self).
            neighbor_cache: Optional shared neighbor cache for efficient queries.
            flocker_idx: Optional index of this flocker in the list.
        """
        if not self.active:
            return
        
        # Update wing animation
        self.wing_phase += dt * 3.0  # Wing flapping speed
        
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
        - Forked tail (two tail feathers)
        - Pointed, swept-back wings
        - Streamlined body
        - Darker color on top, lighter underneath
        """
        if not self.active:
            return
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        base_color = config.FLOCKER_ENEMY_COLOR
        body_radius = self.radius * 0.6
        
        # Draw glow effect
        from rendering import visual_effects
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, base_color,
            glow_radius=body_radius * 0.3, intensity=0.2
        )
        
        # Calculate wing animation (subtle flapping)
        wing_angle_offset = math.sin(self.wing_phase) * 5.0  # 5 degree wing movement
        
        # Draw body (oval shape, streamlined)
        body_length = self.radius * 1.2
        body_width = self.radius * 0.8
        
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
        darker_color = tuple(max(0, c - 40) for c in base_color)
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
        
        # Draw wings (swept back, pointed)
        wing_length = self.radius * 1.0
        wing_base_width = self.radius * 0.3
        
        # Left wing
        left_wing_angle = angle_rad + math.radians(90 + wing_angle_offset)
        left_wing_tip_x = self.x + math.cos(left_wing_angle) * wing_length
        left_wing_tip_y = self.y + math.sin(left_wing_angle) * wing_length
        left_wing_base_x = self.x + math.cos(angle_rad) * body_radius * 0.3
        left_wing_base_y = self.y + math.sin(angle_rad) * body_radius * 0.3
        
        # Right wing
        right_wing_angle = angle_rad - math.radians(90 - wing_angle_offset)
        right_wing_tip_x = self.x + math.cos(right_wing_angle) * wing_length
        right_wing_tip_y = self.y + math.sin(right_wing_angle) * wing_length
        right_wing_base_x = self.x + math.cos(angle_rad) * body_radius * 0.3
        right_wing_base_y = self.y + math.sin(angle_rad) * body_radius * 0.3
        
        # Draw wings as triangles
        pygame.draw.polygon(screen, darker_color, [
            (int(left_wing_base_x), int(left_wing_base_y)),
            (int(left_wing_tip_x), int(left_wing_tip_y)),
            (int(self.x + math.cos(angle_rad) * body_radius * 0.5), 
             int(self.y + math.sin(angle_rad) * body_radius * 0.5))
        ])
        pygame.draw.polygon(screen, darker_color, [
            (int(right_wing_base_x), int(right_wing_base_y)),
            (int(right_wing_tip_x), int(right_wing_tip_y)),
            (int(self.x + math.cos(angle_rad) * body_radius * 0.5), 
             int(self.y + math.sin(angle_rad) * body_radius * 0.5))
        ])
        
        # Draw forked tail (two tail feathers extending backward)
        tail_length = self.radius * 0.8
        tail_spread = math.radians(25)  # 25 degree spread between tail feathers
        
        # Left tail feather
        left_tail_angle = angle_rad + math.pi + tail_spread
        left_tail_tip_x = self.x + math.cos(left_tail_angle) * tail_length
        left_tail_tip_y = self.y + math.sin(left_tail_angle) * tail_length
        tail_base_x = self.x - math.cos(angle_rad) * body_radius * 0.6
        tail_base_y = self.y - math.sin(angle_rad) * body_radius * 0.6
        
        # Right tail feather
        right_tail_angle = angle_rad + math.pi - tail_spread
        right_tail_tip_x = self.x + math.cos(right_tail_angle) * tail_length
        right_tail_tip_y = self.y + math.sin(right_tail_angle) * tail_length
        
        # Draw tail feathers
        pygame.draw.polygon(screen, base_color, [
            (int(tail_base_x), int(tail_base_y)),
            (int(left_tail_tip_x), int(left_tail_tip_y)),
            (int(self.x - math.cos(angle_rad) * body_radius * 0.4), 
             int(self.y - math.sin(angle_rad) * body_radius * 0.4))
        ])
        pygame.draw.polygon(screen, base_color, [
            (int(tail_base_x), int(tail_base_y)),
            (int(right_tail_tip_x), int(right_tail_tip_y)),
            (int(self.x - math.cos(angle_rad) * body_radius * 0.4), 
             int(self.y - math.sin(angle_rad) * body_radius * 0.4))
        ])
        
        # Draw outline
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), int(body_radius), 1)

