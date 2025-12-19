"""Ship entity implementation.

This module implements the Ship class for the player-controlled spacecraft.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional
import config
from utils import angle_to_radians
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.projectile import Projectile
from rendering import visual_effects
from sounds import SoundManager


class Ship(RotatingThrusterShip):
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
        super().__init__(start_pos, config.SHIP_SIZE)
        self.fuel = config.INITIAL_FUEL
        self.ammo = config.INITIAL_AMMO
        self.damaged = False
        self.damage_timer = 0
        self.glow_phase = 0.0  # For pulsing glow when damaged
        self.prev_thrusting = False  # Track previous frame's thrusting state for sound management
        self.sound_manager = SoundManager()  # Initialize sound manager
    
    def apply_thrust(self) -> bool:
        """Apply thrust in current direction.
        
        Returns:
            True if fuel was consumed, False if out of fuel.
        """
        if self.fuel <= 0:
            return False
        
        # Apply thrust using base class implementation
        result = super().apply_thrust()
        
        if result:
            # Consume fuel
            self.fuel -= config.FUEL_CONSUMPTION_PER_THRUST
            
            # Start thruster sound (will only start if not already playing)
            self.sound_manager.start_thruster()
        
        return result
    
    def update(self, dt: float) -> None:
        """Update ship position and apply friction.
        
        Args:
            dt: Delta time since last update.
        """
        # Save thrusting state from previous frame (set by apply_thrust)
        # This allows it to persist through the draw() call
        was_thrusting = self.thrusting
        
        # Call base class update (handles movement, friction, edge bouncing, particles)
        super().update(dt)
        
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
        
        # Manage thruster sound: stop if we were thrusting in previous frame but apply_thrust wasn't called this frame
        # was_thrusting indicates if apply_thrust was called in previous frame
        # If it was True but apply_thrust wasn't called this frame (thrusting is False), stop the sound
        if self.prev_thrusting and not was_thrusting:
            self.sound_manager.stop_thruster()
        
        # Update previous thrusting state for next frame
        # Track whether apply_thrust was called this frame (indicated by was_thrusting)
        self.prev_thrusting = was_thrusting
    
    def fire(self) -> Optional[Projectile]:
        """Fire a projectile.
        
        Returns:
            Projectile instance if fired, None if no ammo.
        """
        if self.ammo <= 0:
            return None
        
        self.ammo -= config.AMMO_CONSUMPTION_PER_SHOT
        
        # Play shoot sound
        self.sound_manager.play_shoot()
        
        # Calculate projectile start position (slightly ahead of ship)
        angle_rad = angle_to_radians(self.angle)
        offset_x = math.cos(angle_rad) * (self.radius + 5)
        offset_y = math.sin(angle_rad) * (self.radius + 5)
        start_pos = (self.x + offset_x, self.y + offset_y)
        
        return Projectile(start_pos, self.angle)
    
    def on_edge_collision(self) -> None:
        """Handle edge collision - set damage state."""
        self.damaged = True
        self.damage_timer = 30
    
    def on_wall_collision(self) -> None:
        """Handle wall collision - set damage state."""
        self.damaged = True
        self.damage_timer = 30
    
    def on_circle_collision(self) -> None:
        """Handle circle collision - set damage state."""
        self.damaged = True
        self.damage_timer = 30
    
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

