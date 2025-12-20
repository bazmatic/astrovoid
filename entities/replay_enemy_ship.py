"""Replay enemy ship that replays player commands.

This module implements a replay enemy ship that inherits from RotatingThrusterShip
and continuously replays the player's commands from a fixed-size action window.
"""

import pygame
import math
import random
from typing import Tuple, Optional, List
import config
from entities.rotating_thruster_ship import RotatingThrusterShip
from entities.command_recorder import CommandRecorder, CommandType
from entities.projectile import Projectile
from rendering import visual_effects
from utils import angle_to_radians, get_angle_to_point, normalize_angle, distance


class ReplayEnemyShip(RotatingThrusterShip):
    """Enemy ship that replays player commands from a fixed-size action window.
    
    This ship continuously replays the last N actions recorded by the
    CommandRecorder, creating a "ghost" of the player's movements.
    
    Attributes:
        command_recorder: The CommandRecorder instance to get commands from.
        current_replay_index: Index of the current command being replayed.
    """
    
    # Command dispatch mapping - maps CommandType to handler method names
    # NO_ACTION requires special handling with player position, so it's handled separately
    _COMMAND_HANDLERS = {
        CommandType.ROTATE_LEFT: 'rotate_left',
        CommandType.ROTATE_RIGHT: 'rotate_right',
        CommandType.APPLY_THRUST: 'apply_thrust',
        # Note: FIRE command is not handled - replay enemy doesn't shoot
        # NO_ACTION is handled separately to rotate towards player
    }
    
    # Drawing constants
    BODY_RADIUS_MULTIPLIER = 0.6  # Circular body (octopus head)
    TENTACLE_COUNT = 4  # Number of tentacles
    TENTACLE_LENGTH_MULTIPLIER = 4
    TENTACLE_BASE_WIDTH_MULTIPLIER = 0.15
    TENTACLE_TIP_WIDTH_MULTIPLIER = 0.05
    TENTACLE_SPREAD_ANGLE = 140  # Degrees - how wide the tentacles spread
    TENTACLE_GLOW_INTENSITY_MULTIPLIER = 0.3
    BODY_GLOW_INTENSITY_MULTIPLIER = 0.5
    BODY_GLOW_RADIUS_MULTIPLIER = 0.4
    TENTACLE_GLOW_RADIUS_MULTIPLIER = 0.15
    EYE_SIZE_MULTIPLIER = 0.2
    EYE_SPACING_MULTIPLIER = 0.4
    EYE_FORWARD_OFFSET_MULTIPLIER = 0.5
    EYE_HIGHLIGHT_OFFSET_MULTIPLIER = 0.3
    EYE_HIGHLIGHT_SIZE_RATIO = 0.3
    THRUST_BASE_OFFSET_MULTIPLIER = 0.8
    OUTLINE_COLOR = (200, 150, 255)
    EYE_COLOR = (255, 0, 0)
    EYE_HIGHLIGHT_COLOR = (255, 150, 150)
    
    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize replay enemy ship.
        
        Args:
            start_pos: Starting position as (x, y) tuple.
            command_recorder: CommandRecorder instance to replay commands from.
        """
        super().__init__(start_pos, config.REPLAY_ENEMY_SIZE)
        self.command_recorder = command_recorder
        self.current_replay_index = 0  # Index of command currently being replayed
        self.fire_cooldown: int = 0  # Frames remaining until next shot
        self.next_fire_interval: int = 0  # Random interval for next shot
        # Tentacle particle system - one list per tentacle
        self.tentacle_particles: List[List[dict]] = [[] for _ in range(self.TENTACLE_COUNT)]
        self.tentacle_max_particles = 30  # Max particles per tentacle
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the replay enemy ship.
        
        Replay enemy ships have a lower max speed than the player ship.
        
        Returns:
            Maximum speed value (lower than player ship).
        """
        return config.SHIP_MAX_SPEED * 0.3 
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update replay enemy ship and execute replay commands.
        
        The replay enemy replays the last REPLAY_ENEMY_WINDOW_SIZE actions,
        starting after that many actions have been recorded.
        
        Args:
            dt: Delta time since last update.
            player_pos: Optional player position for NO_ACTION behavior (rotate towards player).
        """
        # Get current replay commands
        replay_commands = self.command_recorder.get_replay_commands()
        command_count = self.command_recorder.get_command_count()
        
        # Wait until we have at least REPLAY_ENEMY_WINDOW_SIZE actions stored
        if command_count < config.REPLAY_ENEMY_WINDOW_SIZE:
            # Not enough actions recorded yet, just update physics
            super().update(dt)
            # Still update tentacle particles even if not replaying yet
            self._update_tentacle_particles(dt)
            return
        
        # Execute the command at the current replay index
        # The replay index cycles through the window continuously
        if replay_commands:
            # Get the command at the current index
            cmd_type = replay_commands[self.current_replay_index]
            self._execute_command(cmd_type, player_pos)
            
            # Advance to the next command in the window
            # When we reach the end, loop back to the beginning
            self.current_replay_index = (self.current_replay_index + 1) % len(replay_commands)
        
        # Update fire cooldown
        self._update_fire_cooldown()
        
        # Update physics (movement, friction, collisions)
        super().update(dt)
        
        # Update tentacle particles
        self._update_tentacle_particles(dt)
    
    def _execute_command(self, command_type: CommandType, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Execute a replay command using dispatch pattern.
        
        Args:
            command_type: The command type to execute.
            player_pos: Optional player position for NO_ACTION behavior.
        """
        # Handle NO_ACTION specially - rotate towards player if position available
        if command_type == CommandType.NO_ACTION:
            if player_pos:
                self._rotate_towards_player(player_pos)
            # If no player position, do nothing
            return
        
        # Handle other commands using dispatch pattern
        handler_name = self._COMMAND_HANDLERS.get(command_type)
        if handler_name:
            handler_method = getattr(self, handler_name)
            handler_method()
    
    def _normalize_angle_diff(self, angle_diff: float) -> float:
        """Normalize angle difference to -180 to 180 range.
        
        Args:
            angle_diff: Raw angle difference in degrees.
            
        Returns:
            Normalized angle difference in -180 to 180 range.
        """
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        return angle_diff
    
    def _rotate_and_translate_point(
        self, 
        point: Tuple[float, float], 
        cos_angle: float, 
        sin_angle: float
    ) -> Tuple[int, int]:
        """Rotate and translate a point relative to ship position.
        
        Args:
            point: Relative point (x, y) in ship's local coordinate system.
            cos_angle: Cosine of ship's angle.
            sin_angle: Sine of ship's angle.
            
        Returns:
            Translated screen coordinates as (x, y) tuple.
        """
        px, py = point
        rx = px * cos_angle - py * sin_angle
        ry = px * sin_angle + py * cos_angle
        return (int(self.x + rx), int(self.y + ry))
    
    def _update_fire_cooldown(self) -> None:
        """Update fire cooldown timer and initialize if needed."""
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        # Initialize next fire interval on first call if needed
        if self.next_fire_interval == 0:
            self._reset_fire_cooldown()
    
    def _reset_fire_cooldown(self) -> None:
        """Reset fire cooldown with a random interval."""
        self.next_fire_interval = random.randint(
            config.ENEMY_FIRE_INTERVAL_MIN,
            config.ENEMY_FIRE_INTERVAL_MAX
        )
        self.fire_cooldown = self.next_fire_interval
    
    def _update_tentacle_particles(self, dt: float) -> None:
        """Update tentacle particle system based on movement.
        
        Args:
            dt: Delta time since last update.
        """
        # Calculate movement direction and speed
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        
        # Calculate base positions for tentacles around the body
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        spread_rad = math.radians(self.TENTACLE_SPREAD_ANGLE)
        
        # Determine trail direction (opposite of movement, or behind facing direction if stationary)
        if speed > 0.01:
            # Movement direction (where we're going)
            move_angle_rad = math.atan2(self.vy, self.vx)
            # Trail direction (opposite of movement)
            trail_angle_rad = move_angle_rad + math.pi
        else:
            # If stationary, tentacles trail behind the facing direction
            trail_angle_rad = angle_to_radians(self.angle) + math.pi
        
        # Add new particles for each tentacle (always spawn, more when moving)
        # Spawn rate increases with speed, but always spawn at least 2
        particle_spawn_rate = max(2, int(speed * 4) + 2) if speed > 0.01 else 3
        
        for tentacle_idx in range(self.TENTACLE_COUNT):
            # Calculate tentacle base angle (spread around the rear)
            # Tentacles are positioned around the back half of the body
            base_angle_offset = (tentacle_idx / self.TENTACLE_COUNT) * spread_rad - spread_rad / 2
            tentacle_base_angle = trail_angle_rad + base_angle_offset
            
            # Base position for this tentacle (on the body edge)
            base_x = math.cos(tentacle_base_angle) * body_radius
            base_y = math.sin(tentacle_base_angle) * body_radius
            
            # Always ensure we have some particles - spawn more aggressively
            particles_needed = self.tentacle_max_particles - len(self.tentacle_particles[tentacle_idx])
            if particles_needed > 0:
                # Add new particles (spawn multiple per frame when moving fast)
                for _ in range(min(particle_spawn_rate, particles_needed)):
                    # Add particle with some randomness for natural flow
                    particle_offset_angle = tentacle_base_angle + random.uniform(-0.2, 0.2)
                    
                    # Particle velocity: trails behind with some drag
                    if speed > 0.01:
                        # When moving: particles trail behind with velocity
                        particle_vx = -math.cos(particle_offset_angle) * speed * 0.25
                        particle_vy = -math.sin(particle_offset_angle) * speed * 0.25
                    else:
                        # When stationary: particles drift slowly backward
                        particle_vx = -math.cos(particle_offset_angle) * 1.0
                        particle_vy = -math.sin(particle_offset_angle) * 1.0
                    
                    self.tentacle_particles[tentacle_idx].append({
                        'x': base_x,  # Relative to ship position
                        'y': base_y,
                        'vx': particle_vx,
                        'vy': particle_vy,
                        'life': 60,  # Particle lifetime in frames (longer for visibility)
                        'size': random.uniform(4.0, 6.0)  # Larger particles
                    })
        
        # Update existing particles
        for tentacle_particles in self.tentacle_particles:
            for particle in tentacle_particles:
                # Apply drag (particles slow down over time)
                particle['vx'] *= 0.96
                particle['vy'] *= 0.96
                # Update position
                particle['x'] += particle['vx'] * dt
                particle['y'] += particle['vy'] * dt
                # Decrease life
                particle['life'] -= 1
            
            # Remove dead particles
            tentacle_particles[:] = [p for p in tentacle_particles if p['life'] > 0]
    
    def _get_thrust_particle_color(self, life_ratio: float, is_plume: bool = False) -> Tuple[int, int, int]:
        """Get purple-tinted color for thrust particle based on life ratio.
        
        Args:
            life_ratio: Ratio of remaining life (1.0 = full life, 0.0 = dead).
            is_plume: Whether this is for the plume (slightly different colors).
            
        Returns:
            RGB color tuple.
        """
        if is_plume:
            if life_ratio > 0.7:  # t < 0.3
                return (220, 170, 255)  # Light purple
            elif life_ratio > 0.4:  # t < 0.6
                return (180, 120, 255)  # Medium purple
            else:
                return (140, 70, 255)   # Dark purple
        else:
            if life_ratio > 0.6:
                return (200, 150, 255)  # Light purple
            elif life_ratio > 0.3:
                return (180, 100, 255)  # Medium purple
            else:
                return (150, 50, 255)   # Dark purple
    
    def _draw_eye(
        self,
        screen: pygame.Surface,
        eye_pos: Tuple[float, float],
        eye_size: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw an eye with highlight at the specified relative position.
        
        Args:
            screen: The pygame Surface to draw on.
            eye_pos: Relative eye position (x, y) in ship's local coordinate system.
            eye_size: Size of the eye in pixels.
            cos_angle: Cosine of ship's angle.
            sin_angle: Sine of ship's angle.
        """
        eye_x, eye_y = self._rotate_and_translate_point(eye_pos, cos_angle, sin_angle)
        
        # Draw eye
        pygame.draw.circle(screen, self.EYE_COLOR, (eye_x, eye_y), int(eye_size))
        
        # Draw eye highlight
        highlight_offset = eye_size * self.EYE_HIGHLIGHT_OFFSET_MULTIPLIER
        highlight_pos = (eye_pos[0] - highlight_offset, eye_pos[1] - highlight_offset)
        highlight_x, highlight_y = self._rotate_and_translate_point(highlight_pos, cos_angle, sin_angle)
        pygame.draw.circle(screen, self.EYE_HIGHLIGHT_COLOR, (highlight_x, highlight_y),
                          int(eye_size * self.EYE_HIGHLIGHT_SIZE_RATIO))
    
    def _rotate_towards_player(self, player_pos: Tuple[float, float]) -> None:
        """Rotate towards the player ship.
        
        Rotates the ship to point closer to the player's direction.
        
        Args:
            player_pos: Player position as (x, y) tuple.
        """
        # Calculate angle to player
        target_angle = get_angle_to_point((self.x, self.y), player_pos)
        
        # Calculate angle difference (normalized to -180 to 180 range)
        angle_diff = self._normalize_angle_diff(target_angle - self.angle)
        
        # Rotate towards target angle
        # Use rotation speed to rotate closer, but don't overshoot
        rotation_step = config.SHIP_ROTATION_SPEED
        if abs(angle_diff) < rotation_step:
            # Close enough, set directly
            self.angle = target_angle
        elif angle_diff > 0:
            # Rotate right (clockwise)
            self.rotate_right()
        else:
            # Rotate left (counter-clockwise)
            self.rotate_left()
    
    def _check_and_fire_at_player(self, player_pos: Tuple[float, float]) -> Optional[Projectile]:
        """Check if pointing roughly at player, apply thrust, and fire if conditions are met.
        
        Args:
            player_pos: Player position as (x, y) tuple.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        # Calculate distance to player
        dist_to_player = distance((self.x, self.y), player_pos)
        
        # Check if player is within firing range
        if dist_to_player > config.ENEMY_FIRE_RANGE:
            return None
        
        # Calculate angle to player
        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        
        # Calculate angle difference (normalized to -180 to 180 range)
        angle_diff = self._normalize_angle_diff(angle_to_player - self.angle)
        
        # Check if pointing roughly towards player (within tolerance)
        if abs(angle_diff) <= config.REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE:
            # Apply thrust when pointing at player
            self.apply_thrust()
            
            # Fire projectile if cooldown allows
            if self.fire_cooldown <= 0:
                projectile = Projectile((self.x, self.y), self.angle, is_enemy=True)
                self._reset_fire_cooldown()
                return projectile
        
        return None
    
    def get_fired_projectile(self, player_pos: Optional[Tuple[float, float]]) -> Optional[Projectile]:
        """Get a projectile fired by this replay enemy if applicable.
        
        Args:
            player_pos: Current player position.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        if not self.active or not player_pos:
            return None
        
        return self._check_and_fire_at_player(player_pos)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the replay enemy ship as an octopus with streaming tentacles.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        # Base color scheme (purple/violet for replay enemy)
        base_color = config.REPLAY_ENEMY_COLOR
        glow_color = config.REPLAY_ENEMY_COLOR
        
        # Draw tentacles first (behind the body)
        self._draw_tentacles(screen)
        
        # Draw body (circular octopus head)
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        
        # Draw glow for body
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, glow_color,
            glow_radius=self.radius * self.BODY_GLOW_RADIUS_MULTIPLIER,
            intensity=config.SHIP_GLOW_INTENSITY * self.BODY_GLOW_INTENSITY_MULTIPLIER
        )
        
        # Draw body circle
        pygame.draw.circle(screen, base_color, (int(self.x), int(self.y)), int(body_radius))
        pygame.draw.circle(screen, self.OUTLINE_COLOR, (int(self.x), int(self.y)), int(body_radius), 2)
        
        # Draw two red eyes at the front of the body
        eye_size = self.radius * self.EYE_SIZE_MULTIPLIER
        eye_spacing = self.radius * self.EYE_SPACING_MULTIPLIER
        eye_forward_offset = body_radius * self.EYE_FORWARD_OFFSET_MULTIPLIER
        
        # Draw eyes using helper method
        left_eye_pos = (eye_forward_offset, -eye_spacing * 0.5)
        right_eye_pos = (eye_forward_offset, eye_spacing * 0.5)
        self._draw_eye(screen, left_eye_pos, eye_size, cos_angle, sin_angle)
        self._draw_eye(screen, right_eye_pos, eye_size, cos_angle, sin_angle)
    
    def _draw_tentacles(self, screen: pygame.Surface) -> None:
        """Draw tentacles as streaming particle trails.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        
        # Calculate tentacle base positions (where they attach to body)
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > 0.01:
            move_angle_rad = math.atan2(self.vy, self.vx)
            trail_angle_rad = move_angle_rad + math.pi
        else:
            trail_angle_rad = angle_to_radians(self.angle) + math.pi
        
        spread_rad = math.radians(self.TENTACLE_SPREAD_ANGLE)
        
        # Draw each tentacle as a particle trail
        for tentacle_idx, tentacle_particles in enumerate(self.tentacle_particles):
            # Calculate tentacle base position (where it attaches to body)
            base_angle_offset = (tentacle_idx / self.TENTACLE_COUNT) * spread_rad - spread_rad / 2
            tentacle_base_angle = trail_angle_rad + base_angle_offset
            base_x = self.x + math.cos(tentacle_base_angle) * body_radius
            base_y = self.y + math.sin(tentacle_base_angle) * body_radius
            
            if not tentacle_particles:
                # Draw a short stub tentacle even if no particles yet
                stub_length = body_radius * 0.5
                stub_x = base_x - math.cos(tentacle_base_angle) * stub_length
                stub_y = base_y - math.sin(tentacle_base_angle) * stub_length
                color = (200, 140, 255)  # Bright purple
                pygame.draw.line(screen, color, 
                               (int(base_x), int(base_y)), 
                               (int(stub_x), int(stub_y)), 
                               3)
                continue
            
            # Sort particles by life (oldest first for proper drawing order)
            sorted_particles = sorted(tentacle_particles, key=lambda p: p['life'], reverse=True)
            
            # Draw tentacle as connected segments from body to tip
            if len(sorted_particles) > 0:
                # Start from body attachment point
                prev_x = base_x
                prev_y = base_y
                
                # Draw segments connecting body to particles
                for particle in sorted_particles:
                    particle_x = self.x + particle['x']
                    particle_y = self.y + particle['y']
                    life_ratio = particle['life'] / 60.0
                    
                    # Make tentacles much thicker and brighter
                    # Width tapers from base (thick) to tip (thin)
                    width = max(4, int(8 * life_ratio))  # Much thicker - 4-8 pixels
                    
                    # Use bright, saturated color
                    color = self._get_tentacle_color(life_ratio)
                    
                    # Draw thick segment
                    pygame.draw.line(screen, color, 
                                   (int(prev_x), int(prev_y)), 
                                   (int(particle_x), int(particle_y)), 
                                   width)
                    
                    # Draw particle as a bright circle for extra visibility
                    particle_size = max(3, int(6 * life_ratio))
                    pygame.draw.circle(screen, color, 
                                     (int(particle_x), int(particle_y)), 
                                     particle_size)
                    
                    prev_x = particle_x
                    prev_y = particle_y
    
    def _get_tentacle_color(self, life_ratio: float) -> Tuple[int, int, int]:
        """Get color for tentacle particle based on life ratio.
        
        Args:
            life_ratio: Ratio of remaining life (1.0 = full life, 0.0 = dead).
            
        Returns:
            RGB color tuple (bright purple/violet gradient).
        """
        # Bright purple/violet gradient that fades as life decreases
        # Clamp life_ratio to valid range
        life_ratio = max(0.0, min(1.0, life_ratio))
        
        # Use much brighter, more saturated colors for visibility
        if life_ratio > 0.7:
            return (220, 160, 255)  # Very bright purple
        elif life_ratio > 0.4:
            return (200, 130, 255)  # Bright purple
        elif life_ratio > 0.2:
            return (180, 110, 240)   # Medium purple
        else:
            return (160, 90, 220)  # Medium-dark purple (still visible)
    
    def on_wall_collision(self) -> None:
        """Handle wall collision - replay enemy bounces off walls.
        
        This method is called by the base class when the replay enemy collides
        with a wall. The bounce physics (velocity reflection, position correction)
        are handled by the base class. This override is intentionally empty as
        the replay enemy doesn't need special collision handling - it bounces
        based on its own position/velocity state, completely independent from
        the player ship's collisions.
        """
        # No additional handling needed - base class handles all physics
        pass
    
    def on_circle_collision(self) -> None:
        """Handle circle collision - replay enemy can collide with player.
        
        This method is called by the base class when the replay enemy collides
        with another circular entity (e.g., the player ship). The collision
        physics (push back, velocity adjustment) are handled by the base class.
        This override is intentionally empty as no special handling is needed.
        """
        # No additional handling needed - base class handles all physics
        pass
