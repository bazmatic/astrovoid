"""Ship entity implementation.

This module implements the Ship class for the player-controlled spacecraft.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional
import config
from utils import (
    angle_to_radians,
    normalize_angle,
    rotate_point,
    circle_line_collision,
    circle_line_collision_swept,
    circle_circle_collision,
    distance,
    get_wall_normal,
    get_closest_point_on_line,
    reflect_velocity
)
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from entities.projectile import Projectile
from rendering import visual_effects


class Ship(GameEntity, Collidable, Drawable):
    """Player-controlled ship with momentum-based physics.
    
    The ship uses zero-G physics with low friction, allowing for momentum-based
    movement. It can rotate, apply thrust, fire projectiles, and collide with
    walls and enemies.
    
    Attributes:
        angle: Current facing angle in degrees (0 = right, 90 = down).
        fuel: Current fuel remaining.
        ammo: Current ammunition remaining.
        damaged: Whether the ship is currently in a damaged state.
        damage_timer: Frames remaining in damaged state.
    """
    
    def __init__(self, start_pos: Tuple[float, float]):
        """Initialize ship at starting position.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
        """
        super().__init__(start_pos, config.SHIP_SIZE, 0.0, 0.0)
        self.angle = 0.0  # degrees, 0 = right, 90 = down
        self.fuel = config.INITIAL_FUEL
        self.ammo = config.INITIAL_AMMO
        self.damaged = False
        self.damage_timer = 0
        self.glow_phase = 0.0  # For pulsing glow when damaged
        self.thrust_particles = []  # For enhanced thrust visualization
        self.thrusting = False  # Track when thrust is actively being applied
        self.prev_x = self.x  # Previous position for swept collision detection
        self.prev_y = self.y
    
    def rotate_left(self) -> None:
        """Rotate ship counter-clockwise."""
        self.angle -= config.SHIP_ROTATION_SPEED
        self.angle = normalize_angle(self.angle)
    
    def rotate_right(self) -> None:
        """Rotate ship clockwise."""
        self.angle += config.SHIP_ROTATION_SPEED
        self.angle = normalize_angle(self.angle)
    
    def apply_thrust(self) -> bool:
        """Apply thrust in current direction.
        
        Returns:
            True if fuel was consumed, False if out of fuel.
        """
        if self.fuel <= 0:
            return False
        
        # Calculate thrust vector
        angle_rad = angle_to_radians(self.angle)
        thrust_x = math.cos(angle_rad) * config.SHIP_THRUST_FORCE
        thrust_y = math.sin(angle_rad) * config.SHIP_THRUST_FORCE
        
        # Apply thrust
        self.vx += thrust_x
        self.vy += thrust_y
        
        # Limit max speed
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > config.SHIP_MAX_SPEED:
            scale = config.SHIP_MAX_SPEED / speed
            self.vx *= scale
            self.vy *= scale
        
        # Consume fuel
        self.fuel -= config.FUEL_CONSUMPTION_PER_THRUST
        self.thrusting = True  # Mark that thrust is active
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
        
        # Apply friction
        self.vx *= config.SHIP_FRICTION
        self.vy *= config.SHIP_FRICTION
        
        # Update position
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        # Bounce off screen edges
        bounce_factor = 0.85  # Retain 85% of velocity on bounce
        
        # Check horizontal edges (left and right)
        if self.x < self.radius:
            self.x = self.radius
            self.vx = -self.vx * bounce_factor
            self.damaged = True
            self.damage_timer = 30
        elif self.x > config.SCREEN_WIDTH - self.radius:
            self.x = config.SCREEN_WIDTH - self.radius
            self.vx = -self.vx * bounce_factor
            self.damaged = True
            self.damage_timer = 30
        
        # Check vertical edges (top and bottom)
        if self.y < self.radius:
            self.y = self.radius
            self.vy = -self.vy * bounce_factor
            self.damaged = True
            self.damage_timer = 30
        elif self.y > config.SCREEN_HEIGHT - self.radius:
            self.y = config.SCREEN_HEIGHT - self.radius
            self.vy = -self.vy * bounce_factor
            self.damaged = True
            self.damage_timer = 30
        
        # Update damage timer
        if self.damaged:
            self.damage_timer -= 1
            if self.damage_timer <= 0:
                self.damaged = False
        
        # Update glow phase for pulsing when damaged
        if self.damaged:
            self.glow_phase += 0.2
            if self.glow_phase >= 2 * math.pi:
                self.glow_phase -= 2 * math.pi
        
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
        
        # Update existing particles
        for particle in self.thrust_particles[:]:
            particle['x'] += particle['vx'] * dt
            particle['y'] += particle['vy'] * dt
            particle['life'] -= 1
            if particle['life'] <= 0:
                self.thrust_particles.remove(particle)
    
    def fire(self) -> Optional[Projectile]:
        """Fire a projectile.
        
        Returns:
            Projectile instance if fired, None if no ammo.
        """
        if self.ammo <= 0:
            return None
        
        self.ammo -= config.AMMO_CONSUMPTION_PER_SHOT
        
        # Calculate projectile start position (slightly ahead of ship)
        angle_rad = angle_to_radians(self.angle)
        offset_x = math.cos(angle_rad) * (self.radius + 5)
        offset_y = math.sin(angle_rad) * (self.radius + 5)
        start_pos = (self.x + offset_x, self.y + offset_y)
        
        return Projectile(start_pos, self.angle)
    
    def check_wall_collision(
        self,
        walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> bool:
        """Check collision with walls using continuous collision detection.
        
        Uses swept collision detection to prevent tunneling through walls
        at high speeds. Finds the earliest collision along the movement path
        and stops movement at that point.
        
        Args:
            walls: List of wall line segments.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        # Use swept collision detection to find earliest collision
        earliest_collision = None
        earliest_time = 1.0  # Start with end of path
        collision_wall = None
        
        start_pos = (self.prev_x, self.prev_y)
        end_pos = (self.x, self.y)
        
        # Check all walls for collisions along movement path
        for wall in walls:
            collision_detected, collision_time, collision_point = circle_line_collision_swept(
                start_pos, end_pos, self.radius,
                wall[0], wall[1]
            )
            
            if collision_detected and collision_time is not None:
                # Found a collision - check if it's earlier than previous
                if collision_time < earliest_time:
                    earliest_time = collision_time
                    earliest_collision = collision_point
                    collision_wall = wall
        
        # If no collision found, also check if ship is already inside a wall
        # (can happen if ship spawns in wall or previous frame had issues)
        if earliest_collision is None:
            for wall in walls:
                if circle_line_collision(
                    (self.x, self.y), self.radius,
                    wall[0], wall[1]
                ):
                    # Ship is already inside wall - push out immediately
                    normal = get_wall_normal((self.x, self.y), wall[0], wall[1])
                    
                    # Calculate penetration depth
                    closest_point = get_closest_point_on_line((self.x, self.y), wall[0], wall[1])
                    dist_to_wall = distance((self.x, self.y), closest_point)
                    penetration_depth = self.radius - dist_to_wall
                    
                    # Push back by penetration depth + safety margin
                    push_distance = penetration_depth + self.radius * 0.5
                    self.x += normal[0] * push_distance
                    self.y += normal[1] * push_distance
                    
                    # Reflect velocity
                    self.vx, self.vy = reflect_velocity(
                        (self.vx, self.vy),
                        normal,
                        bounce_factor=0.85
                    )
                    
                    self.damaged = True
                    self.damage_timer = 30
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
            dist_to_wall = distance((self.x, self.y), closest_point)
            penetration_depth = max(0.0, self.radius - dist_to_wall)
            
            # Push ship away from wall
            # Use penetration depth + safety margin to ensure complete clearance
            push_distance = penetration_depth + self.radius * 0.5
            self.x += normal[0] * push_distance
            self.y += normal[1] * push_distance
            
            # Reflect velocity off the wall
            self.vx, self.vy = reflect_velocity(
                (self.vx, self.vy),
                normal,
                bounce_factor=0.85  # Retain 85% of speed on bounce
            )
            
            self.damaged = True
            self.damage_timer = 30
            return True
        
        return False
    
    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float
    ) -> bool:
        """Check collision with another circular entity.
        
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
            # Push back from enemy
            dx = self.x - other_pos[0]
            dy = self.y - other_pos[1]
            dist = distance((self.x, self.y), other_pos)
            if dist > 0:
                push_force = 2.0
                self.vx += (dx / dist) * push_force
                self.vy += (dy / dist) * push_force
            self.damaged = True
            self.damage_timer = 30
            return True
        return False
    
    def get_vertices(self) -> List[Tuple[float, float]]:
        """Get ship vertices for rendering (triangle shape).
        
        Returns:
            List of (x, y) vertex coordinates.
        """
        # Triangle pointing right (0 degrees)
        base_vertices = [
            (self.radius, 0),  # Nose
            (-self.radius * 0.7, -self.radius * 0.7),  # Left rear
            (-self.radius * 0.7, self.radius * 0.7)   # Right rear
        ]
        
        # Rotate vertices around center
        center = (0, 0)
        rotated_vertices = []
        for vertex in base_vertices:
            rotated = rotate_point(vertex, center, self.angle)
            rotated_vertices.append((rotated[0] + self.x, rotated[1] + self.y))
        
        return rotated_vertices
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the ship with enhanced visuals.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        vertices = self.get_vertices()
        
        # Determine colors based on damage state
        if self.damaged:
            color_nose = config.COLOR_SHIP_DAMAGED_NOSE
            color_rear = config.COLOR_SHIP_DAMAGED_REAR
            glow_color = (255, 100, 100)
            glow_intensity = config.SHIP_GLOW_INTENSITY * (1.0 + 0.5 * math.sin(self.glow_phase))
        else:
            color_nose = config.COLOR_SHIP_NOSE
            color_rear = config.COLOR_SHIP_REAR
            glow_color = config.COLOR_SHIP
            glow_intensity = config.SHIP_GLOW_INTENSITY
        
        # Draw glow effect
        visual_effects.draw_glow_polygon(
            screen, vertices, glow_color,
            glow_radius=self.radius * config.SHIP_GLOW_RADIUS_MULTIPLIER,
            intensity=glow_intensity
        )
        
        # Draw gradient fill (nose to rear)
        # Nose is first vertex (index 0), rear vertices are at indices 1 and 2
        visual_effects.draw_gradient_polygon(
            screen, vertices, color_nose, color_rear,
            start_vertex=0, end_vertex=1
        )
        
        # Draw ship details
        # Cockpit window (small circle at front)
        nose_vertex = vertices[0]
        cockpit_offset = 2
        angle_rad = angle_to_radians(self.angle)
        cockpit_x = nose_vertex[0] - math.cos(angle_rad) * cockpit_offset
        cockpit_y = nose_vertex[1] - math.sin(angle_rad) * cockpit_offset
        pygame.draw.circle(screen, (200, 220, 255), (int(cockpit_x), int(cockpit_y)), 2)
        
        # Engine details (small rectangles at rear)
        rear_vertices = [vertices[1], vertices[2]]
        for rear_v in rear_vertices:
            # Draw small rectangle perpendicular to ship direction
            perp_angle = self.angle + 90
            perp_rad = angle_to_radians(perp_angle)
            engine_size = 2
            engine_x1 = rear_v[0] + math.cos(perp_rad) * engine_size
            engine_y1 = rear_v[1] + math.sin(perp_rad) * engine_size
            engine_x2 = rear_v[0] - math.cos(perp_rad) * engine_size
            engine_y2 = rear_v[1] - math.sin(perp_rad) * engine_size
            pygame.draw.line(screen, (150, 150, 200), 
                           (int(engine_x1), int(engine_y1)),
                           (int(engine_x2), int(engine_y2)), 2)
        
        # Wing markings (subtle lines along edges)
        if len(vertices) >= 3:
            # Line from nose to left rear
            pygame.draw.line(screen, (80, 120, 180), 
                           (int(vertices[0][0]), int(vertices[0][1])),
                           (int(vertices[1][0]), int(vertices[1][1])), 1)
            # Line from nose to right rear
            pygame.draw.line(screen, (80, 120, 180),
                           (int(vertices[0][0]), int(vertices[0][1])),
                           (int(vertices[2][0]), int(vertices[2][1])), 1)
        
        # Draw enhanced thrust visualization (only when actively thrusting)
        # Check if we have active thrust particles (from previous frame's thrust)
        # or if thrusting flag is currently set (from this frame's apply_thrust call)
        has_thrust_effect = self.thrusting or len(self.thrust_particles) > 0
        if has_thrust_effect:
            angle_rad = angle_to_radians(self.angle)
            base_x = self.x - math.cos(angle_rad) * self.radius * 0.8
            base_y = self.y - math.sin(angle_rad) * self.radius * 0.8
            
            # Calculate speed for plume length
            speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            
            # Draw particle trail
            for particle in self.thrust_particles:
                particle_x = self.x + particle['x']
                particle_y = self.y + particle['y']
                life_ratio = particle['life'] / config.THRUST_PLUME_LENGTH
                
                # Color gradient: yellow -> orange -> red
                if life_ratio > 0.6:
                    color = (255, 255, 100)  # Yellow
                elif life_ratio > 0.3:
                    color = (255, 180, 50)   # Orange
                else:
                    color = (255, 100, 50)   # Red
                
                size = int(particle['size'] * life_ratio)
                if size > 0:
                    pygame.draw.circle(screen, color, 
                                     (int(particle_x), int(particle_y)), size)
            
            # Draw cone-shaped thrust plume
            plume_length = min(config.THRUST_PLUME_LENGTH, speed * 2)
            for i in range(config.THRUST_PLUME_PARTICLES):
                t = i / config.THRUST_PLUME_PARTICLES
                plume_x = base_x - math.cos(angle_rad) * plume_length * t
                plume_y = base_y - math.sin(angle_rad) * plume_length * t
                
                # Size decreases along plume
                size = int(4 * (1 - t))
                if size > 0:
                    # Color gradient
                    if t < 0.3:
                        color = (255, 255, 150)  # Bright yellow
                    elif t < 0.6:
                        color = (255, 200, 50)   # Orange
                    else:
                        color = (255, 100, 0)    # Red
                    
                    # Add some randomness for flicker
                    flicker = random.uniform(0.8, 1.0)
                    flicker_color = tuple(int(c * flicker) for c in color)
                    pygame.draw.circle(screen, flicker_color,
                                     (int(plume_x), int(plume_y)), size)
    
    def draw_ui(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw ship UI (fuel, ammo).
        
        Args:
            screen: The pygame Surface to draw on.
            font: Font to use for text rendering.
        """
        # Fuel gauge
        fuel_text = font.render(f"Fuel: {int(self.fuel)}", True, config.COLOR_TEXT)
        screen.blit(fuel_text, (10, 10))
        
        # Fuel bar
        bar_width = 200
        bar_height = 20
        bar_x = 10
        bar_y = 40
        fuel_percent = max(0, min(1, self.fuel / config.INITIAL_FUEL))
        
        # Background
        pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        # Fuel level
        fuel_color = (100, 200, 100) if fuel_percent > 0.3 else (200, 100, 100)
        pygame.draw.rect(screen, fuel_color, (bar_x, bar_y, int(bar_width * fuel_percent), bar_height))
        pygame.draw.rect(screen, config.COLOR_TEXT, (bar_x, bar_y, bar_width, bar_height), 2)
        
        # Ammo counter
        ammo_text = font.render(f"Ammo: {self.ammo}", True, config.COLOR_TEXT)
        screen.blit(ammo_text, (10, 70))

