"""Rotating thruster ship base class.

This module provides the RotatingThrusterShip base class for ships that use
rotating thruster movement mechanics. This includes rotation, thrust application,
momentum-based physics, and collision detection.

Subclasses can implement their own control mechanisms (keyboard, AI, etc.)
and add additional features like fuel management, sound effects, etc.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional
from abc import ABC, abstractmethod
import config
from utils import (
    angle_to_radians,
    normalize_angle,
    rotate_point,
    circle_line_collision,
    circle_line_collision_swept,
    circle_circle_collision,
    distance,
    distance_squared,
    get_wall_normal,
    get_closest_point_on_line,
    reflect_velocity,
)
from utils.math_utils import apply_circle_collision_physics, apply_wall_collision_physics
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable


class RotatingThrusterShip(GameEntity, Collidable, Drawable):
    """Base class for ships with rotating thruster movement mechanics.
    
    This class provides the core movement system including:
    - Rotation (left/right)
    - Thrust application in facing direction
    - Momentum-based physics with friction
    - Edge bouncing
    - Collision detection (walls and circles)
    - Thrust particle visualization
    
    Subclasses can:
    - Override apply_thrust() to add constraints (e.g., fuel checks)
    - Override draw() to customize appearance
    - Add their own control mechanisms (keyboard, AI, etc.)
    - Add additional features (fuel, ammo, sound, etc.)
    
    Attributes:
        angle: Current facing angle in degrees (0 = right, 90 = down).
        thrust_particles: List of thrust particle dictionaries for visualization.
        thrusting: Whether thrust is currently being applied this frame.
        prev_x: Previous X position for swept collision detection.
        prev_y: Previous Y position for swept collision detection.
    """
    
    def __init__(self, start_pos: Tuple[float, float], radius: float):
        """Initialize rotating thruster ship at starting position.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            radius: Collision radius of the ship.
        """
        super().__init__(start_pos, radius, 0.0, 0.0)
        self.angle = 0.0  # degrees, 0 = right, 90 = down
        self.thrust_particles: List[dict] = []  # For enhanced thrust visualization
        self.thrusting = False  # Track when thrust is actively being applied
        self.prev_x = self.x  # Previous position for swept collision detection
        self.prev_y = self.y
        self.base_rotation_speed = config.SHIP_ROTATION_SPEED
        self.rotation_speed_multiplier = 1.0
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for this ship.
        
        Subclasses can override this to provide different max speeds.
        
        Returns:
            Maximum speed value.
        """
        return config.SHIP_MAX_SPEED
    
    def rotate_left(self) -> None:
        """Rotate ship counter-clockwise."""
        self.angle -= self.current_rotation_speed
        self.angle = normalize_angle(self.angle)
    
    def rotate_right(self) -> None:
        """Rotate ship clockwise."""
        self.angle += self.current_rotation_speed
        self.angle = normalize_angle(self.angle)

    @property
    def current_rotation_speed(self) -> float:
        return self.base_rotation_speed * self.rotation_speed_multiplier
    
    def apply_thrust(self) -> bool:
        """Apply thrust in current direction.
        
        This base implementation always applies thrust. Subclasses can override
        to add constraints (e.g., fuel checks).
        
        Returns:
            True if thrust was applied, False otherwise.
        """
        # Calculate thrust vector
        angle_rad = angle_to_radians(self.angle)
        thrust_x = math.cos(angle_rad) * config.SHIP_THRUST_FORCE
        thrust_y = math.sin(angle_rad) * config.SHIP_THRUST_FORCE
        
        # Apply thrust
        self.vx += thrust_x
        self.vy += thrust_y
        
        # Limit max speed
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.vx *= scale
            self.vy *= scale
        
        # Mark that thrust is active
        self.thrusting = True
        
        return True
    
    def update(self, dt: float) -> None:
        """Update ship position and apply friction.
        
        Args:
            dt: Delta time since last update.
        """
        # Save previous position for swept collision detection
        self.prev_x = self.x
        self.prev_y = self.y
        
        # Save thrusting state from previous frame (set by apply_thrust)
        # This allows it to persist through the draw() call
        was_thrusting = self.thrusting
        
        # Clear thrusting flag at start of update (will be set again if apply_thrust is called this frame)
        self.thrusting = False
        
        # Apply friction and update position
        self.apply_friction_and_update_position(config.SHIP_FRICTION, dt)
        
        # Bounce off screen edges using physics
        # Check horizontal edges (left and right)
        if self.x < self.radius:
            self.x = self.radius
            apply_wall_collision_physics(self, (1.0, 0.0), config.COLLISION_RESTITUTION)
            self.on_edge_collision()
        elif self.x > config.SCREEN_WIDTH - self.radius:
            self.x = config.SCREEN_WIDTH - self.radius
            apply_wall_collision_physics(self, (-1.0, 0.0), config.COLLISION_RESTITUTION)
            self.on_edge_collision()
        
        # Check vertical edges (top and bottom)
        if self.y < self.radius:
            self.y = self.radius
            apply_wall_collision_physics(self, (0.0, 1.0), config.COLLISION_RESTITUTION)
            self.on_edge_collision()
        elif self.y > config.SCREEN_HEIGHT - self.radius:
            self.y = config.SCREEN_HEIGHT - self.radius
            apply_wall_collision_physics(self, (0.0, -1.0), config.COLLISION_RESTITUTION)
            self.on_edge_collision()
        
        # Update thrust particles (only when thrusting from previous frame)
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if was_thrusting and speed > 0.0:
            # Add new particles based on speed
            angle_rad = angle_to_radians(self.angle)
            for _ in range(int(speed * 0.5)):
                if len(self.thrust_particles) < config.THRUST_PLUME_PARTICLES * 3:
                    particle_x = -math.cos(angle_rad) * self.radius * 0.8
                    particle_y = -math.sin(angle_rad) * self.radius * 0.8
                    particle_vx = -math.cos(angle_rad) * speed * 0.3
                    particle_vy = -math.sin(angle_rad) * speed * 0.3
                    self.thrust_particles.append({
                        'x': particle_x,
                        'y': particle_y,
                        'vx': particle_vx,
                        'vy': particle_vy,
                        'life': config.THRUST_PLUME_LENGTH,
                        'size': random.uniform(2, 4)
                    })
        
        # Update existing particles (use list comprehension instead of remove)
        for particle in self.thrust_particles:
            particle['x'] += particle['vx'] * dt
            particle['y'] += particle['vy'] * dt
            particle['life'] -= 1
        # Filter out dead particles
        self.thrust_particles = [p for p in self.thrust_particles if p['life'] > 0]
        
        # Enforce maximum speed limit (after all physics updates)
        # This ensures speed never exceeds max, regardless of collisions, bounces, etc.
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.vx *= scale
            self.vy *= scale
    
    def check_wall_collision(
        self,
        walls: List,
        spatial_grid=None
    ) -> bool:
        """Check collision with walls using continuous collision detection.
        
        Uses swept collision detection to prevent tunneling through walls
        at high speeds. Finds the earliest collision along the movement path
        and stops movement at that point.
        
        Args:
            walls: List of wall segments (WallSegment instances or tuples).
            spatial_grid: Optional spatial grid for optimized collision detection.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        # Use swept collision detection to find earliest collision
        earliest_collision = None
        earliest_time = 1.0  # Start with end of path
        collision_wall = None
        
        start_pos = (self.prev_x, self.prev_y)
        end_pos = (self.x, self.y)
        
        # Use spatial grid if available, otherwise check all walls
        walls_to_check = walls
        if spatial_grid is not None:
            # Get walls along the entire movement path to prevent tunneling
            # This ensures walls near both start and end positions are checked
            walls_to_check = spatial_grid.get_walls_along_path(
                start_pos, end_pos, self.radius * 2.0  # Check slightly larger area
            )
        
        # Check walls for collisions along movement path
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
            
            collision_detected, collision_time, collision_point = circle_line_collision_swept(
                start_pos, end_pos, self.radius,
                segment[0], segment[1]
            )
            
            if collision_detected and collision_time is not None:
                # Found a collision - check if it's earlier than previous
                if collision_time < earliest_time:
                    earliest_time = collision_time
                    earliest_collision = collision_point
                    collision_wall = segment
        
        # If no collision found, also check if ship is already inside a wall
        # (can happen if ship spawns in wall or previous frame had issues)
        if earliest_collision is None:
            for wall in walls_to_check:
                # Handle both WallSegment and tuple formats
                if hasattr(wall, 'get_segment'):
                    if not wall.active:
                        continue
                    segment = wall.get_segment()
                else:
                    segment = wall
                
                if circle_line_collision(
                    (self.x, self.y), self.radius,
                    segment[0], segment[1]
                ):
                    # Ship is already inside wall - push out immediately
                    normal = get_wall_normal((self.x, self.y), segment[0], segment[1])
                    
                    # Calculate penetration depth
                    closest_point = get_closest_point_on_line((self.x, self.y), segment[0], segment[1])
                    dist_to_wall_sq = distance_squared((self.x, self.y), closest_point)
                    dist_to_wall = math.sqrt(dist_to_wall_sq)
                    penetration_depth = self.radius - dist_to_wall
                    
                    # Push back by penetration depth + safety margin
                    push_distance = penetration_depth + self.radius * 0.5
                    self.x += normal[0] * push_distance
                    self.y += normal[1] * push_distance
                    
                    # Reflect velocity using physics
                    apply_wall_collision_physics(self, normal, config.COLLISION_RESTITUTION)
                    
                    # Notify subclass of collision (hook for damage, sound, etc.)
                    self.on_wall_collision()
                    return True
        
        # Handle swept collision
        if earliest_collision is not None and collision_wall is not None:
            # Move ship to collision point (or slightly before to be safe)
            # Use a small epsilon before collision point to ensure we're not inside wall
            safe_time = max(0.0, earliest_time - 0.01)
            self.x = self.prev_x + (self.x - self.prev_x) * safe_time
            self.y = self.prev_y + (self.y - self.prev_y) * safe_time
            
            # Get wall normal at collision point
            normal = get_wall_normal((self.x, self.y), collision_wall[0], collision_wall[1])
            
            # Calculate penetration depth (how far inside wall we are)
            closest_point = get_closest_point_on_line((self.x, self.y), collision_wall[0], collision_wall[1])
            dist_to_wall_sq = distance_squared((self.x, self.y), closest_point)
            dist_to_wall = math.sqrt(dist_to_wall_sq)
            penetration_depth = max(0.0, self.radius - dist_to_wall)
            
            # Push ship away from wall
            # Use penetration depth + safety margin to ensure complete clearance
            push_distance = penetration_depth + self.radius * 0.5
            self.x += normal[0] * push_distance
            self.y += normal[1] * push_distance
            
            # Reflect velocity off the wall using physics
            apply_wall_collision_physics(self, normal, config.COLLISION_RESTITUTION)
            
            # Notify subclass of collision (hook for damage, sound, etc.)
            self.on_wall_collision()
            return True
        
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float,
        other_entity: Optional[GameEntity] = None
    ) -> bool:
        """Check collision with another circular entity.
        
        Uses proper elastic collision physics when other_entity is provided,
        otherwise falls back to simple push-back for backward compatibility.
        
        Args:
            other_pos: Position of the other entity (x, y).
            other_radius: Radius of the other entity.
            other_entity: Optional GameEntity object. If provided, both objects'
                         velocities will be updated using conservation of momentum.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        if circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        ):
            if other_entity is not None:
                # Use proper physics with conservation of momentum
                apply_circle_collision_physics(self, other_entity, config.COLLISION_RESTITUTION)
            else:
                # Backward compatibility: simple push-back
                dx = self.x - other_pos[0]
                dy = self.y - other_pos[1]
                dist_sq = distance_squared((self.x, self.y), other_pos)
                if dist_sq > 0:
                    dist = math.sqrt(dist_sq)
                    push_force = 2.0
                    self.vx += (dx / dist) * push_force
                    self.vy += (dy / dist) * push_force
            
            # Notify subclass of collision (hook for damage, sound, etc.)
            self.on_circle_collision()
            return True
        return False
    
    def on_edge_collision(self) -> None:
        """Hook method called when screen edge collision occurs.
        
        Subclasses can override this to handle collision effects
        (e.g., damage, sound, visual feedback).
        """
        pass
    
    def on_wall_collision(self) -> None:
        """Hook method called when wall collision occurs.
        
        Subclasses can override this to handle collision effects
        (e.g., damage, sound, visual feedback).
        """
        pass
    
    def on_circle_collision(self) -> None:
        """Hook method called when circle collision occurs.
        
        Subclasses can override this to handle collision effects
        (e.g., damage, sound, visual feedback).
        """
        pass
    
    def get_vertices(self) -> List[Tuple[float, float]]:
        """Get ship vertices for rendering (triangle shape).
        
        Returns:
            List of (x, y) vertex coordinates.
        """
        # Triangle pointing right (0 degrees) with near-equilateral proportions
        half_height = self.radius * math.sqrt(3) * 0.5
        rear_x = -self.radius * 0.5
        base_vertices = [
            (self.radius, 0.0),           # Nose
            (rear_x, -half_height),       # Left rear
            (rear_x, half_height)         # Right rear
        ]
        
        # Rotate vertices around center
        center = (0, 0)
        rotated_vertices = []
        for vertex in base_vertices:
            rotated = rotate_point(vertex, center, self.angle)
            rotated_vertices.append((rotated[0] + self.x, rotated[1] + self.y))
        
        return rotated_vertices
    
    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the ship on screen.
        
        Subclasses must implement this to provide their own visual representation.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        pass

