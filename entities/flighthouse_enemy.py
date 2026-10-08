"""Flighthouse enemy that scans and spawns flockers toward the player."""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame
import config

if TYPE_CHECKING:
    from entities.base import GameEntity
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
    circle_circle_collision,
)
from utils.math_utils import apply_circle_collision_physics


class FlighthouseEnemy(GameEntity, Collidable, Drawable):
    """Stationary scanner that spawns flockers when the player is seen."""

    # Drawing constants (lengths are multiples of the radius unless noted)
    BEAM_LENGTH_FRACTION = 0.5  # Visible beam length as a fraction of the vision range
    BEAM_STEPS = 48  # Radial bands in the beam's fade
    BEAM_ALPHA = 60  # Beam alpha at the lamp
    BEAM_CORE_ALPHA = 55  # Extra alpha along the beam's centre
    BEAM_CORE_ANGLE_FRACTION = 0.35  # Width of the bright core relative to the cone
    BEAM_ALERT_BOOST = 1.6  # Beam brightness multiplier when alert
    BASE_SIDES = 8
    BASE_WALL_THICKNESS = 0.14
    HOUSING_RADIUS = 0.58
    LAMP_RADIUS = 0.26
    HOOD_POINTS = ((0.15, -0.5), (0.98, -0.3), (0.98, 0.3), (0.15, 0.5))  # Lamp hood, x along facing
    PIP_ORBIT = 1.0  # Distance of the hit point lights from the centre
    PIP_RADIUS = 0.12
    SHADOW_COLOR = (8, 25, 30)
    LAMP_COLOR = (255, 255, 200)
    ALERT_COLOR = (255, 60, 60)
    ALERT_RISE_SECONDS = 0.12  # Time to snap to full alert
    ALERT_FALL_SECONDS = 0.8  # Time to calm down again
    LAUNCH_FLASH_SECONDS = 0.35

    DEATH_DURATION = 54.0  # Frames: beam sputters, masonry breaks, lamp goes out

    _beam_cache: dict = {}

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
        self.max_hit_points = self.hit_points
        self.alert_level = 0.0  # 0.0 calm, 1.0 locked on to the player
        self.launch_flash = 0.0  # 1.0 when a flocker launches, fading to 0.0
        self._anim_time = 0.0  # seconds

    def get_pos(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def get_radius(self) -> float:
        return self.radius

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
            self.launch_flash = 1.0
        else:
            self.launch_flash = max(0.0, self.launch_flash - dt_seconds / self.LAUNCH_FLASH_SECONDS)

        self._anim_time += dt_seconds
        if player_visible:
            self.alert_level = min(1.0, self.alert_level + dt_seconds / self.ALERT_RISE_SECONDS)
        else:
            self.alert_level = max(0.0, self.alert_level - dt_seconds / self.ALERT_FALL_SECONDS)

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

    def check_circle_collision(
        self,
        other_pos: Tuple[float, float],
        other_radius: float,
        other_entity: Optional['GameEntity'] = None
    ) -> bool:
        """Check collision with another circular entity.
        
        Uses proper elastic collision physics when other_entity is provided,
        otherwise falls back to simple collision detection for backward compatibility.
        
        Note: Flighthouses are stationary (zero velocity) but still participate in physics.
        
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
            # Flighthouses are stationary (vx=0, vy=0) but still participate
            apply_circle_collision_physics(self, other_entity, config.COLLISION_RESTITUTION)
        
        return True

    def _get_beam_surface(self, color: Tuple[int, int, int]) -> pygame.Surface:
        """Get the searchlight cone for a color (cached).
        
        The cone has its apex at the left centre and points along +x. Its
        angle is the real vision cone; it fades out along its length.
        """
        length = int(config.FLIGHTHOUSE_ENEMY_VISION_RANGE * self.BEAM_LENGTH_FRACTION)
        key = (color, length, self.vision_cone_half)
        surf = self._beam_cache.get(key)
        if surf is not None:
            return surf
        
        half_rad = math.radians(self.vision_cone_half)
        height = int(2 * length * math.tan(half_rad)) + 2
        centre_y = height / 2

        def make_cone(half_angle: float, peak_alpha: int) -> pygame.Surface:
            cone = pygame.Surface((length, height), pygame.SRCALPHA)
            # Draw far-to-near so each band overwrites the fainter one behind it
            for step in range(self.BEAM_STEPS):
                reach = length * (1.0 - step / self.BEAM_STEPS)
                alpha = int(peak_alpha * (1.0 - reach / length) ** 1.5)
                if alpha <= 0:
                    continue
                spread = reach * math.tan(half_angle)
                pygame.draw.polygon(
                    cone, (*color, alpha),
                    [(0, centre_y), (reach, centre_y - spread), (reach, centre_y + spread)]
                )
            return cone

        surf = make_cone(half_rad, self.BEAM_ALPHA)
        surf.blit(make_cone(half_rad * self.BEAM_CORE_ANGLE_FRACTION, self.BEAM_CORE_ALPHA), (0, 0))
        self._beam_cache[key] = surf
        return surf

    def _draw_beam(self, screen: pygame.Surface, color: Tuple[int, int, int], strength: float) -> None:
        """Draw the searchlight cone along the facing direction."""
        if strength <= 0.0:
            return
        beam = pygame.transform.rotate(self._get_beam_surface(color), -self.angle)
        beam.set_alpha(int(255 * min(1.0, strength)))
        # The cone's apex sits at the lamp, so its centre is half a beam ahead
        angle_rad = angle_to_radians(self.angle)
        half_length = self._get_beam_surface(color).get_width() / 2
        centre = (
            int(self.x + math.cos(angle_rad) * half_length),
            int(self.y + math.sin(angle_rad) * half_length),
        )
        screen.blit(beam, beam.get_rect(center=centre))

    def _local_to_world(self, point: Tuple[float, float], cos_angle: float, sin_angle: float) -> Tuple[float, float]:
        """Convert a point in radius units (x along facing) to world coordinates."""
        lx = point[0] * self.radius
        ly = point[1] * self.radius
        # Measured from the whole-pixel centre so every part lines up
        return (int(self.x) + lx * cos_angle - ly * sin_angle, int(self.y) + lx * sin_angle + ly * cos_angle)

    def _base_outline(self, center: Tuple[int, int], radius: float, inset: int = 0) -> List[Tuple[int, int]]:
        """Corners of the base, snapped to the pixel grid.
        
        Offsets are rounded before being added to the whole-pixel centre, so
        opposite corners land on mirror-image pixels. An inset moves every
        side inwards by that many pixels, rounded separately so the wall
        between the two outlines is the same thickness on every side.
        """
        # Moving a side in by `inset` moves its corners in by this much
        corner_inset = inset / math.cos(math.pi / self.BASE_SIDES)
        points = []
        for i in range(self.BASE_SIDES):
            corner_angle = math.pi / self.BASE_SIDES + i * 2 * math.pi / self.BASE_SIDES
            cos_corner, sin_corner = math.cos(corner_angle), math.sin(corner_angle)
            points.append((
                center[0] + int(round(cos_corner * radius)) - int(round(cos_corner * corner_inset)),
                center[1] + int(round(sin_corner * radius)) - int(round(sin_corner * corner_inset)),
            ))
        return points

    def draw(self, screen) -> None:
        """Draw the flighthouse as a lighthouse seen from above.
        
        A searchlight sweeps with the real vision cone and turns red when the
        player is spotted. Lights on the base show remaining hit points.
        """
        if not self.active:
            return

        alert = self.alert_level
        base_color = config.FLIGHTHOUSE_ENEMY_COLOR
        center = (int(self.x), int(self.y))
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        # The alert beam throbs so a lock-on is hard to miss
        throb = 0.85 + 0.15 * math.sin(self._anim_time * 18.0)

        self._draw_beam(screen, base_color, 1.0 - alert)
        self._draw_beam(screen, self.ALERT_COLOR, alert * throb * self.BEAM_ALERT_BOOST)

        # Faceted base. It is drawn as a filled wall with a filled floor inset
        # in it, which keeps the wall the same thickness on every side.
        accent = visual_effects.interpolate_color(base_color, self.ALERT_COLOR, alert * throb)
        wall = max(2, int(round(self.radius * self.BASE_WALL_THICKNESS)))
        glow = visual_effects.create_soft_glow_surface(self.radius * 2.2, base_color, 70)
        screen.blit(glow, glow.get_rect(center=center))
        pygame.draw.polygon(screen, accent, self._base_outline(center, self.radius))
        pygame.draw.polygon(
            screen, visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.18),
            self._base_outline(center, self.radius, inset=wall)
        )

        # Rotating lamp housing and hood
        housing_color = visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.45)
        hood = [self._local_to_world(point, cos_angle, sin_angle) for point in self.HOOD_POINTS]
        pygame.draw.polygon(screen, housing_color, hood)
        pygame.draw.aalines(screen, accent, True, hood)
        pygame.draw.circle(screen, housing_color, center, int(self.radius * self.HOUSING_RADIUS))
        pygame.draw.circle(screen, accent, center, int(self.radius * self.HOUSING_RADIUS), 1)

        # Lens across the mouth of the hood, and the lamp itself
        lamp_color = visual_effects.interpolate_color(self.LAMP_COLOR, self.ALERT_COLOR, alert)
        flash_color = visual_effects.interpolate_color(lamp_color, (255, 255, 255), self.launch_flash)
        pygame.draw.line(screen, flash_color, hood[1], hood[2], 2)
        lamp_glow = visual_effects.create_soft_glow_surface(self.radius * (1.0 + 0.8 * alert), lamp_color, 170)
        screen.blit(lamp_glow, lamp_glow.get_rect(center=center))
        pygame.draw.circle(screen, flash_color, center, max(2, int(self.radius * self.LAMP_RADIUS)))

        # Hit point lights on the rim, drawn last so the hood never hides them
        pip_radius = max(2, int(round(self.radius * self.PIP_RADIUS)))
        unlit = visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.3)
        for i in range(self.max_hit_points):
            pip_angle = -math.pi / 2 + i * 2 * math.pi / self.max_hit_points
            pip_pos = (
                center[0] + int(round(math.cos(pip_angle) * self.radius * self.PIP_ORBIT)),
                center[1] + int(round(math.sin(pip_angle) * self.radius * self.PIP_ORBIT)),
            )
            pygame.draw.circle(screen, self.SHADOW_COLOR, pip_pos, pip_radius + 1)
            pygame.draw.circle(screen, accent if i < self.hit_points else unlit, pip_pos, pip_radius)

        if self.launch_flash > 0.0:
            self._draw_launch_flash(screen, center)

    def draw_death(self, screen: pygame.Surface) -> None:
        """Sputter out the beam, scatter the base and collapse the lamp."""
        if not self.is_dying:
            return
        progress = self.death_progress
        color = config.FLIGHTHOUSE_ENEMY_COLOR
        # A short, flickering last sweep; the dead scanner never tracks or spawns.
        beam_strength = max(0.0, 1.0 - progress / 0.3)
        if int(progress * 40) % 2 == 0:
            self._draw_beam(screen, color, beam_strength)

        breakup = max(0.0, (progress - 0.12) / 0.88)
        size = self.radius * (1.0 - breakup ** 2)
        if size < 0.5:
            return
        for index in range(self.BASE_SIDES):
            angle = (index + 0.5) * 2 * math.pi / self.BASE_SIDES
            drift = self.radius * 1.8 * breakup
            center = (self.x + math.cos(angle) * drift, self.y + math.sin(angle) * drift)
            corners = []
            for reach, offset in ((0.65, -0.5), (1.0, -0.5), (1.0, 0.5), (0.65, 0.5)):
                direction = angle + offset * 2 * math.pi / self.BASE_SIDES + breakup * 0.7
                corners.append((center[0] + math.cos(direction) * size * reach,
                                center[1] + math.sin(direction) * size * reach))
            pygame.draw.polygon(screen, color, corners)

        # The housing slumps toward the hood as the lamp briefly flares and dies.
        heading = math.radians(self.angle + 100 * breakup)
        center = (int(self.x + math.cos(heading) * self.radius * breakup * 0.6),
                  int(self.y + math.sin(heading) * self.radius * breakup * 0.6))
        housing = max(1, int(size * self.HOUSING_RADIUS))
        pygame.draw.circle(screen, self.SHADOW_COLOR, center, housing)
        pygame.draw.circle(screen, color, center, housing, 1)
        hood = [(center[0] + size * (x * math.cos(heading) - y * math.sin(heading)),
                 center[1] + size * (x * math.sin(heading) + y * math.cos(heading)))
                for x, y in self.HOOD_POINTS]
        pygame.draw.polygon(screen, color, hood, 1)
        light = max(0.0, 1.0 - progress / 0.65)
        if light > 0:
            glow = visual_effects.create_soft_glow_surface(self.radius * (1.2 + progress),
                                                         self.LAMP_COLOR, int(170 * light))
            screen.blit(glow, glow.get_rect(center=center))
            pygame.draw.circle(screen, self.LAMP_COLOR, center,
                               max(1, int(size * self.LAMP_RADIUS * light)))

    def _draw_launch_flash(self, screen: pygame.Surface, center: Tuple[int, int]) -> None:
        """Draw the ring that bursts outward when a flocker launches."""
        progress = 1.0 - self.launch_flash
        ring_radius = int(self.radius * (1.0 + 1.6 * progress))
        size = ring_radius * 2 + 6
        ring = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(
            ring, (255, 255, 255, int(220 * self.launch_flash)),
            (size // 2, size // 2), ring_radius, max(1, int(3 * self.launch_flash))
        )
        screen.blit(ring, ring.get_rect(center=center))
