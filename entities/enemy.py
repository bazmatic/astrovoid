"""Enemy entity implementation.

This module implements the Enemy class using the Strategy pattern for behaviors,
following the Open/Closed Principle.
"""

import pygame
import random
import math
from typing import Tuple, List, Optional, TYPE_CHECKING
import config
import level_rules
from utils import (
    angle_to_radians,
    circle_line_collision,
    circle_circle_collision,
    get_angle_to_point,
    distance,
    distance_squared
)
from utils.math_utils import apply_circle_collision_physics, apply_wall_collision_physics
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable

if TYPE_CHECKING:
    from entities.projectile import Projectile
from entities.enemy_strategies import (
    StaticEnemyStrategy,
    PatrolEnemyStrategy,
    AggressiveEnemyStrategy
)
from rendering import visual_effects


class Enemy(GameEntity, Collidable, Drawable):
    """Enemy entity with configurable behavior strategies.
    
    Uses the Strategy pattern to allow different enemy behaviors without
    modifying the Enemy class itself. This follows the Open/Closed Principle.
    
    Attributes:
        strategy: The behavior strategy for this enemy.
        speed: Movement speed (for dynamic enemies).
        angle: Current facing angle in degrees.
    """
    
    def __init__(self, pos: Tuple[float, float], enemy_type: str = "static", level: int = 1):
        """Initialize enemy at position with specified type.
        
        Args:
            pos: Initial position as (x, y) tuple.
            enemy_type: Type of enemy - "static", "patrol", or "aggressive".
            level: Current level number (1-based) for strength scaling.
        """
        radius = config.STATIC_ENEMY_SIZE if enemy_type == "static" else config.DYNAMIC_ENEMY_SIZE
        super().__init__(pos, radius)
        
        self.type = enemy_type
        self.level = level
        
        # Get level-based strength configuration
        strength = level_rules.get_enemy_strength(level)
        
        # Set strategy based on type
        if enemy_type == "static":
            self.strategy = StaticEnemyStrategy()
            self.speed = 0.0
            self.angle = random.uniform(0, 360)  # Random starting orientation
            # Hit points for momentum system
            self.hit_points = config.STATIC_ENEMY_HIT_POINTS
            self.max_hit_points = config.STATIC_ENEMY_HIT_POINTS
        elif enemy_type == "patrol":
            self.strategy = PatrolEnemyStrategy()
            self.speed = strength.patrol_speed
            self.angle = random.uniform(0, 360)  # Random starting orientation
        elif enemy_type == "aggressive":
            self.strategy = AggressiveEnemyStrategy()
            self.speed = strength.aggressive_speed
            self.angle = random.uniform(0, 360)  # Random starting orientation
        else:
            raise ValueError(f"Unknown enemy type: {enemy_type}")
        
        # Store strength properties
        self.damage = strength.damage
        self.fire_interval_min = strength.fire_interval_min
        self.fire_interval_max = strength.fire_interval_max
        self.fire_range = strength.fire_range
        
        # Animation state
        self.pulse_phase = random.uniform(0, 2 * math.pi)  # Random start to avoid sync
        self.is_alert = False  # Alert state for aggressive enemies
    
    def update(
        self,
        dt: float,
        player_pos: Optional[Tuple[float, float]] = None,
        walls: Optional[List] = None
    ) -> None:
        """Update enemy position and behavior using strategy.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position, if available.
            walls: List of wall segments for collision detection.
        """
        if not self.active:
            return
        
        self.strategy.update(self, dt, player_pos, walls)
        
        # Update pulse animation
        pulse_speed = config.ENEMY_PULSE_SPEED
        if self.is_alert:
            pulse_speed *= 2.0  # Faster pulse when alert
        self.pulse_phase += pulse_speed
        if self.pulse_phase >= 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
    
    def get_fired_projectile(self, player_pos: Optional[Tuple[float, float]]) -> Optional['Projectile']:
        """Get a projectile fired by this enemy if applicable.
        
        Args:
            player_pos: Current player position.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        if not self.active:
            return None
        
        # Check if strategy has a fire method (only patrol enemies have this)
        if hasattr(self.strategy, 'fire'):
            return self.strategy.fire(self, player_pos)
        
        return None
    
    def check_wall_collision(
        self,
        walls: List,
        spatial_grid=None
    ) -> bool:
        """Check collision with wall segments and bounce if moving.
        
        Args:
            walls: List of wall segments (WallSegment instances or tuples).
            spatial_grid: Optional spatial grid for optimized collision detection.
            
        Returns:
            True if collision occurred, False otherwise.
        """
        # For static enemies, only check collisions if moving
        if self.type == "static":
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
                    normal_x = -wall_ny
                    normal_y = wall_nx
                    
                    # Check which side of wall entity is on, flip normal if needed
                    to_entity_x = self.x - wall_start[0]
                    to_entity_y = self.y - wall_start[1]
                    dot_normal = to_entity_x * normal_x + to_entity_y * normal_y
                    if dot_normal < 0:
                        normal_x = -normal_x
                        normal_y = -normal_y
                    
                    # For static enemies, bounce off walls
                    if self.type == "static":
                        # Reflect velocity using physics
                        apply_wall_collision_physics(self, (normal_x, normal_y), config.COLLISION_RESTITUTION)
                        
                        # Move entity away from wall to prevent overlap
                        overlap_distance = self.radius + 1.0
                        self.x += normal_x * overlap_distance
                        self.y += normal_y * overlap_distance
                    else:
                        # For dynamic enemies (patrol, aggressive), also bounce off walls
                        # This prevents them from passing through walls
                        apply_wall_collision_physics(self, (normal_x, normal_y), config.COLLISION_RESTITUTION)
                        
                        # Move entity away from wall to prevent overlap
                        overlap_distance = self.radius + 1.0
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
            (self.x, self.y), self.radius,
            other_pos, other_radius
        ):
            return False
        
        if other_entity is not None:
            # Use proper physics with conservation of momentum
            apply_circle_collision_physics(self, other_entity, config.COLLISION_RESTITUTION)
        
        return True
    
    def destroy(self) -> None:
        """Destroy the enemy."""
        self.active = False
    
    def take_damage(self) -> bool:
        """Take damage from a projectile hit.
        
        Returns:
            True if enemy is destroyed, False otherwise.
        """
        if self.type == "static":
            self.hit_points -= 1
            return self.hit_points <= 0
        # Non-static enemies are destroyed immediately (existing behavior)
        return True
    
    def apply_momentum(self, vx: float, vy: float) -> None:
        """Apply momentum from a projectile impact.
        
        Args:
            vx: X component of velocity to add.
            vy: Y component of velocity to add.
        """
        if self.type == "static":
            self.vx += vx
            self.vy += vy
    
    def draw(self, screen: pygame.Surface, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Draw the enemy on screen with enhanced visuals.
        
        Args:
            screen: The pygame Surface to draw on.
            player_pos: Optional player position for turret aiming and firing readiness.
        """
        if not self.active:
            return
        
        # Check if enemy is on screen (simple bounds check for optimization)
        screen_margin = 100  # Draw slightly off-screen for smooth transitions
        if (self.x < -screen_margin or self.x > config.SCREEN_WIDTH + screen_margin or
            self.y < -screen_margin or self.y > config.SCREEN_HEIGHT + screen_margin):
            return  # Skip drawing if far off-screen
        
        # Cache trigonometric calculations
        sin_pulse = math.sin(self.pulse_phase)
        cos_pulse = math.cos(self.pulse_phase)
        sin_pulse_2x = math.sin(self.pulse_phase * 2)
        
        # Calculate pulsing radius and color intensity
        pulse_factor = 1.0 + config.ENEMY_PULSE_AMPLITUDE * sin_pulse
        current_radius = self.radius * pulse_factor
        
        # Base color
        base_color = config.COLOR_ENEMY_STATIC if self.type == "static" else config.COLOR_ENEMY_DYNAMIC
        
        # For patrol enemies: check firing readiness and calculate turret angle
        turret_angle = None
        is_ready_to_fire = False
        if self.type == "patrol" and player_pos is not None:
            # Calculate turret angle (direction to player)
            turret_angle = get_angle_to_point((self.x, self.y), player_pos)
            
            # Check if ready to fire (player in range and cooldown expired)
            dist_to_player_sq = distance_squared((self.x, self.y), player_pos)
            fire_range_sq = self.fire_range * self.fire_range
            if (dist_to_player_sq <= fire_range_sq and 
                hasattr(self.strategy, 'fire_cooldown') and 
                self.strategy.fire_cooldown <= 0):
                is_ready_to_fire = True
        
        # Adjust color based on pulse and alert state (use cached sin value)
        color_intensity = 0.8 + 0.2 * (sin_pulse * 0.5 + 0.5)
        if self.is_alert:
            # Brighter and more intense when alert
            color_intensity = 1.0
            base_color = tuple(min(255, int(c * 1.3)) for c in base_color)
        
        # Apply brightening effect for patrol enemies ready to fire
        if is_ready_to_fire:
            brightness_multiplier = 1.4
            base_color = tuple(min(255, int(c * brightness_multiplier)) for c in base_color)
            color_intensity = 1.0
        
        color = tuple(int(c * color_intensity) for c in base_color)
        
        # Draw glow effect (more intense when alert or ready to fire)
        glow_intensity = 0.2
        if self.is_alert:
            glow_intensity = 0.5
        if is_ready_to_fire:
            glow_intensity = 0.7
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), current_radius, color,
            glow_radius=current_radius * 0.3, intensity=glow_intensity
        )
        
        # Draw main circle
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), int(current_radius))
        
        # Draw border (flashing when alert, use cached sin value)
        border_color = (255, 255, 255)
        if self.is_alert:
            # Flashing border
            flash = int(255 * (sin_pulse_2x * 0.5 + 0.5))
            border_color = (flash, flash // 2, flash // 2)
        pygame.draw.circle(screen, border_color, (int(self.x), int(self.y)), int(current_radius), 2)
        
        # Type-specific visuals (cache trigonometric calculations)
        if self.type == "static":
            # Angular/spiky pattern - draw radial spikes
            num_spikes = 8
            spike_angle_base = self.pulse_phase * 10
            spike_length = current_radius * 0.6
            for i in range(num_spikes):
                spike_angle = (i * 360 / num_spikes) + spike_angle_base
                spike_rad = angle_to_radians(spike_angle)
                cos_spike = math.cos(spike_rad)
                sin_spike = math.sin(spike_rad)
                spike_x = self.x + cos_spike * spike_length
                spike_y = self.y + sin_spike * spike_length
                pygame.draw.line(screen, (255, 150, 150),
                               (int(self.x), int(self.y)),
                               (int(spike_x), int(spike_y)), 2)
        
        elif self.type == "patrol":
            # Smooth circle with concentric pattern
            # Draw inner circle
            inner_radius = current_radius * 0.5
            pygame.draw.circle(screen, tuple(min(255, c + 30) for c in color),
                             (int(self.x), int(self.y)), int(inner_radius), 1)
            # Draw radial lines (cache calculations)
            num_lines = 4
            line_angle_base = self.pulse_phase * 20
            line_length = current_radius * 0.7
            for i in range(num_lines):
                line_angle = (i * 360 / num_lines) + line_angle_base
                line_rad = angle_to_radians(line_angle)
                cos_line = math.cos(line_rad)
                sin_line = math.sin(line_rad)
                line_x = self.x + cos_line * line_length
                line_y = self.y + sin_line * line_length
                pygame.draw.line(screen, tuple(min(255, c + 20) for c in color),
                               (int(self.x), int(self.y)),
                               (int(line_x), int(line_y)), 1)
            
            # Draw turret direction indicator (arrow pointing at player)
            if turret_angle is not None:
                turret_rad = angle_to_radians(turret_angle)
                cos_turret = math.cos(turret_rad)
                sin_turret = math.sin(turret_rad)
                
                # Make arrow larger and more prominent
                arrow_length = 12
                arrow_width = 6
                arrow_extend = 4
                base_offset = arrow_length * 0.6
                
                # Arrow tip extends beyond circle edge for better visibility
                arrow_tip_x = self.x + cos_turret * (current_radius + arrow_extend)
                arrow_tip_y = self.y + sin_turret * (current_radius + arrow_extend)
                
                # Arrow base points (perpendicular to direction)
                base_x = self.x + cos_turret * (current_radius - base_offset)
                base_y = self.y + sin_turret * (current_radius - base_offset)
                
                # Perpendicular vectors for arrow base (cache calculations)
                perp_rad = turret_rad + math.pi / 2
                cos_perp = math.cos(perp_rad)
                sin_perp = math.sin(perp_rad)
                base1_x = base_x + cos_perp * arrow_width / 2
                base1_y = base_y + sin_perp * arrow_width / 2
                base2_x = base_x - cos_perp * arrow_width / 2
                base2_y = base_y - sin_perp * arrow_width / 2
                
                # Draw line from center to arrow base for better visibility
                turret_color = (255, 255, 100) if is_ready_to_fire else (255, 200, 50)
                line_start_x = self.x + cos_turret * (current_radius * 0.3)
                line_start_y = self.y + sin_turret * (current_radius * 0.3)
                pygame.draw.line(
                    screen, turret_color,
                    (int(line_start_x), int(line_start_y)),
                    (int(base_x), int(base_y)), 2
                )
                
                # Draw larger triangle arrow (bright yellow/orange)
                pygame.draw.polygon(screen, turret_color, [
                    (int(arrow_tip_x), int(arrow_tip_y)),
                    (int(base1_x), int(base1_y)),
                    (int(base2_x), int(base2_y))
                ])
                
                # Draw outline for better visibility
                pygame.draw.polygon(screen, (255, 255, 255), [
                    (int(arrow_tip_x), int(arrow_tip_y)),
                    (int(base1_x), int(base1_y)),
                    (int(base2_x), int(base2_y))
                ], 1)
        
        elif self.type == "aggressive":
            # Jagged/warning appearance - draw warning stripes (cache calculations)
            num_stripes = 6
            stripe_angle_base = self.pulse_phase * 15
            for i in range(num_stripes):
                stripe_angle = (i * 360 / num_stripes) + stripe_angle_base
                stripe_rad = angle_to_radians(stripe_angle)
                cos_stripe = math.cos(stripe_rad)
                sin_stripe = math.sin(stripe_rad)
                stripe_x1 = self.x + cos_stripe * current_radius * 0.3
                stripe_y1 = self.y + sin_stripe * current_radius * 0.3
                stripe_x2 = self.x + cos_stripe * current_radius * 0.9
                stripe_y2 = self.y + sin_stripe * current_radius * 0.9
                # Alternate colors for warning effect
                stripe_color = (255, 200, 100) if i % 2 == 0 else (255, 100, 50)
                pygame.draw.line(screen, stripe_color,
                               (int(stripe_x1), int(stripe_y1)),
                               (int(stripe_x2), int(stripe_y2)), 2)
        
        # Draw geometric patterns (cache calculations)
        # Radial lines from center (all types)
        num_radial = 6
        radial_angle_base = self.pulse_phase * 5
        radial_length = current_radius * 0.4
        for i in range(num_radial):
            radial_angle = (i * 360 / num_radial) + radial_angle_base
            radial_rad = angle_to_radians(radial_angle)
            cos_radial = math.cos(radial_rad)
            sin_radial = math.sin(radial_rad)
            radial_x = self.x + cos_radial * radial_length
            radial_y = self.y + sin_radial * radial_length
            pattern_color = tuple(max(0, c - 40) for c in color)
            pygame.draw.line(screen, pattern_color,
                           (int(self.x), int(self.y)),
                           (int(radial_x), int(radial_y)), 1)
        
        # Draw movement direction indicator for dynamic enemies (white line)
        if self.type != "static":
            angle_rad = angle_to_radians(self.angle)
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            indicator_x = self.x + cos_angle * current_radius
            indicator_y = self.y + sin_angle * current_radius
            # Always use white for movement direction indicator
            indicator_color = (255, 255, 255)
            pygame.draw.line(
                screen, indicator_color,
                (int(self.x), int(self.y)),
                (int(indicator_x), int(indicator_y)), 2
            )


def create_enemies(level: int, spawn_positions: List[Tuple[float, float]]) -> List[Enemy]:
    """Create enemies for a level.
    
    Args:
        level: Current level number.
        spawn_positions: List of valid spawn positions.
        
    Returns:
        List of Enemy instances.
    """
    # Get enemy count and distribution from level rules
    enemy_count = level_rules.get_enemy_count(level)
    enemy_count = min(enemy_count, len(spawn_positions))
    
    distribution = level_rules.get_enemy_type_distribution(level, enemy_count)
    
    enemies = []
    used_positions = []
    
    # Shuffle positions
    available_positions = spawn_positions.copy()
    random.shuffle(available_positions)
    
    # Create static enemies
    for i in range(min(distribution['static'], len(available_positions))):
        pos = available_positions[i]
        enemies.append(Enemy(pos, "static", level))
        used_positions.append(pos)
    
    # Create dynamic enemies (patrol and aggressive)
    remaining_positions = [p for p in available_positions if p not in used_positions]
    
    for i in range(min(distribution['patrol'], len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "patrol", level))
    
    remaining_positions = [p for p in remaining_positions if p not in [e.get_pos() for e in enemies]]
    for i in range(min(distribution['aggressive'], len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "aggressive", level))
    
    return enemies

