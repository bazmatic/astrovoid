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
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        # Initialize next fire interval on first call if needed
        if self.next_fire_interval == 0:
            self.next_fire_interval = random.randint(
                config.ENEMY_FIRE_INTERVAL_MIN,
                config.ENEMY_FIRE_INTERVAL_MAX
            )
            self.fire_cooldown = self.next_fire_interval
        
        # Update physics (movement, friction, collisions)
        super().update(dt)
    
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
    
    def _rotate_towards_player(self, player_pos: Tuple[float, float]) -> None:
        """Rotate towards the player ship.
        
        Rotates the ship to point closer to the player's direction.
        
        Args:
            player_pos: Player position as (x, y) tuple.
        """
        # Calculate angle to player
        target_angle = get_angle_to_point((self.x, self.y), player_pos)
        
        # Calculate angle difference (normalized to -180 to 180 range)
        angle_diff = target_angle - self.angle
        # Normalize to shortest rotation path
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        
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
        """Check if pointing roughly at player and fire if conditions are met.
        
        Args:
            player_pos: Player position as (x, y) tuple.
            
        Returns:
            Projectile instance if fired, None otherwise.
        """
        # Check if cooldown expired
        if self.fire_cooldown > 0:
            return None
        
        # Calculate distance to player
        dist_to_player = distance((self.x, self.y), player_pos)
        
        # Check if player is within firing range
        if dist_to_player > config.ENEMY_FIRE_RANGE:
            return None
        
        # Calculate angle to player
        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        
        # Calculate angle difference (normalized to -180 to 180 range)
        angle_diff = angle_to_player - self.angle
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        
        # Check if pointing roughly towards player (within tolerance)
        if abs(angle_diff) <= config.REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE:
            # Fire projectile in current facing direction
            projectile = Projectile((self.x, self.y), self.angle, is_enemy=True)
            
            # Reset cooldown with random interval
            self.next_fire_interval = random.randint(
                config.ENEMY_FIRE_INTERVAL_MIN,
                config.ENEMY_FIRE_INTERVAL_MAX
            )
            self.fire_cooldown = self.next_fire_interval
            
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
        """Draw the replay enemy ship with distinct visual style.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if not self.active:
            return
        
        vertices = self.get_vertices()
        
        # Use replay enemy color scheme
        color_nose = tuple(min(255, c + 30) for c in config.REPLAY_ENEMY_COLOR)
        color_rear = tuple(max(0, c - 30) for c in config.REPLAY_ENEMY_COLOR)
        glow_color = config.REPLAY_ENEMY_COLOR
        
        # Draw glow effect (slightly different from player ship)
        visual_effects.draw_glow_polygon(
            screen, vertices, glow_color,
            glow_radius=self.radius * config.SHIP_GLOW_RADIUS_MULTIPLIER * 0.8,
            intensity=config.SHIP_GLOW_INTENSITY * 0.7
        )
        
        # Draw gradient fill (nose to rear)
        visual_effects.draw_gradient_polygon(
            screen, vertices, color_nose, color_rear,
            start_vertex=0, end_vertex=1
        )
        
        # Draw outline to distinguish from player ship
        pygame.draw.polygon(screen, (200, 150, 255), vertices, 2)
        
        # Draw distinctive marker (small circle) to indicate it's a replay
        center_x = int(self.x)
        center_y = int(self.y)
        pygame.draw.circle(screen, (255, 200, 255), (center_x, center_y), 3)
        
        # Draw thrust visualization if thrusting
        if self.thrusting or len(self.thrust_particles) > 0:
            angle_rad = angle_to_radians(self.angle)
            base_x = self.x - math.cos(angle_rad) * self.radius * 0.8
            base_y = self.y - math.sin(angle_rad) * self.radius * 0.8
            
            # Draw particle trail
            for particle in self.thrust_particles:
                particle_x = self.x + particle['x']
                particle_y = self.y + particle['y']
                life_ratio = particle['life'] / config.THRUST_PLUME_LENGTH
                
                # Purple-tinted thrust particles
                if life_ratio > 0.6:
                    color = (200, 150, 255)  # Light purple
                elif life_ratio > 0.3:
                    color = (180, 100, 255)  # Medium purple
                else:
                    color = (150, 50, 255)   # Dark purple
                
                size = int(particle['size'] * life_ratio)
                if size > 0:
                    pygame.draw.circle(screen, color, 
                                     (int(particle_x), int(particle_y)), size)
            
            # Draw cone-shaped thrust plume
            speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
            plume_length = min(config.THRUST_PLUME_LENGTH, speed * 2)
            for i in range(config.THRUST_PLUME_PARTICLES):
                t = i / config.THRUST_PLUME_PARTICLES
                plume_x = base_x - math.cos(angle_rad) * plume_length * t
                plume_y = base_y - math.sin(angle_rad) * plume_length * t
                
                size = int(4 * (1 - t))
                if size > 0:
                    # Purple-tinted gradient
                    if t < 0.3:
                        color = (220, 170, 255)  # Light purple
                    elif t < 0.6:
                        color = (180, 120, 255)  # Medium purple
                    else:
                        color = (140, 70, 255)   # Dark purple
                    
                    pygame.draw.circle(screen, color,
                                     (int(plume_x), int(plume_y)), size)
    
    def on_wall_collision(self) -> None:
        """Handle wall collision - replay enemy bounces off walls.
        
        This method is called when the replay enemy collides with a wall.
        The bounce physics are handled by the base class. This override
        ensures the replay enemy handles collisions independently from
        the player ship - bounce events are physics responses, not commands.
        """
        # Base class handles physics (velocity reflection, position correction)
        # The replay enemy bounces based on its own position/velocity state,
        # completely independent from the player ship's collisions
        pass
    
    def on_circle_collision(self) -> None:
        """Handle circle collision - replay enemy can collide with player."""
        # Base class handles physics
        pass
