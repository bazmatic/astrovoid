"""Flighthouse enemy that scans and spawns flockers toward the player."""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame
import config
from entities.base import GameEntity
from entities.collidable import Collidable
from entities.drawable import Drawable
from entities.flocker_enemy_ship import FlockerEnemyShip
from rendering import visual_effects
from utils import (
    angle_to_radians,
    distance,
    get_angle_to_point,
    line_line_collision,
    normalize_angle,
)


class FlighthouseEnemy(GameEntity, Collidable, Drawable):
    """Stationary scanner that spawns flockers when the player is seen."""

    def __init__(self, pos: Tuple[float, float], level: int = 1):
        super().__init__(pos, config.FLIGHTHOUSE_ENEMY_SIZE)
        self.angle = random.uniform(0, 360)
        self._scan_dir = 1.0  # 1 = clockwise, -1 = counter-clockwise
        self._spawn_cooldown = 0.0  # seconds
        self._had_target_last_frame = False
        self.hit_points = config.FLIGHTHOUSE_ENEMY_HIT_POINTS
        self.vision_cone_half = config.FLIGHTHOUSE_ENEMY_VISION_CONE_DEGREES * 0.5
        self.level = level
        # Get level-based spawn interval
        import level_rules
        self._spawn_interval = level_rules.get_flighthouse_spawn_interval(level)
        self._player_visible = False  # Track if player is currently visible

    def get_pos(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def get_radius(self) -> float:
        return self.radius

    def destroy(self) -> None:
        self.active = False

    def take_damage(self) -> bool:
        self.hit_points -= 1
        return self.hit_points <= 0

    def apply_momentum(self, _vx: float, _vy: float) -> None:
        """Flighthouses are anchored; momentum does not move them."""
        return

    def update(
        self,
        dt: float,
        player_pos: Optional[Tuple[float, float]] = None,
        walls: Optional[List] = None,
        spatial_grid = None
    ) -> List[FlockerEnemyShip]:
        """Update scanning/tracking and spawn flockers if the player is visible.
        
        Args:
            dt: Delta time since last update.
            player_pos: Current player position, if available.
            walls: List of wall segments for line-of-sight checking.
            spatial_grid: Optional spatial grid for optimized wall queries.
        """
        if not self.active:
            return []

        dt_seconds = dt / float(config.FPS)
        self._spawn_cooldown = max(0.0, self._spawn_cooldown - dt_seconds)

        spawned: List[FlockerEnemyShip] = []
        player_visible = False

        if player_pos is not None:
            player_visible = self._player_in_fov(player_pos, walls, spatial_grid)
            if player_visible:
                self._track_player(player_pos, dt_seconds)
                if not self._had_target_last_frame:
                    # First frame of sight: force immediate spawn
                    self._spawn_cooldown = 0.0
            else:
                self._scan(dt_seconds)
        else:
            self._scan(dt_seconds)

        if player_visible and player_pos is not None and self._spawn_cooldown <= 0.0:
            spawned.append(self._spawn_flocker(player_pos))
            self._spawn_cooldown = self._spawn_interval

        self._had_target_last_frame = player_visible
        self._player_visible = player_visible  # Store visibility state for drawing
        return spawned

    def _player_in_fov(
        self,
        player_pos: Tuple[float, float],
        walls: Optional[List] = None,
        spatial_grid = None
    ) -> bool:
        """Check if player is in field of view with line-of-sight.
        
        Args:
            player_pos: Player position.
            walls: List of wall segments for line-of-sight checking.
            spatial_grid: Optional spatial grid for optimized wall queries.
            
        Returns:
            True if player is visible (in range, in cone, and line-of-sight clear).
        """
        dist = distance((self.x, self.y), player_pos)
        if dist > config.FLIGHTHOUSE_ENEMY_VISION_RANGE:
            return False

        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        angle_diff = self._angle_diff(angle_to_player - self.angle)
        if abs(angle_diff) > self.vision_cone_half:
            return False
        
        # Check line-of-sight: line from flighthouse to player must not intersect walls
        if walls is not None:
            # Use spatial grid if available for optimization
            walls_to_check = walls
            if spatial_grid is not None:
                walls_to_check = spatial_grid.get_walls_along_path(
                    (self.x, self.y), player_pos, 0.0
                )
            
            # Check if line from flighthouse to player intersects any wall
            for wall in walls_to_check:
                # Handle both WallSegment and tuple formats
                if hasattr(wall, 'get_segment'):
                    if not wall.active:
                        continue
                    segment = wall.get_segment()
                else:
                    segment = wall
                
                # Check if line from flighthouse to player intersects this wall segment
                if line_line_collision(
                    (self.x, self.y), player_pos,
                    segment[0], segment[1]
                ):
                    return False  # Wall blocks line-of-sight
        
        return True

    def _track_player(self, player_pos: Tuple[float, float], dt_seconds: float) -> None:
        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        angle_diff = self._angle_diff(angle_to_player - self.angle)

        max_rotate = config.FLIGHTHOUSE_ENEMY_TRACK_SPEED_DEGREES_PER_SECOND * dt_seconds
        clamped = max(-max_rotate, min(max_rotate, angle_diff))
        self.angle = normalize_angle(self.angle + clamped)

    def _scan(self, dt_seconds: float) -> None:
        """Continuously rotate 360 degrees while scanning for player."""
        max_rotate = config.FLIGHTHOUSE_ENEMY_SCAN_SPEED_DEGREES_PER_SECOND * dt_seconds * self._scan_dir
        self.angle = normalize_angle(self.angle + max_rotate)

    def _spawn_flocker(self, player_pos: Tuple[float, float]) -> FlockerEnemyShip:
        flocker = FlockerEnemyShip((self.x, self.y))
        angle_to_player = get_angle_to_point((self.x, self.y), player_pos)
        flocker.angle = angle_to_player

        # Give flocker an initial push toward the player
        base_speed = config.SHIP_MAX_SPEED * config.FLOCKER_ENEMY_SPEED_MULTIPLIER
        initial_speed = base_speed * config.FLIGHTHOUSE_ENEMY_INITIAL_FLOCKER_SPEED_MULTIPLIER
        angle_rad = angle_to_radians(angle_to_player)
        flocker.vx = math.cos(angle_rad) * initial_speed
        flocker.vy = math.sin(angle_rad) * initial_speed
        return flocker

    @staticmethod
    def _angle_diff(angle: float) -> float:
        """Normalize to -180..180 for comparison."""
        angle = (angle + 180) % 360 - 180
        return angle

    def check_wall_collision(self, walls, spatial_grid=None) -> bool:
        # Flighthouses are stationary; ignore wall collisions
        return False

    def check_circle_collision(self, other_pos: Tuple[float, float], other_radius: float) -> bool:
        from utils import circle_circle_collision

        return circle_circle_collision(
            (self.x, self.y), self.radius,
            other_pos, other_radius
        )

    def draw(self, screen) -> None:
        if not self.active:
            return

        # Body with subtle pulse
        pulse = 1.0 + 0.05 * math.sin(pygame.time.get_ticks() * 0.005)
        current_radius = self.radius * pulse

        color = config.FLIGHTHOUSE_ENEMY_COLOR
        
        # Add red glow when player is visible
        if self._player_visible:
            # Draw red glow effect
            red_glow_color = (255, 50, 50)  # Bright red
            visual_effects.draw_glow_circle(
                screen, (self.x, self.y), current_radius, red_glow_color,
                glow_radius=current_radius * 0.8, intensity=0.6
            )
        
        # Normal glow
        visual_effects.draw_glow_circle(
            screen, (self.x, self.y), current_radius, color,
            glow_radius=current_radius * 0.4, intensity=0.25
        )

        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), int(current_radius))
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), int(current_radius), 2)

        # Facing line
        angle_rad = angle_to_radians(self.angle)
        line_len = current_radius * 1.3
        end_x = self.x + math.cos(angle_rad) * line_len
        end_y = self.y + math.sin(angle_rad) * line_len
        pygame.draw.line(screen, (255, 255, 180), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 3)

        # Vision cone outline (optional visual hint)
        cone_half_rad = math.radians(self.vision_cone_half)
        for sign in (-1, 1):
            edge_angle = angle_rad + cone_half_rad * sign
            edge_x = self.x + math.cos(edge_angle) * (current_radius * 1.5)
            edge_y = self.y + math.sin(edge_angle) * (current_radius * 1.5)
            pygame.draw.line(screen, (180, 255, 220), (int(self.x), int(self.y)), (int(edge_x), int(edge_y)), 1)


