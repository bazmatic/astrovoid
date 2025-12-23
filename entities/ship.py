"""Ship entity implementation.

This module implements the Ship class for the player-controlled spacecraft.
"""

import pygame
import math
import random
from typing import Tuple, List, Optional
import config
from utils import angle_to_radians
from utils.math_utils import hsv_to_rgb
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
        self.shield_active = False
        self.shield_phase = 0.0  # Phase for pulsing animation when shield is active
        self.shield_initial_timer = 60  # Frames remaining for initial shield activation (1 second at 60 FPS) - no fuel consumed during this period
        self.game_started = False  # Flag to prevent shield timer countdown until game starts
        self.gun_upgrade_level = 0  # Powerup level: 0 = base, 1 = faster fire, 2 = fan effect, 3 = super fast
        self.upgrade_glow_phase = 0.0  # Phase for pulsing glow when upgraded
        self.powerup_flash_timer = 0  # Frames remaining for powerup flash
        self.powerup_flash_phase = 0.0
    
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
        
        # Update upgrade glow phase
        if self.gun_upgrade_level > 0:
            self.upgrade_glow_phase += 0.15
            if self.upgrade_glow_phase >= 2 * math.pi:
                self.upgrade_glow_phase -= 2 * math.pi
        
        # Update powerup flash animation timer
        if self.powerup_flash_timer > 0:
            self.powerup_flash_timer -= 1
            self.powerup_flash_phase += 0.35
            if self.powerup_flash_phase >= 2 * math.pi:
                self.powerup_flash_phase -= 2 * math.pi
        
        # Update shield phase and consume fuel when shield is active
        if self.shield_active:
            self.shield_phase += 0.3  # Speed of pulse animation
            if self.shield_phase >= 2 * math.pi:
                self.shield_phase -= 2 * math.pi
            
            # Update initial shield timer (decreases each frame) - only if game has started
            if self.game_started and self.shield_initial_timer > 0:
                self.shield_initial_timer -= 1
                # After initial period, automatically deactivate shield
                if self.shield_initial_timer <= 0:
                    self.shield_active = False
            elif self.game_started:
                # Consume fuel while shield is active (only after initial period)
                self.fuel -= config.SHIELD_FUEL_CONSUMPTION_PER_FRAME * dt
                
                # Deactivate shield automatically when fuel reaches 0
                if self.fuel <= 0:
                    self.fuel = 0
                    self.shield_active = False
        
        # Manage thruster sound: stop if we were thrusting in previous frame but apply_thrust wasn't called this frame
        # was_thrusting indicates if apply_thrust was called in previous frame
        # If it was True but apply_thrust wasn't called this frame (thrusting is False), stop the sound
        if self.prev_thrusting and not was_thrusting:
            self.sound_manager.stop_thruster()
        
        # Update previous thrusting state for next frame
        # Track whether apply_thrust was called this frame (indicated by was_thrusting)
        self.prev_thrusting = was_thrusting
    
    def fire(self) -> Optional[List[Projectile]]:
        """Fire projectile(s).
        
        Returns:
            List of Projectile instances if fired (single when level 0-1, 3 when level 2+),
            None if no ammo (only when level 0).
        """
        # When upgraded (level 1+), unlimited ammo - skip ammo check and consumption
        if self.gun_upgrade_level < 1:
            if self.ammo <= 0:
                return None
            self.ammo -= config.AMMO_CONSUMPTION_PER_SHOT
        
        # Play shoot sound (better sound when level 2+)
        self.sound_manager.play_shoot(is_upgraded=(self.gun_upgrade_level >= 2))
        
        # Calculate projectile start position (slightly ahead of ship)
        angle_rad = angle_to_radians(self.angle)
        offset_x = math.cos(angle_rad) * (self.radius + 5)
        offset_y = math.sin(angle_rad) * (self.radius + 5)
        start_pos = (self.x + offset_x, self.y + offset_y)
        
        # Calculate enhancements for powerups beyond level 3
        extra_powerups = max(0, self.gun_upgrade_level - 3)
        enhanced_size_mult = 1.0
        enhanced_speed_mult = 1.0
        dynamic_color = None
        enhanced_glow_intensity = 0.4
        
        if extra_powerups > 0:
            # Calculate cumulative multipliers
            enhanced_size_mult = 1.0 + (extra_powerups * config.POWERUP_BEYOND_LEVEL_3_SIZE_INCREMENT)
            enhanced_speed_mult = 1.0 + (extra_powerups * config.POWERUP_BEYOND_LEVEL_3_SPEED_INCREMENT)
            enhanced_glow_intensity = 0.4 + (extra_powerups * config.POWERUP_BEYOND_LEVEL_3_GLOW_INTENSITY_INCREMENT)
            
            # Generate color using hue rotation
            hue = (extra_powerups * config.POWERUP_BEYOND_LEVEL_3_HUE_ROTATION) % 360
            # Use full saturation and value for vibrant colors
            dynamic_color = hsv_to_rgb(hue, 1.0, 1.0)
        
        # Fan effect (3-way spread) at level 2+
        if self.gun_upgrade_level >= 2:
            # Fire 3-way spread: center, left, right
            projectiles = []
            spread_angle = config.UPGRADED_PROJECTILE_SPREAD_ANGLE
            
            # Center projectile
            projectiles.append(Projectile(
                start_pos, self.angle, is_upgraded=True,
                enhanced_size_multiplier=enhanced_size_mult,
                enhanced_speed_multiplier=enhanced_speed_mult,
                dynamic_color=dynamic_color,
                enhanced_glow_intensity=enhanced_glow_intensity
            ))
            
            # Left projectile
            left_angle = self.angle - spread_angle
            projectiles.append(Projectile(
                start_pos, left_angle, is_upgraded=True,
                enhanced_size_multiplier=enhanced_size_mult,
                enhanced_speed_multiplier=enhanced_speed_mult,
                dynamic_color=dynamic_color,
                enhanced_glow_intensity=enhanced_glow_intensity
            ))
            
            # Right projectile
            right_angle = self.angle + spread_angle
            projectiles.append(Projectile(
                start_pos, right_angle, is_upgraded=True,
                enhanced_size_multiplier=enhanced_size_mult,
                enhanced_speed_multiplier=enhanced_speed_mult,
                dynamic_color=dynamic_color,
                enhanced_glow_intensity=enhanced_glow_intensity
            ))
            
            return projectiles
        else:
            # Single projectile (level 0 or 1)
            is_upgraded = self.gun_upgrade_level >= 1
            return [Projectile(
                start_pos, self.angle, is_upgraded=is_upgraded,
                enhanced_size_multiplier=enhanced_size_mult,
                enhanced_speed_multiplier=enhanced_speed_mult,
                dynamic_color=dynamic_color,
                enhanced_glow_intensity=enhanced_glow_intensity
            )]
    
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
    
    def activate_shield(self) -> None:
        """Activate shield (called by game logic, not directly by player)."""
        self.shield_active = True
    
    def deactivate_shield(self) -> None:
        """Deactivate shield (called by game logic, not directly by player)."""
        self.shield_active = False
    
    def is_shield_active(self) -> bool:
        """Check if shield is currently active.
        
        Returns:
            True if shield is active, False otherwise.
        """
        return self.shield_active
    
    def activate_gun_upgrade(self) -> None:
        """Activate gun upgrade (called when crystal is collected)."""
        # Increment level (no cap - unlimited powerups)
        previous_level = self.gun_upgrade_level
        self.gun_upgrade_level += 1
        if previous_level == 0:
            self.rotation_speed_multiplier = config.POWERUP_ROTATION_SPEED_MULTIPLIER
        self._start_powerup_flash()
        self.sound_manager.play_powerup_activation()
    
    def reset_gun_upgrade(self) -> None:
        """Reset gun upgrade state (called on level start)."""
        self.gun_upgrade_level = 0
        self.upgrade_glow_phase = 0.0
        self.powerup_flash_timer = 0
        self.powerup_flash_phase = 0.0
        self.rotation_speed_multiplier = 1.0
    
    def is_gun_upgraded_active(self) -> bool:
        """Check if gun upgrade is currently active.
        
        Returns:
            True if gun upgrade is active (level > 0), False otherwise.
        """
        return self.gun_upgrade_level > 0
    
    def get_gun_upgrade_level(self) -> int:
        """Get current gun upgrade level.
        
        Returns:
            Current upgrade level (0-3).
        """
        return self.gun_upgrade_level
    
    def _start_powerup_flash(self) -> None:
        """Trigger a brief flash effect when collecting a powerup."""
        self.powerup_flash_timer = config.POWERUP_FLASH_DURATION_FRAMES
        self.powerup_flash_phase = 0.0
    
    def _draw_shine_effect(
        self,
        screen: pygame.Surface,
        center_x: float,
        center_y: float,
        fade_factor: float,
        phase: float
    ) -> None:
        """Draw a pulsing shine effect (reusable for spawn shine and shield).
        
        Args:
            screen: The pygame Surface to draw on.
            center_x: X coordinate of the center.
            center_y: Y coordinate of the center.
            fade_factor: Fade factor (0.0-1.0, where 1.0 is full intensity).
            phase: Animation phase for pulsing (in radians).
        """
        # Calculate pulse size - shield should be well outside the ship for visibility
        # Start further out: pulse between 2.5x and 3.5x ship radius from center
        pulse_factor = 2.5 + 0.5 * (1.0 + math.sin(phase))
        # Shield ring starts at this radius from ship center (well outside the ship)
        shield_inner_radius = self.radius * pulse_factor
        shield_outer_radius = shield_inner_radius * 1.3  # Outer edge of shield ring
        
        # Calculate intensity (fades out over time, pulses)
        intensity = 0.6 * fade_factor * (0.7 + 0.3 * math.sin(phase * 2))
        
        # Draw shield as an outer ring only - no inner circle to keep ship visible
        shine_color = (150, 220, 255)  # Bright cyan
        
        # Draw outer glow ring (no solid inner circle)
        ring_alpha = int(255 * intensity * 0.6)
        if ring_alpha > 0:
            # Create surface for the ring
            ring_size = int(shield_outer_radius * 2.5)
            ring_surf = pygame.Surface((ring_size, ring_size), pygame.SRCALPHA)
            ring_center = ring_surf.get_width() // 2
            ring_color = (*shine_color, ring_alpha)
            
            # Draw the ring (hollow circle) at shield_inner_radius
            pygame.draw.circle(ring_surf, ring_color, (ring_center, ring_center), int(shield_inner_radius), 4)
            
            # Add a subtle outer glow by drawing additional rings
            for i in range(3):
                glow_alpha = int(ring_alpha * (0.3 - i * 0.1))
                if glow_alpha > 0:
                    glow_radius = shield_inner_radius + (i + 1) * 2
                    glow_color = (*shine_color, glow_alpha)
                    pygame.draw.circle(ring_surf, glow_color, (ring_center, ring_center), int(glow_radius), 2)
            
            screen.blit(ring_surf, (center_x - ring_center, center_y - ring_center))
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the ship with enhanced visuals.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        # Draw shield glow effect when shield is active
        if self.shield_active:
            # During initial activation, fade out over time
            if self.shield_initial_timer > 0:
                fade_factor = self.shield_initial_timer / 60.0
            else:
                fade_factor = 1.0  # Full intensity after initial period
            self._draw_shine_effect(screen, self.x, self.y, fade_factor, self.shield_phase)
        
        vertices = self.get_vertices()
        flash_factor = 0.0
        if self.powerup_flash_timer > 0:
            flash_factor = self.powerup_flash_timer / float(config.POWERUP_FLASH_DURATION_FRAMES)
        
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
        
        if flash_factor > 0.0:
            tint_factor = flash_factor * config.POWERUP_FLASH_TINT_STRENGTH
            
            def _tint(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
                return tuple(min(255, int(c + (255 - c) * tint_factor)) for c in color)
            
            color_nose = _tint(color_nose)
            color_rear = _tint(color_rear)
            glow_color = _tint(glow_color)
            glow_intensity = max(
                glow_intensity,
                config.SHIP_GLOW_INTENSITY * (1.0 + config.POWERUP_FLASH_GLOW_MULTIPLIER * flash_factor)
            )
            self._draw_shine_effect(screen, self.x, self.y, flash_factor, self.powerup_flash_phase)
        
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
        # Direction vectors used for details
        nose_vertex = vertices[0]
        angle_rad = angle_to_radians(self.angle)
        dir_x = math.cos(angle_rad)
        dir_y = math.sin(angle_rad)
        perp_x = -math.sin(angle_rad)
        perp_y = math.cos(angle_rad)
        
        # Cockpit window (small circle at front)
        cockpit_offset = 2
        cockpit_x = nose_vertex[0] - math.cos(angle_rad) * cockpit_offset
        cockpit_y = nose_vertex[1] - math.sin(angle_rad) * cockpit_offset
        pygame.draw.circle(screen, (200, 220, 255), (int(cockpit_x), int(cockpit_y)), 2)
        
        # Needle-like nose tip to clearly mark the front
        needle_length = self.radius * 0.2
        needle_half_width = self.radius * 0.14
        needle_tip = (nose_vertex[0] + dir_x * needle_length, nose_vertex[1] + dir_y * needle_length)
        needle_left = (nose_vertex[0] + perp_x * needle_half_width, nose_vertex[1] + perp_y * needle_half_width)
        needle_right = (nose_vertex[0] - perp_x * needle_half_width, nose_vertex[1] - perp_y * needle_half_width)
        pygame.draw.polygon(
            screen,
            color_nose,
            [
                (int(needle_tip[0]), int(needle_tip[1])),
                (int(needle_left[0]), int(needle_left[1])),
                (int(needle_right[0]), int(needle_right[1]))
            ]
        )
        pygame.draw.line(
            screen,
            (235, 245, 255),
            (int(nose_vertex[0]), int(nose_vertex[1])),
            (int(needle_tip[0]), int(needle_tip[1])),
            1
        )
        
        # Dual rear thrusters to clearly mark the back
        rear_vertices = [vertices[1], vertices[2]]
        rear_center = (
            (rear_vertices[0][0] + rear_vertices[1][0]) * 0.5,
            (rear_vertices[0][1] + rear_vertices[1][1]) * 0.5
        )
        thruster_spacing = self.radius * 0.35
        thruster_length = self.radius * 0.1
        thruster_width = self.radius * 0.2
        thruster_tip_width = thruster_width * 0.3
        thruster_color = color_rear
        
        for side in (-1, 1):
            lateral_offset_x = perp_x * thruster_spacing * side
            lateral_offset_y = perp_y * thruster_spacing * side
            
            front_center_x = rear_center[0] + lateral_offset_x - dir_x * self.radius * 0.1
            front_center_y = rear_center[1] + lateral_offset_y - dir_y * self.radius * 0.1
            back_center_x = front_center_x - dir_x * thruster_length
            back_center_y = front_center_y - dir_y * thruster_length
            
            corners = [
                (
                    int(front_center_x + perp_x * thruster_width),
                    int(front_center_y + perp_y * thruster_width)
                ),
                (
                    int(front_center_x - perp_x * thruster_width),
                    int(front_center_y - perp_y * thruster_width)
                ),
                (
                    int(back_center_x - perp_x * thruster_tip_width),
                    int(back_center_y - perp_y * thruster_tip_width)
                ),
                (
                    int(back_center_x + perp_x * thruster_tip_width),
                    int(back_center_y + perp_y * thruster_tip_width)
                )
            ]
            
            pygame.draw.polygon(screen, thruster_color, corners)
            pygame.draw.polygon(screen, (230, 230, 255), corners, 1)
            
            # Thruster nozzle highlight
            nozzle_tip = (back_center_x - dir_x * self.radius * 0.1, back_center_y - dir_y * self.radius * 0.1)
            pygame.draw.circle(screen, (180, 200, 235), (int(nozzle_tip[0]), int(nozzle_tip[1])), 2)
        
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
    
    def draw_ui(self, screen: pygame.Surface, font: pygame.font.Font, potential_score: Optional[float] = None, max_score: float = 100.0, level: Optional[int] = None, time_seconds: Optional[float] = None) -> None:
        """Draw ship UI (level, time, fuel, ammo, score) using circular gauges.
        
        Args:
            screen: The pygame Surface to draw on.
            font: Font to use for text rendering.
            potential_score: Current potential score (for score gauge).
            max_score: Maximum possible score (default 100).
            level: Current level number to display at top.
            time_seconds: Elapsed time in seconds to display in circular gauge.
        """
        from rendering.ui_elements import UIElementRenderer
        from rendering.number_sprite import NumberSprite
        
        # UI zone constants
        UI_ZONE_WIDTH = 320
        GAUGE_RADIUS = 60
        GAUGE_CENTER_X = UI_ZONE_WIDTH // 2  # Center of UI zone
        LEVEL_Y = 60  # Level indicator at top (needs space, so gauges start lower)
        TIME_Y = 180   # Time gauge position (create space above other gauges)
        
        # Calculate equal spacing for radial gauges
        # Start after time indicator, shift all gauges downward
        GAUGE_START_Y = TIME_Y + GAUGE_RADIUS * 2 + 50  # Push gauges farther down
        GAUGE_SPACING = 170  # Equal spacing between all radial gauges
        GAUGE_Y_POSITIONS = {
            'fuel': GAUGE_START_Y,
            'score': GAUGE_START_Y + GAUGE_SPACING,
            'ammo': GAUGE_START_Y + (GAUGE_SPACING * 2)
        }
        GUN_UPGRADE_Y = GAUGE_START_Y + (GAUGE_SPACING * 3)  # Below all gauges
        EMPTY_COLOR = (50, 50, 50)
        
        def draw_gauge(
            center_y: int,
            percentage: float,
            text: str,
            fill_color: Tuple[int, int, int],
            label_text: str,
            text_color: Tuple[int, int, int] = config.COLOR_TEXT
        ) -> None:
            """Helper to draw a gauge with common parameters."""
            UIElementRenderer.draw_circular_gauge(
                screen,
                GAUGE_CENTER_X,
                center_y,
                GAUGE_RADIUS,
                percentage,
                text,
                fill_color,
                empty_color=EMPTY_COLOR,
                text_color=text_color,
                label_text=label_text
            )
        
        # Level indicator at top (centered)
        if level is not None:
            number_sprite = NumberSprite()
            number_surface = number_sprite.render_number(level, scale=0.2)
            if number_surface:
                number_rect = number_surface.get_rect(center=(GAUGE_CENTER_X, LEVEL_Y))
                screen.blit(number_surface, number_rect)
        
        # Time gauge (circular display, no fill)
        if time_seconds is not None:
            time_text = f"{time_seconds:.1f}s"
            # Draw as a circular gauge with no fill (percentage = 0) but with a background circle
            UIElementRenderer.draw_circular_gauge(
                screen,
                GAUGE_CENTER_X,
                TIME_Y,
                GAUGE_RADIUS,
                0.0,  # No fill percentage
                time_text,
                (100, 150, 200),  # Light blue color for time
                empty_color=(50, 50, 50),
                text_color=config.COLOR_TEXT,
                label_text="TIME"
            )
        
        # Fuel gauge
        fuel_percent = max(0, min(1, self.fuel / config.INITIAL_FUEL))
        fuel_color = UIElementRenderer._calculate_percentage_color(
            fuel_percent,
            high_color=(100, 200, 100),
            medium_color=(100, 200, 100),
            low_color=(200, 100, 100),
            high_threshold=0.3,
            medium_threshold=0.3
        )
        draw_gauge(GAUGE_Y_POSITIONS['fuel'], fuel_percent, str(int(self.fuel)), fuel_color, "FUEL")
        
        # Score gauge (if provided)
        if potential_score is not None:
            score_percent = max(0, min(1, potential_score / max_score))
            score_color = UIElementRenderer._calculate_percentage_color(
                score_percent,
                high_color=(255, 215, 0),
                medium_color=(255, 150, 0),
                low_color=(255, 100, 100),
                high_threshold=0.5,
                medium_threshold=0.2
            )
            draw_gauge(GAUGE_Y_POSITIONS['score'], score_percent, str(int(potential_score)), score_color, "POWER")
        
        # Ammo gauge
        if self.gun_upgrade_level >= 1:
            ammo_percent = 1.0
            ammo_text = "∞"
            ammo_color = config.COLOR_UPGRADED_SHIP_GLOW
            ammo_text_color = config.COLOR_UPGRADED_SHIP_GLOW
        else:
            ammo_percent = max(0, min(1, self.ammo / config.INITIAL_AMMO))
            ammo_text = str(self.ammo)
            ammo_color = (100, 200, 255)
            ammo_text_color = config.COLOR_TEXT
        
        draw_gauge(GAUGE_Y_POSITIONS['ammo'], ammo_percent, ammo_text, ammo_color, "AMMO", ammo_text_color)
        
        # Gun upgrade indicator (below gauges, centered)
        if self.gun_upgrade_level > 0:
            upgrade_text = font.render(f"GUN UPGRADE x{self.gun_upgrade_level}", True, config.COLOR_UPGRADED_SHIP_GLOW)
            text_rect = upgrade_text.get_rect(center=(GAUGE_CENTER_X, GUN_UPGRADE_Y))
            screen.blit(upgrade_text, text_rect)

