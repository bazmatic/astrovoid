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
    
    
    # Drawing constants (lengths are multiples of the ship radius, in local
    # coordinates: x along the facing direction, y across it)
    MANTLE_TIP_X = 1.0  # Pointed front of the mantle
    MANTLE_BASE_X = -0.3  # Open collar at the back of the mantle
    MANTLE_HALF_WIDTH = 0.46
    MANTLE_PROFILE_POINTS = 14  # Outline points per side
    MANTLE_CONTRACT_WIDTH = 0.22  # Width lost at full contraction
    MANTLE_CONTRACT_STRETCH = 0.08  # Length gained at full contraction
    MANTLE_IDLE_CONTRACTION = 0.25  # Breathing depth when not thrusting
    FIN_START = 0.5  # Fin span along the mantle (0 = collar, 1 = tip)
    FIN_END = 0.97
    FIN_WIDTH = 0.42
    FIN_POINTS = 9
    HEAD_X = -0.45
    HEAD_RADIUS = 0.3
    TENTACLE_COUNT = 8  # Number of tentacles
    LONG_TENTACLE_INDICES = (2, 5)  # The two feeding tentacles with glowing clubs
    TENTACLE_SEGMENTS = 6
    LONG_TENTACLE_SEGMENTS = 10
    TENTACLE_LENGTH = 1.3  # Length of a regular arm
    TENTACLE_ANCHOR_X = -0.62
    TENTACLE_ANCHOR_SPREAD = 0.2  # Half-width of the row of arm roots
    TENTACLE_SPREAD_ANGLE = 50  # Degrees - fan half-angle of the relaxed arms
    TENTACLE_JET_CLOSE = 0.75  # How far the fan closes at full jet
    TENTACLE_WIGGLE_ANGLE = 28  # Degrees - travelling wave amplitude at the tips
    TENTACLE_STIFFNESS_BASE = 0.45  # Pull towards the rest pose at the root
    TENTACLE_STIFFNESS_TIP = 0.2  # ... and at the tip
    TENTACLE_BASE_HALF_WIDTH = 0.085
    TENTACLE_TIP_HALF_WIDTH = 0.02
    TENTACLE_CLUB_RADIUS = 0.11
    PULSE_SPEED = 0.07  # Idle animation speed in radians per frame
    JET_PULSE_SPEED = 0.2  # Extra animation speed at full jet
    JET_GAIN = 0.12  # Jet added per thrust
    JET_DECAY = 0.94  # Jet kept per frame
    BODY_GLOW_INTENSITY_MULTIPLIER = 1.2
    BODY_GLOW_RADIUS_MULTIPLIER = 1.8
    SPOT_ROWS = (-0.5, 0.0, 0.5)  # Rows of light spots across the mantle width
    SPOTS_PER_ROW = 5
    SPOT_RADIUS = 0.055
    SPOT_COLOR = (110, 255, 235)  # Bioluminescent teal
    SHADOW_COLOR = (20, 10, 50)
    EYE_SIZE_MULTIPLIER = 0.2
    EYE_SPACING_MULTIPLIER = 0.56
    EYE_HIGHLIGHT_OFFSET_MULTIPLIER = 0.6  # Offset multiplier for eye highlight (closer to edge for visibility)
    EYE_HIGHLIGHT_SIZE_RATIO = 0.3
    EYE_COLOR = (255, 0, 0)
    EYE_HIGHLIGHT_COLOR = (255, 150, 150)
    PUPIL_COLOR = (40, 0, 10)
    PUPIL_SIZE_RATIO = 0.45
    MAX_SPEED_MULTIPLIER = 0.3
    # Blink animation constants
    BLINK_INTERVAL_MIN = 180  # Minimum frames between blinks (3 seconds at 60 FPS)
    BLINK_INTERVAL_MAX = 480  # Maximum frames between blinks (8 seconds at 60 FPS)
    BLINK_DURATION = 30  # Frames for a single blink (0.5 seconds at 60 FPS) - much slower
    BLINK_CLOSE_FRAMES = 10  # Frames to close (first half of blink)
    BLINK_OPEN_FRAMES = 10  # Frames to open (second half of blink)
    EYELID_COLOR = (100, 60, 200)  # Color for eyelids (darker purple to match body)
    EYELID_SLANT_ANGLE = 15  # Degrees - angle of slant for slanted eye shape

    def __init__(self, start_pos: Tuple[float, float], command_recorder: CommandRecorder):
        """Initialize replay enemy ship."""
        super().__init__(start_pos, config.REPLAY_ENEMY_SIZE)
        self.angle = random.uniform(0, 360)  # Random starting orientation
        self.command_recorder = command_recorder
        self.current_replay_index = 0
        self.fire_cooldown: int = 0
        self.pulse_phase: float = 0.0  # Animation phase for mantle and tentacles
        self.jet: float = 0.0  # 0.0 drifting, 1.0 jetting hard
        # One chain of world-space points per tentacle, built on first use
        # because subclasses change the radius after construction
        self.tentacles: List[List[Tuple[float, float]]] = []
        # Blink animation state
        self.blink_timer: float = random.randint(self.BLINK_INTERVAL_MIN, self.BLINK_INTERVAL_MAX)
        self.blink_state: float = 1.0  # 1.0 = fully open, 0.0 = fully closed
        self.is_blinking: bool = False
        self.blink_frame: int = 0  # Frame counter within current blink

    def get_damage_fraction(self) -> float:
        """Return damage fraction (0.0 no damage, 1.0 destroyed)."""
        return 0.0

    def _get_blink_interval_multiplier(self, damage_fraction: float) -> float:
        """Calculate blink timer multiplier based on damage."""
        max_mult = getattr(config, "MOTHER_BOSS_BLINK_FREQUENCY_MULTIPLIER_MAX", 1.0)
        if max_mult <= 1.0 or damage_fraction <= 0.0:
            return 1.0
        return 1.0 + damage_fraction * (max_mult - 1.0)

    def _get_blink_duration_multiplier(self, damage_fraction: float) -> float:
        """Calculate blink duration multiplier based on damage."""
        max_mult = getattr(config, "MOTHER_BOSS_BLINK_DURATION_MULTIPLIER_MAX", 1.0)
        if max_mult <= 1.0 or damage_fraction <= 0.0:
            return 1.0
        return 1.0 + damage_fraction * (max_mult - 1.0)
    
    @property
    def max_speed(self) -> float:
        """Get the maximum speed for the replay enemy ship."""
        return config.SHIP_MAX_SPEED * self.MAX_SPEED_MULTIPLIER
    
    def trigger_blink(self) -> None:
        """Trigger a blink animation (e.g., when colliding with something).
        
        This will start a blink if not already blinking, or reset the blink
        if already in progress.
        """
        if not self.is_blinking:
            # Start blinking
            self.is_blinking = True
            self.blink_state = 1.0
            self.blink_frame = 0
        else:
            # If already blinking, reset to start of blink
            self.blink_frame = 0
            self.blink_state = 1.0
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None) -> None:
        """Update replay enemy ship and execute replay commands."""
        replay_commands = self.command_recorder.get_replay_commands()
        command_count = self.command_recorder.get_command_count()
        
        # Update blink animation
        damage_fraction = self.get_damage_fraction()
        interval_multiplier = self._get_blink_interval_multiplier(damage_fraction)

        if not self.is_blinking:
            # Countdown to next blink
            if self.blink_timer > 0:
                self.blink_timer = max(0.0, self.blink_timer - interval_multiplier)
            else:
                # Start blinking
                self.is_blinking = True
                self.blink_state = 1.0
                self.blink_frame = 0
        else:
            # Currently blinking - update blink state
            self.blink_frame += 1
            
            duration_multiplier = self._get_blink_duration_multiplier(damage_fraction)
            close_frames = max(1, int(self.BLINK_CLOSE_FRAMES * duration_multiplier))
            open_frames = max(1, int(self.BLINK_OPEN_FRAMES * duration_multiplier))
            hold_frames = max(2, int(2 * duration_multiplier))

            if self.blink_frame < close_frames:
                # Closing phase: reduce blink_state from 1.0 to 0.0
                self.blink_state = 1.0 - (self.blink_frame / close_frames)
            elif self.blink_frame < close_frames + hold_frames:
                # Fully closed: hold for a short period
                self.blink_state = 0.0
            elif self.blink_frame < close_frames + hold_frames + open_frames:
                # Opening phase
                open_frame = self.blink_frame - (close_frames + hold_frames)
                self.blink_state = open_frame / open_frames
            else:
                # Blink complete
                self.is_blinking = False
                self.blink_state = 1.0
                base_interval = random.randint(self.BLINK_INTERVAL_MIN, self.BLINK_INTERVAL_MAX)
                self.blink_timer = base_interval / max(1.0, interval_multiplier)
        
        if command_count < config.REPLAY_ENEMY_WINDOW_SIZE:
            super().update(dt)
            self._update_tentacles(dt)
            return
        
        if replay_commands:
            cmd_type = replay_commands[self.current_replay_index]
            self._execute_command(cmd_type, player_pos)
            self.current_replay_index = (self.current_replay_index + 1) % len(replay_commands)
        
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        super().update(dt)
        self._update_tentacles(dt)
    
    def apply_thrust(self) -> bool:
        """Apply thrust and kick the jet animation."""
        applied = super().apply_thrust()
        if applied:
            self.jet = min(1.0, self.jet + self.JET_GAIN)
        return applied
    
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
        """Draw an eye with highlight and blinking eyelids.
        
        The highlight mimics natural light reflection: it's positioned in the top-left
        of the eye orb in world space. As the creature rotates, the highlight moves
        around the eye to maintain this fixed world-space position, creating a realistic
        light reflection effect.
        
        Eyelids occlude the eye when blinking, with sharp corners.
        """
        # Get eye position in world space
        eye_x, eye_y = self._rotate_and_translate_point(eye_pos, cos_angle, sin_angle)
        
        glow_surf = visual_effects.create_soft_glow_surface(eye_size * 2.4, self.EYE_COLOR, 150)
        screen.blit(glow_surf, (eye_x - glow_surf.get_width() // 2, eye_y - glow_surf.get_height() // 2))
        
        # Draw eye as normal circle (always full size)
        pygame.draw.circle(screen, self.EYE_COLOR, (eye_x, eye_y), int(eye_size))
        
        # Pupil sits slightly forward so the squid looks where it is heading
        pupil_offset = eye_size * 0.25
        pygame.draw.circle(
            screen, self.PUPIL_COLOR,
            (int(eye_x + cos_angle * pupil_offset), int(eye_y + sin_angle * pupil_offset)),
            max(1, int(eye_size * self.PUPIL_SIZE_RATIO))
        )
        
        # Draw highlight only when eyes are mostly open
        if self.blink_state > 0.3:
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
        
        # Draw occluding eyelids when blinking (slanted for almond-shaped eyes)
        if self.blink_state < 1.0:
            coverage = (1.0 - self.blink_state) * eye_size
            
            # Calculate slant angle in radians (relative to body orientation)
            slant_rad = math.radians(self.EYELID_SLANT_ANGLE)
            
            # Create a surface for the eye area to clip eyelids to circle
            eye_surface_size = int(eye_size * 2) + 4
            eye_surface = pygame.Surface((eye_surface_size, eye_surface_size), pygame.SRCALPHA)
            eye_surface_center = eye_surface_size // 2
            
            # Calculate eyelid points in local coordinates (relative to eye center)
            # Top eyelid: slanted from top-left to bottom-right
            # In local coords, eye center is at (0, 0)
            eyelid_width = eye_size * 1.5  # Wide enough to cover eye
            
            # Top eyelid points in local coordinates (before rotation)
            top_eyelid_top_y = -eye_size - 1
            top_eyelid_bottom_y = -eye_size + coverage
            
            # Calculate slanted edges in local coordinates
            # Top edge: slanted line
            top_left_local_x = -eyelid_width
            top_left_local_y = top_eyelid_top_y + math.sin(slant_rad) * eyelid_width
            top_right_local_x = eyelid_width
            top_right_local_y = top_eyelid_top_y - math.sin(slant_rad) * eyelid_width
            
            # Bottom edge of top eyelid (moves down as coverage increases)
            bottom_left_local_x = top_left_local_x + math.sin(slant_rad) * coverage
            bottom_left_local_y = top_eyelid_bottom_y + math.cos(slant_rad) * coverage
            bottom_right_local_x = top_right_local_x - math.sin(slant_rad) * coverage
            bottom_right_local_y = top_eyelid_bottom_y + math.cos(slant_rad) * coverage
            
            # Rotate eyelid points by body angle and translate to eye surface center
            top_eyelid_points = []
            for local_x, local_y in [
                (top_left_local_x, top_left_local_y),
                (top_right_local_x, top_right_local_y),
                (bottom_right_local_x, bottom_right_local_y),
                (bottom_left_local_x, bottom_left_local_y)
            ]:
                # Rotate by body angle
                rotated_x = local_x * cos_angle - local_y * sin_angle
                rotated_y = local_x * sin_angle + local_y * cos_angle
                # Translate to eye surface center
                surface_x = eye_surface_center + rotated_x
                surface_y = eye_surface_center + rotated_y
                top_eyelid_points.append((int(surface_x), int(surface_y)))
            
            # Bottom eyelid points in local coordinates
            bottom_eyelid_top_y = eye_size - coverage
            bottom_eyelid_bottom_y = eye_size + 1
            
            # Top edge of bottom eyelid (slanted, moves up as coverage increases)
            bottom_top_left_local_x = -eyelid_width
            bottom_top_left_local_y = bottom_eyelid_top_y - math.cos(slant_rad) * coverage
            bottom_top_right_local_x = eyelid_width
            bottom_top_right_local_y = bottom_eyelid_top_y - math.cos(slant_rad) * coverage
            
            # Bottom edge of bottom eyelid
            bottom_bottom_left_local_x = bottom_top_left_local_x - math.sin(slant_rad) * coverage
            bottom_bottom_left_local_y = bottom_eyelid_bottom_y
            bottom_bottom_right_local_x = bottom_top_right_local_x + math.sin(slant_rad) * coverage
            bottom_bottom_right_local_y = bottom_eyelid_bottom_y
            
            # Rotate bottom eyelid points by body angle
            bottom_eyelid_points = []
            for local_x, local_y in [
                (bottom_top_left_local_x, bottom_top_left_local_y),
                (bottom_top_right_local_x, bottom_top_right_local_y),
                (bottom_bottom_right_local_x, bottom_bottom_right_local_y),
                (bottom_bottom_left_local_x, bottom_bottom_left_local_y)
            ]:
                # Rotate by body angle
                rotated_x = local_x * cos_angle - local_y * sin_angle
                rotated_y = local_x * sin_angle + local_y * cos_angle
                # Translate to eye surface center
                surface_x = eye_surface_center + rotated_x
                surface_y = eye_surface_center + rotated_y
                bottom_eyelid_points.append((int(surface_x), int(surface_y)))
            
            # Draw eyelids on eye surface
            pygame.draw.polygon(eye_surface, self.EYELID_COLOR, top_eyelid_points)
            pygame.draw.polygon(eye_surface, self.EYELID_COLOR, bottom_eyelid_points)
            
            # Create a mask to clip to circular eye area
            mask = pygame.Surface((eye_surface_size, eye_surface_size), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (eye_surface_center, eye_surface_center), int(eye_size))
            eye_surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Blit the clipped eye surface to the main screen
            screen.blit(eye_surface, (int(eye_x - eye_surface_center), int(eye_y - eye_surface_center)))
    
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
    
    
    def _to_world(self, local_x: float, local_y: float, cos_angle: float, sin_angle: float) -> Tuple[float, float]:
        """Convert a local point (in radius units) to world coordinates."""
        lx = local_x * self.radius
        ly = local_y * self.radius
        return (self.x + lx * cos_angle - ly * sin_angle, self.y + lx * sin_angle + ly * cos_angle)
    
    def _tentacle_segment_length(self) -> float:
        """Length of one tentacle segment in pixels."""
        return self.radius * self.TENTACLE_LENGTH / self.TENTACLE_SEGMENTS
    
    def _get_contraction(self) -> float:
        """Mantle contraction (0.0 relaxed, 1.0 fully squeezed)."""
        breathing = 0.5 + 0.5 * math.sin(self.pulse_phase)
        depth = self.MANTLE_IDLE_CONTRACTION + (1.0 - self.MANTLE_IDLE_CONTRACTION) * self.jet
        return breathing * depth
    
    def _update_tentacles(self, dt: float) -> None:
        """Advance the animation and drag the tentacle chains behind the body.
        
        Each chain follows its root like a towed rope, so the arms stream out
        when the squid moves and swing wide when it turns. A pull towards a
        fanned, wiggling rest pose keeps them alive when it drifts.
        """
        self.pulse_phase += dt * (self.PULSE_SPEED + self.JET_PULSE_SPEED * self.jet)
        self.jet *= self.JET_DECAY ** dt
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        rear_angle = angle_rad + math.pi
        segment = self._tentacle_segment_length()
        spread = math.radians(self.TENTACLE_SPREAD_ANGLE) * (1.0 - self.TENTACLE_JET_CLOSE * self.jet)
        spread *= 0.85 + 0.15 * math.sin(self.pulse_phase)
        wiggle = math.radians(self.TENTACLE_WIGGLE_ANGLE)
        
        if not self.tentacles:
            self.tentacles = [
                [(self.x, self.y)] * (
                    (self.LONG_TENTACLE_SEGMENTS if k in self.LONG_TENTACLE_INDICES else self.TENTACLE_SEGMENTS) + 1
                )
                for k in range(self.TENTACLE_COUNT)
            ]
        
        for k, chain in enumerate(self.tentacles):
            side = k / (self.TENTACLE_COUNT - 1) * 2.0 - 1.0  # -1.0 to 1.0 across the body
            anchor = self._to_world(
                self.TENTACLE_ANCHOR_X, side * self.TENTACLE_ANCHOR_SPREAD, cos_angle, sin_angle
            )
            # Snap to the rest pose on first use or after a jump (e.g. respawn)
            snap = distance(chain[0], anchor) > self.radius * 3
            chain[0] = anchor
            last = len(chain) - 1
            for i in range(1, len(chain)):
                t = i / last
                rest_angle = rear_angle - side * spread * (1.0 - 0.45 * t)
                rest_angle += math.sin(self.pulse_phase * 1.7 - i * 0.8 + k * 1.9) * wiggle * t
                prev_x, prev_y = chain[i - 1]
                rest_x = prev_x + math.cos(rest_angle) * segment
                rest_y = prev_y + math.sin(rest_angle) * segment
                
                dx = chain[i][0] - prev_x
                dy = chain[i][1] - prev_y
                length = math.hypot(dx, dy)
                if snap or length < 1e-6:
                    chain[i] = (rest_x, rest_y)
                    continue
                
                stiffness = self.TENTACLE_STIFFNESS_BASE + (self.TENTACLE_STIFFNESS_TIP - self.TENTACLE_STIFFNESS_BASE) * t
                # Blend the dragged position towards the rest pose, then
                # restore the segment length
                dx = dx / length * segment
                dy = dy / length * segment
                dx += (rest_x - prev_x - dx) * stiffness
                dy += (rest_y - prev_y - dy) * stiffness
                length = math.hypot(dx, dy)
                if length < 1e-6:
                    chain[i] = (rest_x, rest_y)
                else:
                    chain[i] = (prev_x + dx / length * segment, prev_y + dy / length * segment)
    
    def _mantle_half_width(self, u: float, contraction: float) -> float:
        """Half-width of the mantle (radius units) at u (0 = collar, 1 = tip)."""
        bulge = 0.82 + 0.18 * math.sin(math.pi * min(1.0, u * 1.6))
        taper = max(0.0, 1.0 - u ** 2.2) ** 0.6
        return self.MANTLE_HALF_WIDTH * bulge * taper * (1.0 - self.MANTLE_CONTRACT_WIDTH * contraction)
    
    def _mantle_x(self, u: float, contraction: float) -> float:
        """Local x (radius units) of the mantle at u (0 = collar, 1 = tip)."""
        tip_x = self.MANTLE_TIP_X * (1.0 + self.MANTLE_CONTRACT_STRETCH * contraction)
        return self.MANTLE_BASE_X + (tip_x - self.MANTLE_BASE_X) * u
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the replay enemy as a squid: finned mantle, head and trailing arms."""
        if not self.active:
            return
        
        if not self.tentacles:
            self._update_tentacles(0.0)
        
        angle_rad = angle_to_radians(self.angle)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        base_color = config.REPLAY_ENEMY_COLOR
        contraction = self._get_contraction()
        
        glow_surf = visual_effects.create_soft_glow_surface(
            self.radius * self.BODY_GLOW_RADIUS_MULTIPLIER, base_color,
            int(255 * config.SHIP_GLOW_INTENSITY * self.BODY_GLOW_INTENSITY_MULTIPLIER)
        )
        glow_x, glow_y = self._to_world(0.2, 0.0, cos_angle, sin_angle)
        screen.blit(glow_surf, (glow_x - glow_surf.get_width() // 2, glow_y - glow_surf.get_height() // 2))
        
        self._draw_tentacles(screen, base_color)
        self._draw_fins(screen, base_color, contraction, cos_angle, sin_angle)
        self._draw_head(screen, base_color, cos_angle, sin_angle)
        self._draw_mantle(screen, base_color, contraction, cos_angle, sin_angle)
        self._draw_spots(screen, base_color, contraction, cos_angle, sin_angle)
        
        eye_size = self.radius * self.EYE_SIZE_MULTIPLIER
        eye_x = self.HEAD_X * self.radius
        eye_offset = self.radius * self.EYE_SPACING_MULTIPLIER * 0.5
        self._draw_eye(screen, (eye_x, -eye_offset), eye_size, cos_angle, sin_angle)
        self._draw_eye(screen, (eye_x, eye_offset), eye_size, cos_angle, sin_angle)
    
    def _draw_tentacles(self, screen: pygame.Surface, base_color: Tuple[int, int, int]) -> None:
        """Draw each tentacle chain as a tapered ribbon with a lit centre line."""
        highlight = visual_effects.interpolate_color(base_color, (255, 255, 255), 0.35)
        base_half_width = self.radius * self.TENTACLE_BASE_HALF_WIDTH
        tip_half_width = self.radius * self.TENTACLE_TIP_HALF_WIDTH
        
        for k, chain in enumerate(self.tentacles):
            is_long = k in self.LONG_TENTACLE_INDICES
            side = k / (self.TENTACLE_COUNT - 1) * 2.0 - 1.0
            # Outer arms are darker so the bundle reads as rounded
            color = visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.45 + 0.4 * (1.0 - abs(side)))
            root_half_width = base_half_width * (0.7 if is_long else 1.0)
            
            left = []
            right = []
            last = len(chain) - 1
            for i, (px, py) in enumerate(chain):
                ax, ay = chain[max(0, i - 1)]
                bx, by = chain[min(last, i + 1)]
                tx = bx - ax
                ty = by - ay
                length = math.hypot(tx, ty) or 1.0
                t = i / last
                half_width = root_half_width + (tip_half_width - root_half_width) * t
                nx = -ty / length * half_width
                ny = tx / length * half_width
                left.append((px + nx, py + ny))
                right.append((px - nx, py - ny))
            
            pygame.draw.polygon(screen, color, left + right[::-1])
            pygame.draw.aalines(screen, highlight if is_long else color, False, chain)
            
            if is_long:
                self._draw_tentacle_club(screen, chain[-1], k)
    
    def _draw_tentacle_club(self, screen: pygame.Surface, tip: Tuple[float, float], index: int) -> None:
        """Draw the glowing club at the end of a feeding tentacle."""
        club_radius = max(1.5, self.radius * self.TENTACLE_CLUB_RADIUS)
        glow_surf = visual_effects.create_soft_glow_surface(club_radius * 3.5, self.SPOT_COLOR, 140)
        screen.blit(glow_surf, (tip[0] - glow_surf.get_width() // 2, tip[1] - glow_surf.get_height() // 2))
        flicker = 0.5 + 0.5 * math.sin(self.pulse_phase * 3.0 + index)
        color = visual_effects.interpolate_color(self.SPOT_COLOR, (255, 255, 255), flicker * 0.7)
        pygame.draw.circle(screen, color, (int(tip[0]), int(tip[1])), max(1, int(round(club_radius))))
    
    def _draw_fins(
        self,
        screen: pygame.Surface,
        base_color: Tuple[int, int, int],
        contraction: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw the two rippling fins near the mantle tip."""
        fill = visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.6)
        edge = visual_effects.interpolate_color(base_color, (255, 255, 255), 0.3)
        # Fins sweep in as the mantle squeezes
        fin_width = self.FIN_WIDTH * (1.0 - 0.35 * contraction)
        
        for sign in (-1.0, 1.0):
            outer = []
            for j in range(self.FIN_POINTS):
                s = j / (self.FIN_POINTS - 1)
                u = self.FIN_START + (self.FIN_END - self.FIN_START) * s
                ripple = 1.0 + 0.18 * math.sin(self.pulse_phase * 2.5 - s * 3.0)
                # Widest towards the rear of the fin, like a squid's rhombic fins
                lobe = math.sin(math.pi * s ** 0.75) ** 0.7
                y = self._mantle_half_width(u, contraction) * 0.6 + fin_width * lobe * ripple
                outer.append(self._to_world(self._mantle_x(u, contraction), sign * y, cos_angle, sin_angle))
            inner = [
                self._to_world(self._mantle_x(self.FIN_END, contraction), 0.0, cos_angle, sin_angle),
                self._to_world(self._mantle_x(self.FIN_START, contraction), 0.0, cos_angle, sin_angle),
            ]
            pygame.draw.polygon(screen, fill, outer + inner)
            pygame.draw.aalines(screen, edge, False, outer)
    
    def _draw_head(
        self,
        screen: pygame.Surface,
        base_color: Tuple[int, int, int],
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw the head that joins the mantle to the arms."""
        head_x, head_y = self._to_world(self.HEAD_X, 0.0, cos_angle, sin_angle)
        head_radius = self.radius * self.HEAD_RADIUS
        shade = visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.55)
        pygame.draw.circle(screen, shade, (int(head_x), int(head_y)), max(1, int(head_radius)))
        pygame.draw.circle(screen, base_color, (int(head_x), int(head_y)), max(1, int(head_radius * 0.6)))
    
    def _draw_mantle(
        self,
        screen: pygame.Surface,
        base_color: Tuple[int, int, int],
        contraction: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw the mantle as nested bands, dark at the edge and bright along the spine."""
        white = (255, 255, 255)
        layers = (
            (1.0, visual_effects.interpolate_color(self.SHADOW_COLOR, base_color, 0.55)),
            (0.8, base_color),
            (0.52, visual_effects.interpolate_color(base_color, white, 0.25)),
            (0.22, visual_effects.interpolate_color(base_color, white, 0.5)),
        )
        steps = self.MANTLE_PROFILE_POINTS
        outline = []
        for layer_index, (scale, color) in enumerate(layers):
            # Inner bands stop short of the collar and tip
            inset = 0.05 * layer_index
            left = []
            right = []
            for j in range(steps + 1):
                s = j / steps
                u = inset + (1.0 - 2.0 * inset) * s
                half_width = self._mantle_half_width(u, contraction) * scale
                if layer_index:
                    half_width *= math.sin(math.pi * s) ** 0.4
                x = self._mantle_x(u, contraction)
                left.append(self._to_world(x, -half_width, cos_angle, sin_angle))
                right.append(self._to_world(x, half_width, cos_angle, sin_angle))
            points = left + right[::-1]
            pygame.draw.polygon(screen, color, points)
            if not layer_index:
                outline = points
        
        rim = visual_effects.interpolate_color(base_color, white, 0.4)
        pygame.draw.aalines(screen, rim, True, outline)
    
    def _draw_spots(
        self,
        screen: pygame.Surface,
        base_color: Tuple[int, int, int],
        contraction: float,
        cos_angle: float,
        sin_angle: float
    ) -> None:
        """Draw light spots that pulse in a wave from the tip to the collar.
        
        Damaged bosses burn brighter, up to white-hot.
        """
        damage_fraction = self.get_damage_fraction()
        glow_factor = min(1.0, damage_fraction * config.MOTHER_BOSS_LINE_GLOW_INTENSITY_MAX)
        dim = visual_effects.interpolate_color(base_color, self.SHADOW_COLOR, 0.35)
        
        for row_index, row in enumerate(self.SPOT_ROWS):
            for j in range(self.SPOTS_PER_ROW):
                # Centre row is offset so the spots form a diamond pattern
                u = 0.14 + 0.62 * (j + (0.5 if row == 0.0 else 0.0)) / self.SPOTS_PER_ROW
                brightness = (0.5 + 0.5 * math.sin(self.pulse_phase * 2.0 + j * 1.1 + row_index * 0.5)) ** 2
                brightness = max(brightness, glow_factor)
                color = visual_effects.interpolate_color(dim, self.SPOT_COLOR, brightness)
                if glow_factor > 0:
                    color = visual_effects.interpolate_color(color, (255, 255, 255), glow_factor)
                y = row * self._mantle_half_width(u, contraction)
                spot_x, spot_y = self._to_world(self._mantle_x(u, contraction), y, cos_angle, sin_angle)
                spot_radius = self.radius * self.SPOT_RADIUS * (0.7 + 0.5 * brightness)
                pygame.draw.circle(screen, color, (int(spot_x), int(spot_y)), max(1, int(round(spot_radius))))
