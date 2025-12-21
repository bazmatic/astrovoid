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
    
    
    # Drawing constants
    BODY_RADIUS_MULTIPLIER = 0.6  # Body radius multiplier
    BODY_OVAL_WIDTH_MULTIPLIER = 1.1  # Width of oval (perpendicular to facing direction)
    BODY_OVAL_HEIGHT_MULTIPLIER = 1.0  # Height of oval (along facing direction) - makes it longer front-to-back
    TENTACLE_COUNT = 8  # Number of tentacles
    TENTACLE_SPREAD_ANGLE = 100  # Degrees - how wide the tentacles spread
    TENTACLE_BASE_LENGTH = 0.4  # Base length multiplier (times body radius)
    TENTACLE_PULSE_AMPLITUDE = 0.3  # Length pulse amplitude (30% variation)
    TENTACLE_PULSE_SPEED = 0.2  # Animation speed in radians per second
    TENTACLE_BASE_WIDTH_MULTIPLIER = 0.6  # Base width multiplier (times body radius)
    TENTACLE_TIP_WIDTH_MULTIPLIER = 0.08  # Tip width multiplier (times body radius)
    TENTACLE_COLOR = (150, 100, 255)  # Tentacle color
    BODY_GLOW_INTENSITY_MULTIPLIER = 0.5
    BODY_GLOW_RADIUS_MULTIPLIER = 0.4
    BODY_TEXTURE_LINES = 6  # Number of longitudinal curved lines
    BODY_TEXTURE_LINE_COLOR = (120, 80, 220)  # Darker purple for texture lines
    EYE_SIZE_MULTIPLIER = 0.2
    EYE_SPACING_MULTIPLIER = 0.4
    EYE_FORWARD_OFFSET_MULTIPLIER = 0.5
    EYE_HIGHLIGHT_OFFSET_MULTIPLIER = 0.6  # Offset multiplier for eye highlight (closer to edge for visibility)
    EYE_HIGHLIGHT_SIZE_RATIO = 0.3
    THRUST_BASE_OFFSET_MULTIPLIER = 0.8
    OUTLINE_COLOR = (150, 100, 255)
    EYE_COLOR = (255, 0, 0)
    EYE_HIGHLIGHT_COLOR = (255, 150, 150)
    MAX_SPEED_MULTIPLIER = 0.3

    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize replay enemy ship."""
        super().__init__(start_pos, config.REPLAY_ENEMY_SIZE)
        self.command_recorder = command_recorder
        self.current_replay_index = 0
        self.fire_cooldown: int = 0
        self.pulse_phase: float = 0.0  # Animation phase for tentacle pulsing
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the replay enemy ship."""
        return config.SHIP_MAX_SPEED * self.MAX_SPEED_MULTIPLIER
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update replay enemy ship and execute replay commands."""
        replay_commands = self.command_recorder.get_replay_commands()
        command_count = self.command_recorder.get_command_count()
        
        # Update pulse phase for tentacle animation
        self.pulse_phase += dt * self.TENTACLE_PULSE_SPEED
        
        if command_count < config.REPLAY_ENEMY_WINDOW_SIZE:
            super().update(dt)
            return
        
        if replay_commands:
            cmd_type = replay_commands[self.current_replay_index]
            self._execute_command(cmd_type, player_pos)
            self.current_replay_index = (self.current_replay_index + 1) % len(replay_commands)
        
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        super().update(dt)
    
    def _execute_command(self, command_type: CommandType, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Execute a replay command."""
        if command_type == CommandType.NO_ACTION:
            if player_pos:
                self._rotate_towards_player(player_pos)
        elif command_type == CommandType.ROTATE_LEFT:
            self.rotate_left()
        elif command_type == CommandType.ROTATE_RIGHT:
            self.rotate_right()
        elif command_type == CommandType.APPLY_THRUST:
            self.apply_thrust()
    
    def _normalize_angle_diff(self, angle_diff: float) -> float:
        """Normalize angle difference to -180 to 180 range."""
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        return angle_diff
    
    def _rotate_and_translate_point(
        self, 
        point: Tuple[float, float], 
        cos_angle: float, 
        sin_angle: float
    ) -> Tuple[int, int]:
        """Rotate and translate a point relative to ship position."""
        px, py = point
        rx = px * cos_angle - py * sin_angle
        ry = px * sin_angle + py * cos_angle
        return (int(self.x + rx), int(self.y + ry))
    
    def _reset_fire_cooldown(self) -> None:
        """Reset fire cooldown with a random interval."""
        self.fire_cooldown = random.randint(
            config.ENEMY_FIRE_INTERVAL_MIN,
            config.ENEMY_FIRE_INTERVAL_MAX
        )
    
    def _draw_eye(
        self,
        screen: pygame.Surface,
        eye_pos: Tuple[float, float],
        eye_size: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw an eye with highlight at the specified relative position.
        
        The highlight mimics natural light reflection: it's positioned in the top-left
        of the eye orb in world space. As the creature rotates, the highlight moves
        around the eye to maintain this fixed world-space position, creating a realistic
        light reflection effect.
        """
        # Get eye position in world space
        eye_x, eye_y = self._rotate_and_translate_point(eye_pos, cos_angle, sin_angle)
        pygame.draw.circle(screen, self.EYE_COLOR, (eye_x, eye_y), int(eye_size))
        
        # Calculate highlight offset in world space (fixed light source from top-left)
        # Light comes from -135° in world coordinates (top-left direction)
        # This is a FIXED angle in world space, not relative to the eye's rotation
        highlight_angle_rad = math.radians(-135)  # Top-left in world space
        highlight_offset_distance = eye_size * self.EYE_HIGHLIGHT_OFFSET_MULTIPLIER
        
        # Calculate offset in world coordinates (fixed direction, doesn't rotate with eye)
        highlight_offset_x = math.cos(highlight_angle_rad) * highlight_offset_distance
        highlight_offset_y = math.sin(highlight_angle_rad) * highlight_offset_distance
        
        # Add offset to eye world position
        highlight_x = eye_x + highlight_offset_x
        highlight_y = eye_y + highlight_offset_y
        
        pygame.draw.circle(screen, self.EYE_HIGHLIGHT_COLOR, (int(highlight_x), int(highlight_y)),
                          int(eye_size * self.EYE_HIGHLIGHT_SIZE_RATIO))
    
    def _rotate_towards_player(self, player_pos: Tuple[float, float]) -> None:
        """Rotate towards the player ship."""
        target_angle = get_angle_to_point((self.x, self.y), player_pos)
        angle_diff = self._normalize_angle_diff(target_angle - self.angle)
        
        if abs(angle_diff) < config.SHIP_ROTATION_SPEED:
            self.angle = target_angle
        elif angle_diff > 0:
            self.rotate_right()
        else:
            self.rotate_left()
    
    def _check_and_fire_at_player(self, player_pos: Tuple[float, float]) -> Optional[Projectile]:
        """Check if pointing roughly at player, apply thrust, and fire if conditions are met."""
        if distance((self.x, self.y), player_pos) > config.ENEMY_FIRE_RANGE:
            return None
        
        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        angle_diff = self._normalize_angle_diff(angle_to_player - self.angle)
        
        if abs(angle_diff) <= config.REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE:
            self.apply_thrust()
            if self.fire_cooldown <= 0:
                self._reset_fire_cooldown()
                return Projectile((self.x, self.y), self.angle, is_enemy=True)
        
        return None
    
    def get_fired_projectile(self, player_pos: Optional[Tuple[float, float]]) -> Optional[Projectile]:
        """Get a projectile fired by this replay enemy if applicable."""
        if not self.active or not player_pos:
            return None
        return self._check_and_fire_at_player(player_pos)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the replay enemy ship as an octopus with streaming tentacles."""
        if not self.active:
            return
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        base_color = config.REPLAY_ENEMY_COLOR
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        
        self._draw_tentacles(screen)
        
        # Draw oval body (longer front-to-back)
        oval_width = body_radius * 2 * self.BODY_OVAL_WIDTH_MULTIPLIER
        oval_height = body_radius * 2 * self.BODY_OVAL_HEIGHT_MULTIPLIER
        
        # Create surface for rotated oval (larger to accommodate rotation)
        surface_size = int(max(oval_width, oval_height) * 1.5) + 4
        oval_surface = pygame.Surface((surface_size, surface_size), pygame.SRCALPHA)
        surface_center = surface_size // 2
        oval_rect = pygame.Rect(
            surface_center - int(oval_width // 2),
            surface_center - int(oval_height // 2),
            int(oval_width),
            int(oval_height)
        )
        
        # Draw glow (still circular for simplicity)
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, base_color,
            glow_radius=self.radius * self.BODY_GLOW_RADIUS_MULTIPLIER,
            intensity=config.SHIP_GLOW_INTENSITY * self.BODY_GLOW_INTENSITY_MULTIPLIER
        )
        
        # Draw filled oval
        pygame.draw.ellipse(oval_surface, base_color, oval_rect)
        
        # Draw longitudinal curved texture lines
        self._draw_body_texture(oval_surface, oval_rect, surface_center)
        
        # Draw outline
        pygame.draw.ellipse(oval_surface, self.OUTLINE_COLOR, oval_rect, 2)
        
        # Rotate oval to match ship's facing direction
        rotated_surface = pygame.transform.rotate(oval_surface, -self.angle)
        rotated_rect = rotated_surface.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_surface, rotated_rect)
        
        eye_size = self.radius * self.EYE_SIZE_MULTIPLIER
        eye_spacing = self.radius * self.EYE_SPACING_MULTIPLIER
        eye_forward_offset = body_radius * self.EYE_FORWARD_OFFSET_MULTIPLIER
        
        left_eye_pos = (eye_forward_offset, -eye_spacing * 0.5)
        right_eye_pos = (eye_forward_offset, eye_spacing * 0.5)
        self._draw_eye(screen, left_eye_pos, eye_size, cos_angle, sin_angle)
        self._draw_eye(screen, right_eye_pos, eye_size, cos_angle, sin_angle)
    
    def _draw_tentacles(self, screen: pygame.Surface) -> None:
        """Draw short, stubby tentacles that pulse behind the ship."""
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        # Get the ship's facing direction (where eyes are)
        forward_angle_rad = angle_to_radians(self.angle)
        # Tentacles are behind (180 degrees opposite of facing direction)
        rear_angle_rad = forward_angle_rad + math.pi
        
        # Calculate pulse factor for length (0.7 to 1.0 range)
        length_pulse_factor = 0.7 + 0.3 * (1.0 + math.sin(self.pulse_phase)) / 2.0
        
        # Calculate pulse factor for width (more dramatic: 0.4 to 1.0 range)
        width_pulse_factor = 0.4 + 0.6 * (1.0 + math.sin(self.pulse_phase * 1.5)) / 2.0
        
        # Base tentacle length (short and stubby)
        base_length = body_radius * self.TENTACLE_BASE_LENGTH
        current_length = base_length * length_pulse_factor
        
        # Spread angle for tentacles
        spread_rad = math.radians(self.TENTACLE_SPREAD_ANGLE)
        
        for tentacle_idx in range(self.TENTACLE_COUNT):
            # Calculate tentacle angle (spread around rear direction)
            angle_offset = (tentacle_idx / self.TENTACLE_COUNT) * spread_rad - spread_rad / 2
            tentacle_angle = rear_angle_rad + angle_offset
            
            # Base position on body edge (on the rear side of the ship)
            base_x = self.x + math.cos(tentacle_angle) * body_radius
            base_y = self.y + math.sin(tentacle_angle) * body_radius
            
            # Tip position (extending further backward from base, away from ship center)
            # Extend in the same direction as tentacle_angle (which points rearward)
            tip_x = base_x + math.cos(tentacle_angle) * current_length
            tip_y = base_y + math.sin(tentacle_angle) * current_length
            
            # Width pulses more dramatically (independent of length pulse)
            base_width = body_radius * self.TENTACLE_BASE_WIDTH_MULTIPLIER
            tip_width = body_radius * self.TENTACLE_TIP_WIDTH_MULTIPLIER
            width = int(base_width * width_pulse_factor)
            width = max(int(tip_width), width)  # Ensure minimum width
            
            # Draw tentacle as a simple line
            pygame.draw.line(
                screen,
                self.TENTACLE_COLOR,
                (int(base_x), int(base_y)),
                (int(tip_x), int(tip_y)),
                width
            )
    
    def _draw_body_texture(self, surface: pygame.Surface, oval_rect: pygame.Rect, surface_center: int) -> None:
        """Draw longitudinal curved texture lines on the body for 3D effect.
        
        Args:
            surface: The surface to draw on.
            oval_rect: Rectangle defining the oval bounds.
            surface_center: Center coordinate of the surface (both x and y are the same).
        """
        oval_width = oval_rect.width
        oval_height = oval_rect.height
        center_x = center_y = surface_center
        
        # Draw curved lines that follow the oval shape longitudinally
        num_lines = self.BODY_TEXTURE_LINES
        line_spacing = oval_width / (num_lines + 1)
        
        for i in range(num_lines):
            # X position of line (spread across width)
            line_x_offset = (i + 1) * line_spacing - oval_width / 2
            
            # Create curved line using multiple segments
            num_segments = 20
            points = []
            
            for seg in range(num_segments + 1):
                # Progress along the length (0.0 to 1.0)
                t = seg / num_segments
                
                # Y position along the oval height
                y_pos = center_y - oval_height / 2 + t * oval_height
                
                # Calculate x offset that curves with the oval shape
                # Use a sine wave to create a gentle curve
                curve_amplitude = oval_width * 0.15 * math.sin(t * math.pi)
                x_pos = center_x + line_x_offset + curve_amplitude * math.sin(self.pulse_phase * 0.5 + i * 0.3)
                
                # Check if point is within oval bounds (simple ellipse check)
                dx_from_center = (x_pos - center_x) / (oval_width / 2)
                dy_from_center = (y_pos - center_y) / (oval_height / 2)
                distance_from_center = math.sqrt(dx_from_center * dx_from_center + dy_from_center * dy_from_center)
                
                if distance_from_center <= 1.0:
                    points.append((int(x_pos), int(y_pos)))
            
            # Draw dotted line
            if len(points) > 1:
                for j in range(len(points) - 1):
                    # Draw every other segment to create dotted effect
                    if j % 3 < 2:  # Draw 2 out of 3 segments
                        pygame.draw.line(
                            surface,
                            self.BODY_TEXTURE_LINE_COLOR,
                            points[j],
                            points[j + 1],
                            1
                        )
    
