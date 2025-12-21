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
        """Initialize replay enemy ship."""
        super().__init__(start_pos, config.REPLAY_ENEMY_SIZE)
        self.command_recorder = command_recorder
        self.current_replay_index = 0
        self.fire_cooldown: int = 0
        # Tentacle particle system - one list per tentacle
        self.tentacle_particles: List[List[dict]] = [[] for _ in range(self.TENTACLE_COUNT)]
        self.tentacle_max_particles = 30
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the replay enemy ship."""
        return config.SHIP_MAX_SPEED * 0.3
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update replay enemy ship and execute replay commands."""
        replay_commands = self.command_recorder.get_replay_commands()
        command_count = self.command_recorder.get_command_count()
        
        if command_count < config.REPLAY_ENEMY_WINDOW_SIZE:
            super().update(dt)
            self._update_tentacle_particles(dt)
            return
        
        if replay_commands:
            cmd_type = replay_commands[self.current_replay_index]
            self._execute_command(cmd_type, player_pos)
            self.current_replay_index = (self.current_replay_index + 1) % len(replay_commands)
        
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        super().update(dt)
        self._update_tentacle_particles(dt)
    
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
    
    def _update_tentacle_particles(self, dt: float) -> None:
        """Update tentacle particle system based on movement."""
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        spread_rad = math.radians(self.TENTACLE_SPREAD_ANGLE)
        
        if speed > 0.01:
            trail_angle_rad = math.atan2(self.vy, self.vx) + math.pi
        else:
            trail_angle_rad = angle_to_radians(self.angle) + math.pi
        
        particle_spawn_rate = max(2, int(speed * 4) + 2) if speed > 0.01 else 3
        
        for tentacle_idx in range(self.TENTACLE_COUNT):
            base_angle_offset = (tentacle_idx / self.TENTACLE_COUNT) * spread_rad - spread_rad / 2
            tentacle_base_angle = trail_angle_rad + base_angle_offset
            base_x = math.cos(tentacle_base_angle) * body_radius
            base_y = math.sin(tentacle_base_angle) * body_radius
            
            particles_needed = self.tentacle_max_particles - len(self.tentacle_particles[tentacle_idx])
            if particles_needed > 0:
                for _ in range(min(particle_spawn_rate, particles_needed)):
                    particle_offset_angle = tentacle_base_angle + random.uniform(-0.2, 0.2)
                    
                    if speed > 0.01:
                        particle_vx = -math.cos(particle_offset_angle) * speed * 0.25
                        particle_vy = -math.sin(particle_offset_angle) * speed * 0.25
                    else:
                        particle_vx = -math.cos(particle_offset_angle) * 1.0
                        particle_vy = -math.sin(particle_offset_angle) * 1.0
                    
                    self.tentacle_particles[tentacle_idx].append({
                        'x': base_x,
                        'y': base_y,
                        'vx': particle_vx,
                        'vy': particle_vy,
                        'life': 60,
                        'size': random.uniform(4.0, 6.0)
                    })
        
        # Update existing particles
        for tentacle_particles in self.tentacle_particles:
            for particle in tentacle_particles:
                particle['vx'] *= 0.96
                particle['vy'] *= 0.96
                particle['x'] += particle['vx'] * dt
                particle['y'] += particle['vy'] * dt
                particle['life'] -= 1
            tentacle_particles[:] = [p for p in tentacle_particles if p['life'] > 0]
    
    def _draw_eye(
        self,
        screen: pygame.Surface,
        eye_pos: Tuple[float, float],
        eye_size: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw an eye with highlight at the specified relative position."""
        eye_x, eye_y = self._rotate_and_translate_point(eye_pos, cos_angle, sin_angle)
        pygame.draw.circle(screen, self.EYE_COLOR, (eye_x, eye_y), int(eye_size))
        
        highlight_offset = eye_size * self.EYE_HIGHLIGHT_OFFSET_MULTIPLIER
        highlight_pos = (eye_pos[0] - highlight_offset, eye_pos[1] - highlight_offset)
        highlight_x, highlight_y = self._rotate_and_translate_point(highlight_pos, cos_angle, sin_angle)
        pygame.draw.circle(screen, self.EYE_HIGHLIGHT_COLOR, (highlight_x, highlight_y),
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
        
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), body_radius, base_color,
            glow_radius=self.radius * self.BODY_GLOW_RADIUS_MULTIPLIER,
            intensity=config.SHIP_GLOW_INTENSITY * self.BODY_GLOW_INTENSITY_MULTIPLIER
        )
        
        pygame.draw.circle(screen, base_color, (int(self.x), int(self.y)), int(body_radius))
        pygame.draw.circle(screen, self.OUTLINE_COLOR, (int(self.x), int(self.y)), int(body_radius), 2)
        
        eye_size = self.radius * self.EYE_SIZE_MULTIPLIER
        eye_spacing = self.radius * self.EYE_SPACING_MULTIPLIER
        eye_forward_offset = body_radius * self.EYE_FORWARD_OFFSET_MULTIPLIER
        
        left_eye_pos = (eye_forward_offset, -eye_spacing * 0.5)
        right_eye_pos = (eye_forward_offset, eye_spacing * 0.5)
        self._draw_eye(screen, left_eye_pos, eye_size, cos_angle, sin_angle)
        self._draw_eye(screen, right_eye_pos, eye_size, cos_angle, sin_angle)
    
    def _draw_tentacles(self, screen: pygame.Surface) -> None:
        """Draw tentacles as streaming particle trails."""
        body_radius = self.radius * self.BODY_RADIUS_MULTIPLIER
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        
        if speed > 0.01:
            trail_angle_rad = math.atan2(self.vy, self.vx) + math.pi
        else:
            trail_angle_rad = angle_to_radians(self.angle) + math.pi
        
        spread_rad = math.radians(self.TENTACLE_SPREAD_ANGLE)
        
        for tentacle_idx, tentacle_particles in enumerate(self.tentacle_particles):
            base_angle_offset = (tentacle_idx / self.TENTACLE_COUNT) * spread_rad - spread_rad / 2
            tentacle_base_angle = trail_angle_rad + base_angle_offset
            base_x = self.x + math.cos(tentacle_base_angle) * body_radius
            base_y = self.y + math.sin(tentacle_base_angle) * body_radius
            
            if not tentacle_particles:
                stub_length = body_radius * 0.5
                stub_x = base_x - math.cos(tentacle_base_angle) * stub_length
                stub_y = base_y - math.sin(tentacle_base_angle) * stub_length
                pygame.draw.line(screen, (200, 140, 255), 
                               (int(base_x), int(base_y)), 
                               (int(stub_x), int(stub_y)), 3)
                continue
            
            sorted_particles = sorted(tentacle_particles, key=lambda p: p['life'], reverse=True)
            prev_x, prev_y = base_x, base_y
            
            for particle in sorted_particles:
                particle_x = self.x + particle['x']
                particle_y = self.y + particle['y']
                life_ratio = particle['life'] / 60.0
                width = max(4, int(8 * life_ratio))
                color = self._get_tentacle_color(life_ratio)
                
                pygame.draw.line(screen, color, 
                               (int(prev_x), int(prev_y)), 
                               (int(particle_x), int(particle_y)), width)
                pygame.draw.circle(screen, color, 
                                 (int(particle_x), int(particle_y)), 
                                 max(3, int(6 * life_ratio)))
                
                prev_x, prev_y = particle_x, particle_y
    
    def _get_tentacle_color(self, life_ratio: float) -> Tuple[int, int, int]:
        """Get color for tentacle particle based on life ratio."""
        life_ratio = max(0.0, min(1.0, life_ratio))
        if life_ratio > 0.7:
            return (220, 160, 255)
        elif life_ratio > 0.4:
            return (200, 130, 255)
        elif life_ratio > 0.2:
            return (180, 110, 240)
        else:
            return (160, 90, 220)
    
