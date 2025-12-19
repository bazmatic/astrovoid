"""Ship physics and controls."""

import pygame
import math
from typing import Tuple, List, Optional
import config
import utils
from projectile import Projectile


class Ship:
    """Player-controlled ship with momentum-based physics."""
    
    def __init__(self, start_pos: Tuple[float, float]):
        """Initialize ship at starting position."""
        self.x, self.y = start_pos
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0  # degrees, 0 = right, 90 = down
        self.fuel = config.INITIAL_FUEL
        self.ammo = config.INITIAL_AMMO
        self.radius = config.SHIP_SIZE
        self.damaged = False
        self.damage_timer = 0
    
    def rotate_left(self) -> None:
        """Rotate ship counter-clockwise."""
        self.angle -= config.SHIP_ROTATION_SPEED
        self.angle = utils.normalize_angle(self.angle)
    
    def rotate_right(self) -> None:
        """Rotate ship clockwise."""
        self.angle += config.SHIP_ROTATION_SPEED
        self.angle = utils.normalize_angle(self.angle)
    
    def apply_thrust(self) -> bool:
        """Apply thrust in current direction. Returns True if fuel was consumed."""
        if self.fuel <= 0:
            return False
        
        # Calculate thrust vector
        angle_rad = utils.angle_to_radians(self.angle)
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
        return True
    
    def update(self, dt: float) -> None:
        """Update ship position and apply friction."""
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
    
    def fire(self) -> Optional[Projectile]:
        """Fire a projectile. Returns Projectile if fired, None if no ammo."""
        if self.ammo <= 0:
            return None
        
        self.ammo -= config.AMMO_CONSUMPTION_PER_SHOT
        
        # Calculate projectile start position (slightly ahead of ship)
        angle_rad = utils.angle_to_radians(self.angle)
        offset_x = math.cos(angle_rad) * (self.radius + 5)
        offset_y = math.sin(angle_rad) * (self.radius + 5)
        start_pos = (self.x + offset_x, self.y + offset_y)
        
        return Projectile(start_pos, self.angle)
    
    def check_wall_collision(self, walls: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> bool:
        """Check collision with walls. Returns True if collision occurred."""
        # Check collision with each wall segment
        for wall in walls:
            if utils.circle_line_collision(
                (self.x, self.y), self.radius,
                wall[0], wall[1]
            ):
                # Get wall normal (pointing from wall toward ship)
                normal = utils.get_wall_normal((self.x, self.y), wall[0], wall[1])
                
                # Reflect velocity off the wall
                self.vx, self.vy = utils.reflect_velocity(
                    (self.vx, self.vy),
                    normal,
                    bounce_factor=0.85  # Retain 85% of speed on bounce
                )
                
                # Push ship away from wall to prevent sticking
                push_distance = self.radius + 2
                self.x += normal[0] * push_distance
                self.y += normal[1] * push_distance
                
                self.damaged = True
                self.damage_timer = 30
                return True
        return False
    
    def check_enemy_collision(self, enemy_pos: Tuple[float, float], enemy_radius: float) -> bool:
        """Check collision with enemy. Returns True if collision occurred."""
        if utils.circle_circle_collision(
            (self.x, self.y), self.radius,
            enemy_pos, enemy_radius
        ):
            # Push back from enemy
            dx = self.x - enemy_pos[0]
            dy = self.y - enemy_pos[1]
            dist = utils.distance((self.x, self.y), enemy_pos)
            if dist > 0:
                push_force = 2.0
                self.vx += (dx / dist) * push_force
                self.vy += (dy / dist) * push_force
            self.damaged = True
            self.damage_timer = 30
            return True
        return False
    
    def get_vertices(self) -> List[Tuple[float, float]]:
        """Get ship vertices for rendering (triangle shape)."""
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
            rotated = utils.rotate_point(vertex, center, self.angle)
            rotated_vertices.append((rotated[0] + self.x, rotated[1] + self.y))
        
        return rotated_vertices
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the ship."""
        vertices = self.get_vertices()
        
        # Choose color based on damage state
        color = config.COLOR_SHIP
        if self.damaged:
            color = (255, 100, 100)  # Red when damaged
        
        pygame.draw.polygon(screen, color, vertices)
        pygame.draw.polygon(screen, (255, 255, 255), vertices, 2)
        
        # Draw thrust indicator if moving forward
        if abs(self.vx) > 0.1 or abs(self.vy) > 0.1:
            angle_rad = utils.angle_to_radians(self.angle)
            thrust_x = -math.cos(angle_rad) * self.radius * 0.8
            thrust_y = -math.sin(angle_rad) * self.radius * 0.8
            thrust_pos = (self.x + thrust_x, self.y + thrust_y)
            pygame.draw.circle(screen, (255, 200, 0), (int(thrust_pos[0]), int(thrust_pos[1])), 3)
    
    def draw_ui(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw ship UI (fuel, ammo)."""
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

