"""Main game loop and state management."""

import pygame
import math
import time
import random
import os
from typing import List, Optional, Tuple
import config
from entities.ship import Ship
from maze.generator import Maze
from entities.enemy import Enemy, create_enemies
import level_rules
import level_config
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.split_boss import SplitBoss
from entities.projectile import Projectile
from entities.powerup_crystal import PowerupCrystal
from entities.command_recorder import CommandRecorder, CommandType
from input import InputHandler
from scoring.system import ScoringSystem
from profiles import ProfileManager
from rendering import Renderer
from rendering.ui_elements import AnimatedStarRating, StarIndicator, GameIndicators
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon
from rendering.visual_effects import draw_button_glow
from rendering.main_menu import MainMenu
from rendering.level_complete_menu import LevelCompleteMenu
from rendering.profile_selection_menu import ProfileSelectionMenu
from rendering.quit_confirmation_menu import QuitConfirmationMenu
from sounds import SoundManager
from states.splash_screen import SplashScreenState
from game_handlers.entity_manager import EntityManager
from game_handlers.spawn_manager import SpawnManager
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.collision_handler import CollisionHandler
from game_handlers.fire_rate_calculator import calculate_fire_cooldown
from game_handlers.state_handlers import StateHandlerRegistry
from utils.math_utils import get_angle_to_point


class Game:
    """Main game class managing state and game loop."""
    CRITICAL_WARNING_THRESHOLD = config.SETTINGS.game.criticalWarningThreshold
    
    def __init__(self, screen: pygame.Surface):
        """Initialize game."""
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.renderer = Renderer(screen)
        
        # Initialize game indicators component
        # Positioned below gauges with proper spacing
        self.game_indicators = GameIndicators(
            x=20,  # Consistent left margin
            y_start=200,  # Below gauge section with more space
            line_spacing=60,  # Much increased spacing to prevent overlap
            font=self.small_font
        )
        
        self.state = config.STATE_SPLASH
        # Check for START_LEVEL environment variable
        start_level = os.getenv('START_LEVEL')
        if start_level:
            try:
                self.initial_start_level = max(1, int(start_level))
            except ValueError:
                self.initial_start_level = None
        else:
            self.initial_start_level = None
        self.profile_manager = ProfileManager()
        self.ship: Optional[Ship] = None
        self.maze: Optional[Maze] = None
        
        # Entity management
        self.entity_manager = EntityManager()
        self.enemies = self.entity_manager.enemies
        self.replay_enemies = self.entity_manager.replay_enemies
        self.flockers = self.entity_manager.flockers
        self.flighthouses = self.entity_manager.flighthouses
        self.split_bosses = self.entity_manager.split_bosses
        self.mother_bosses = self.entity_manager.mother_bosses
        self.babies = self.entity_manager.babies
        self.eggs = self.entity_manager.eggs
        
        self.projectiles: List[Projectile] = []
        self.powerup_crystals: List[PowerupCrystal] = []
        self.scoring = ScoringSystem()
        self.sound_manager = SoundManager()  # Game-level sound manager for enemy destruction
        self.command_recorder = CommandRecorder()  # Record player commands for replay enemy
        self.input_handler = InputHandler()  # Handle keyboard input and map to commands
        
        # Game handlers
        self.spawn_manager = SpawnManager(self.entity_manager)
        self.enemy_updater = EnemyUpdater()
        self.collision_handler = CollisionHandler(
            self.sound_manager,
            self.scoring,
            self.command_recorder
        )
        self.state_handler_registry = StateHandlerRegistry()
        
        self.running = True
        self.start_time = time.time()
        self.level_complete_time = 0.0
        self.level_score_breakdown = {}
        self.completion_time_seconds = 0.0
        self.level_score_percentage = 0.0
        self.total_score_before_level = 0  # Store score before level for replay
        self.level_succeeded = False  # Track if level was completed successfully
        self.exit_explosion_active = False  # Track if exit explosion is playing
        self.exit_explosion_time = 0.0  # Time since explosion started
        self.exit_explosion_pos: Optional[Tuple[float, float]] = None  # Exit position for explosion
        self.star_animation: Optional[AnimatedStarRating] = None  # Animated star rating for level complete
        self.level_complete_quit_confirm = False  # Track quit confirmation on level complete screen
        self.player_has_moved = False  # Track if player has made their first move
        self.level_start_time = 0.0  # Time when level started (to ignore initial SPACE press)
        self.keys_pressed_at_start = set()  # Track keys that were pressed when level started
        self.star_indicator = StarIndicator(
            on_star_lost=self.sound_manager.play_star_lost,
            on_star_gained=self.sound_manager.play_star_gained
        )
        self.critical_warning_active = False
        self.game_over_active = False  # Track if game over sequence is active
        self.game_frozen = False  # Track if game action is frozen (score reached zero)
        self.game_over_start_time = 0.0  # Time when game over sequence started
        self.game_over_fade_duration = 2.0  # Duration of fade to black (seconds)
        self.game_over_text_delay = 2.0  # Delay before showing "GAME OVER" text (seconds)
        self.game_over_text_duration = 2.0  # Duration to show "GAME OVER" text (seconds)
        self.profile_selection_menu = ProfileSelectionMenu(screen, self.profile_manager)
        
        # Menu UI components
        self.main_menu = MainMenu(screen)
        self.level_complete_menu = LevelCompleteMenu(screen)
        self.quit_confirmation_menu = QuitConfirmationMenu(screen)
        self.splash_screen: Optional[SplashScreenState] = None
        self._initialize_splash_screen()
        self.reset_scoring_to_profile_state()
        self.quit_confirmation_selection = 0
    
    def _initialize_splash_screen(self) -> None:
        """Initialize splash screen state."""
        self.splash_screen = SplashScreenState(None, self.screen)  # State machine not needed for simple splash
        self.splash_screen.enter()
    
    def _execute_ship_command(self, command_type: CommandType) -> None:
        """Execute a command on the player ship.
        
        Args:
            command_type: The command type to execute.
        """
        if command_type == CommandType.ROTATE_LEFT:
            self.ship.rotate_left()
        elif command_type == CommandType.ROTATE_RIGHT:
            self.ship.rotate_right()
        elif command_type == CommandType.APPLY_THRUST:
            self.ship.apply_thrust()
        elif command_type == CommandType.ACTIVATE_SHIELD:
            self.ship.activate_shield()
        # NO_ACTION and FIRE are handled separately
    
    def start_level(self) -> None:
        """Start a new level."""
        # Store total score before starting level (for replay functionality)
        self.total_score_before_level = self.scoring.get_total_score()
        
        # Ensure warning sound is silenced when a level starts
        self.sound_manager.stop_critical_warning()
        self.critical_warning_active = False

        # Reset exit explosion state
        self.exit_explosion_active = False
        self.exit_explosion_time = 0.0
        self.exit_explosion_pos = None
        
        # Reset star animation
        self.star_animation = None
        self.level_complete_quit_confirm = False
        
        # Set random seed from level config or use level number as default
        seed = level_config.get_level_seed(self.level)
        random.seed(seed)
        # Note: Seed is set before maze generation to ensure reproducible mazes
        
        # Get maze complexity from level config (None will use level-based default)
        maze_complexity = level_config.get_maze_complexity(self.level)
        
        # Get maze grid size (always returns a value, calculated if not in config)
        maze_grid_size = level_config.get_maze_grid_size(self.level)
        
        # Generate maze
        self.maze = Maze(self.level, complexity=maze_complexity, grid_size=maze_grid_size)
        
        # Create ship at start position
        self.ship = Ship(self.maze.start_pos)
        # Explicitly reset velocity and previous position to prevent visual jumps
        self.ship.vx = 0.0
        self.ship.vy = 0.0
        self.ship.prev_x = self.ship.x
        self.ship.prev_y = self.ship.y
        # Set initial angle to point towards exit (opposite corner)
        exit_pos = (self.maze.exit.x, self.maze.exit.y)
        initial_angle = get_angle_to_point(self.maze.start_pos, exit_pos)
        self.ship.angle = initial_angle
        # Activate shield at level start (initial activation, no fuel consumed)
        self.ship.shield_active = True
        # Reset gun upgrade state
        self.ship.reset_gun_upgrade()
        
        # Reset player movement flag - game loop won't start until first move
        self.player_has_moved = False
        self.ship.game_started = False  # Prevent shield timer countdown until first move
        
        # Spawn all enemies using SpawnManager
        # Check for level config overrides, fall back to defaults if not present
        enemy_counts = level_config.get_level_enemy_counts(self.level)
        if enemy_counts is None:
            enemy_counts = level_rules.get_enemy_counts(self.level)
        split_boss_count = level_config.get_level_split_boss_count(self.level)
        mother_boss_count = level_config.get_level_mother_boss_count(self.level)
        spawn_positions = self.maze.get_valid_spawn_positions(
            enemy_counts.total + enemy_counts.replay + enemy_counts.flocker + enemy_counts.flighthouse + enemy_counts.egg + split_boss_count + mother_boss_count + 5  # Extra buffer for spawn positions
        )
        self.spawn_manager.spawn_all_enemies(
            self.level, spawn_positions, self.command_recorder, enemy_counts, split_boss_count, mother_boss_count
        )
        
        # Clear projectiles and crystals
        self.projectiles = []
        self.powerup_crystals = []
        
        # Start scoring
        current_time = time.time()
        self.scoring.start_level(current_time)
        self.level_start_time = current_time  # Record level start time to ignore initial SPACE press
        
        # Reset star indicator
        self.star_indicator.reset()
        
        # Start command recording
        self.command_recorder.start_recording()
        
        # Clear any pending input events FIRST to prevent keys from menu from affecting gameplay
        # This must happen BEFORE checking key state
        pygame.event.clear(pygame.KEYDOWN)
        pygame.event.clear(pygame.KEYUP)
        pygame.event.clear(pygame.JOYBUTTONDOWN)
        pygame.event.clear(pygame.JOYBUTTONUP)
        
        # Track which keys were pressed when level started - we'll ignore these until released
        # Check AFTER clearing events to see if keys are still held
        keys_at_start = pygame.key.get_pressed()
        self.keys_pressed_at_start = set()
        problematic_keys = [pygame.K_SPACE, pygame.K_UP, pygame.K_w]
        for key in problematic_keys:
            try:
                # Check if key is in range and pressed
                if key < len(keys_at_start) and keys_at_start[key]:
                    self.keys_pressed_at_start.add(key)
            except (IndexError, KeyError, TypeError):
                pass
        
    
    def handle_events(self) -> None:
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.JOYDEVICEADDED:
                # Controller connected
                self.input_handler.add_controller(event.device_index)
            elif event.type == pygame.JOYDEVICEREMOVED:
                # Controller disconnected
                self.input_handler.remove_controller(event.device_index)
            elif event.type == pygame.JOYBUTTONDOWN:
                # Handle splash screen input
                if self.state == config.STATE_SPLASH and self.splash_screen:
                    self.splash_screen.handle_event(event)
                else:
                    # Use state handler for controller events
                    handler = self.state_handler_registry.get_handler(self.state)
                    handler.handle_controller(event, self)
            elif event.type == pygame.JOYHATMOTION or event.type == pygame.JOYAXISMOTION:
                # Handle controller hat (d-pad) and axis (stick) events for menu navigation
                if self.state in (config.STATE_MENU, config.STATE_PROFILE_SELECTION, config.STATE_LEVEL_COMPLETE):
                    handler = self.state_handler_registry.get_handler(self.state)
                    handler.handle_controller(event, self)
            elif event.type == pygame.KEYDOWN:
                # Handle splash screen input
                if self.state == config.STATE_SPLASH and self.splash_screen:
                    self.splash_screen.handle_event(event)
                else:
                    # Use state handler for keyboard events
                    handler = self.state_handler_registry.get_handler(self.state)
                    handler.handle_keyboard(event, self)
    
    def update(self, dt: float) -> None:
        """Update game state."""
        # Update splash screen
        if self.state == config.STATE_SPLASH:
            if self.splash_screen:
                self.splash_screen.update(dt)
                # Check if splash should transition to menu
                if self.splash_screen.should_transition:
                    self.state = config.STATE_MENU
        
        # Update menu UI animations
        if self.state == config.STATE_MENU:
            profile = self.profile_manager.get_active_profile()
            self.main_menu.set_profile_info(
                profile.name if profile else None,
                profile.level if profile else None
            )
            self.main_menu.update(dt)
        elif self.state == config.STATE_PROFILE_SELECTION:
            self.profile_selection_menu.update(dt)
            return
        elif self.state == config.STATE_LEVEL_COMPLETE:
            self.level_complete_menu.update(dt)
        
        if self.state == config.STATE_LEVEL_COMPLETE:
            # Update star animation during level complete
            if self.star_animation:
                self.star_animation.update(dt)
            return
        
        if self.state != config.STATE_PLAYING:
            return  # Don't update if not playing (including quit confirmation)
        
        # Update exit explosion animation
        if self.exit_explosion_active:
            self.exit_explosion_time += dt / 60.0  # Convert to seconds
            # Explosion lasts 1.5 seconds, then transition to level complete
            if self.exit_explosion_time >= 1.5:
                self.exit_explosion_active = False
                self.complete_level(success=True)
                return
        
        if not self.ship or not self.maze:
            return
        
        # Check if any eggs are still alive - deactivate exit portal if eggs exist
        has_active_eggs = any(egg.active for egg in self.eggs)
        if self.maze.exit.active:
            self.maze.exit.set_activated(not has_active_eggs, self.sound_manager)
        
        # Update exit animation and check player proximity
        if self.maze.exit.active:
            player_pos = (self.ship.x, self.ship.y) if self.ship else None
            self.maze.exit.update(dt, player_pos)
        
        # Apply exit portal attraction force to ship
        if self.ship and self.maze.exit.active:
            attraction_force = self.maze.exit.get_attraction_force((self.ship.x, self.ship.y))
            if attraction_force is not None:
                # Apply attraction force to ship velocity
                self.ship.vx += attraction_force[0]
                self.ship.vy += attraction_force[1]
                
                # Limit max speed (same as thrust)
                speed = math.sqrt(self.ship.vx * self.ship.vx + self.ship.vy * self.ship.vy)
                if speed > self.ship.max_speed:
                    scale = self.ship.max_speed / speed
                    self.ship.vx *= scale
                    self.ship.vy *= scale
        
        # Ignore input for a short period after level start to avoid counting menu key presses
        current_time = time.time()
        ignore_input_duration = 0.5  # Ignore input for 0.5 seconds after level start
        ignore_input = (current_time - self.level_start_time) < ignore_input_duration
        
        # Process input and get commands
        keys = pygame.key.get_pressed()
        
        # Process keyboard input (match original process_input logic)
        keyboard_commands = []
        for key_codes, command_type in self.input_handler.key_mappings.items():
            # Check if any of the mapped keys are pressed
            if any(keys[key_code] for key_code in key_codes):
                keyboard_commands.append(command_type)
        
        # Process controller input only if not ignoring input
        controller_commands = []
        if not ignore_input:
            controller_commands = self.input_handler.process_controller_input()
        
        # Combine commands
        commands = keyboard_commands[:]
        for cmd in controller_commands:
            if cmd not in commands:
                commands.append(cmd)
        
        # Filter out problematic commands during ignore period OR if keys were pressed at start (until released)
        should_filter_commands = ignore_input
        
        if self.keys_pressed_at_start:
            # Check if problematic keys are still pressed
            keys_still_pressed = set()
            for key in self.keys_pressed_at_start:
                try:
                    if keys[key]:
                        keys_still_pressed.add(key)
                except (IndexError, KeyError):
                    pass
            
            # If ANY problematic key is still pressed, we should filter commands
            if keys_still_pressed:
                should_filter_commands = True
            
            # Update the set
            self.keys_pressed_at_start = keys_still_pressed
        
        # Filter out ALL movement commands if we should ignore input
        # This prevents keys pressed at menu from affecting gameplay
        if should_filter_commands:
            # Filter out all movement commands (thrust, rotate)
            commands = [cmd for cmd in commands if cmd not in (
                CommandType.APPLY_THRUST,
                CommandType.ROTATE_LEFT,
                CommandType.ROTATE_RIGHT
            )]
        
        # Handle shield activation (only active while button is held down)
        # Shield is active only while DOWN/S is pressed OR controller shield button (not a toggle)
        shield_key_pressed = keys[pygame.K_DOWN] or keys[pygame.K_s]
        shield_controller_pressed = self.input_handler.is_controller_shield_pressed()
        shield_pressed = shield_key_pressed or shield_controller_pressed
        
        # Only allow manual shield control after initial activation period
        if self.ship.shield_initial_timer <= 0:
            if shield_pressed:
                # Key/button is held - activate shield
                if not self.ship.is_shield_active():
                    self.ship.shield_active = True
            else:
                # Key/button is not held - deactivate shield
                if self.ship.is_shield_active():
                    self.ship.shield_active = False
        
        # Handle fire separately (has rate limiting)
        # Check both keyboard and controller for fire input
        # Ignore fire input during ignore period OR if SPACE was pressed at start and still pressed
        fire_key_pressed = False
        fire_controller_pressed = False
        
        # Check if we should ignore fire (same logic as command filtering)
        space_still_pressed = pygame.K_SPACE in self.keys_pressed_at_start
        should_ignore_fire = ignore_input or space_still_pressed
        
        if not should_ignore_fire:
            try:
                fire_key_pressed = keys[pygame.K_SPACE]
            except (IndexError, KeyError):
                pass
            fire_controller_pressed = self.input_handler.is_controller_fire_pressed()
        
        fire_pressed = fire_key_pressed or fire_controller_pressed
        
        if not self.player_has_moved:
            # Check for explicit movement commands (not shield, not NO_ACTION)
            has_movement = False
            for cmd in commands:
                if cmd in (CommandType.ROTATE_LEFT, CommandType.ROTATE_RIGHT, CommandType.APPLY_THRUST):
                    has_movement = True
                    break
            
            # Fire also counts as first move, but ignore it if we just started the level
            if has_movement or (fire_pressed and not ignore_input):
                # First move detected - start the game loop
                self.player_has_moved = True
                self.ship.game_started = True  # Allow shield timer to countdown
        
        # Execute movement commands on ship and record them
        # Filter out shield command since it's handled separately above
        for cmd in commands:
            if cmd == CommandType.ACTIVATE_SHIELD:
                continue  # Shield already handled above
            self._execute_ship_command(cmd)
            self.command_recorder.record_command(cmd)
        
        if fire_pressed:
            if not hasattr(self, 'last_shot_time'):
                self.last_shot_time = 0
            current_time = pygame.time.get_ticks()
            fire_cooldown = calculate_fire_cooldown(self.ship)
            
            if current_time - self.last_shot_time > fire_cooldown:
                projectiles = self.ship.fire()
                if projectiles:
                    # fire() now returns a list (single or multiple projectiles)
                    self.projectiles.extend(projectiles)
                    self.scoring.record_shot()
                    self.command_recorder.record_command(CommandType.FIRE)
                    self.last_shot_time = current_time
        
        # Record NO_ACTION once per loop when no input is detected
        # This allows the replay enemy to mirror periods of inactivity
        if not commands and not fire_pressed:
            self.command_recorder.record_command(CommandType.NO_ACTION)
        
        # Update ship
        self.ship.update(dt)
        
        # Check ship-wall collision (use spatial grid for optimization)
        # Skip collision if shield is active
        if not self.ship.is_shield_active():
            if self.ship.check_wall_collision(self.maze.walls, self.maze.spatial_grid):
                self.scoring.record_wall_collision()
        
        # Only update enemies after player has made their first move
        player_pos = (self.ship.x, self.ship.y) if self.ship else None
        if self.player_has_moved:
            # Update all enemy types using EnemyUpdater
            self.enemy_updater.update_enemies(
                self.enemies, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles
            )
            self.enemy_updater.update_replay_enemies(
                self.replay_enemies, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles
            )
            self.enemy_updater.update_flighthouses(
                self.flighthouses, dt, player_pos, self.maze, self.ship, self.scoring, self.flockers
            )
            self.enemy_updater.update_flockers(
                self.flockers, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles, self.sound_manager
            )
            self.enemy_updater.update_split_bosses(
                self.split_bosses, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles
            )
            self.enemy_updater.update_mother_bosses(
                self.mother_bosses, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles, self.eggs
            )
            self.enemy_updater.update_babies(
                self.babies, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles
            )
            self.enemy_updater.update_eggs(
                self.eggs, dt, self.maze, self.ship, self.scoring, self.command_recorder, self.babies
            )
            
            # Handle enemy-to-enemy avoidance after all enemies are updated
            self.enemy_updater.handle_enemy_to_enemy_avoidance(
                self.replay_enemies, self.flockers, self.split_bosses, self.mother_bosses, self.babies
            )
        
        # Update projectiles and handle collisions
        active_projectiles = []
        for projectile in self.projectiles:
            projectile.update(dt)
            
            if not projectile.active:
                continue
            
            # Check projectile-wall collision (use spatial grid)
            # Only player projectiles can damage walls
            if not projectile.is_enemy:
                hit_wall = projectile.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
                if hit_wall:
                    # Damage the wall (hit_wall is already a WallSegment)
                    self.maze.damage_wall(hit_wall)
            else:
                # Enemy projectiles just deactivate on wall collision
                projectile.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
            
            # Check enemy projectile-ship collision
            if self.collision_handler.handle_projectile_ship_collision(projectile, self.ship, self.scoring):
                continue  # Projectile destroyed, skip adding to active list
            
            # Check projectile-enemy collisions (only for player projectiles)
            if self.collision_handler.handle_projectile_enemy_collisions(
                projectile, self.enemies, self.replay_enemies, self.flockers, self.flighthouses, self.split_bosses, self.mother_bosses, self.babies, self.eggs, self.powerup_crystals
            ):
                continue  # Projectile destroyed, skip adding to active list
            
            # Only add to active list if projectile is still active after all collision checks
            if projectile.active:
                active_projectiles.append(projectile)
        
        # Replace projectiles list with active ones
        self.projectiles = active_projectiles
        
        # Update powerup crystals
        active_crystals = []
        player_pos = (self.ship.x, self.ship.y) if self.ship else None
        for crystal in self.powerup_crystals:
            if not crystal.active:
                continue
            
            crystal.update(dt, player_pos)
            
            # Check ship-crystal collision
            if self.collision_handler.handle_ship_crystal_collision(self.ship, crystal, self.scoring):
                continue  # Crystal collected, don't add to active list
            
            if crystal.active:
                active_crystals.append(crystal)
        
        self.powerup_crystals = active_crystals
        
        # Check exit reached
        if self.maze.check_exit_reached((self.ship.x, self.ship.y), self.ship.radius):
            if not self.exit_explosion_active:
                # Start exit explosion
                self.exit_explosion_active = True
                self.exit_explosion_time = 0.0
                self.exit_explosion_pos = self.maze.exit.get_pos()
                # Stop all sounds
                self.sound_manager.stop_all_sounds()
                # Stop ship's thruster sound specifically
                if self.ship:
                    self.ship.sound_manager.stop_thruster()
                # Play cosmic warble for exit
                self.sound_manager.play_exit_warble()
                self.sound_manager.stop_critical_warning()
                self.critical_warning_active = False
            return  # Don't update game during explosion
        
        # Check if score has reached zero (level failed)
        current_time = time.time()
        potential = self.scoring.calculate_current_potential_score(
            current_time,
            self.ship.fuel,
            self.ship.ammo
        )
        potential_score = potential['potential_score']
        self._update_critical_warning(potential_score)
        
        # When score reaches zero, freeze all action and start fade
        if potential_score <= 0 and not self.game_frozen:
            self.game_frozen = True
            self._start_game_over_sequence(current_time)
        
        # If game is frozen, don't update entities (action is frozen)
        if self.game_frozen:
            # Update game over sequence timing
            if self.game_over_active:
                elapsed = current_time - self.game_over_start_time
                # Check if sequence is complete (fade + text display)
                if elapsed >= self.game_over_fade_duration + self.game_over_text_delay + self.game_over_text_duration:
                    self.complete_level(success=False)
                    self.game_over_active = False
                    self.game_frozen = False
            return  # Don't update game entities when frozen
        
        # Update star indicator (handles change detection and audio feedback)
        score_percentage = potential.get('score_percentage', 0.0)
        self.star_indicator.update(score_percentage)

    def _update_critical_warning(self, potential_score: float) -> None:
        """Start/stop critical warning sound based on remaining potential score."""
        # Only warn while there are still points/energy remaining
        if 0 < potential_score <= self.CRITICAL_WARNING_THRESHOLD:
            if not self.critical_warning_active:
                self.sound_manager.start_critical_warning()
                self.critical_warning_active = True
            else:
                # Periodic check: verify sound is still playing
                channel_busy = self.sound_manager.critical_warning_channel.get_busy() if self.sound_manager.critical_warning_channel else False
                if not channel_busy:
                    # Sound stopped unexpectedly, restart it
                    self.sound_manager.start_critical_warning()
        elif self.critical_warning_active:
            self.sound_manager.stop_critical_warning()
            self.critical_warning_active = False
    
    def _start_game_over_sequence(self, current_time: float) -> None:
        """Start the game over sequence: freeze action, fade to black, power down sound, then GAME OVER text."""
        self.game_over_active = True
        self.game_over_start_time = current_time
        # Stop all sounds for dramatic effect
        self.sound_manager.stop_all_sounds()
        self.critical_warning_active = False
        # Play power down sound
        self.sound_manager.play_power_down()
    
    def complete_level(self, success: bool = True) -> None:
        """Handle level completion or failure.
        
        Args:
            success: True if level was completed successfully (reached exit),
                     False if level failed (score reached zero)
        """
        current_time = time.time()
        completion_time = self.scoring.get_current_time(current_time)
        self.sound_manager.stop_critical_warning()
        self.critical_warning_active = False
        
        # Store success status
        self.level_succeeded = success
        
        # Calculate score
        self.level_score_breakdown = self.scoring.calculate_level_score(
            completion_time,
            self.ship.fuel,
            self.ship.ammo
        )
        
        # Store completion time for display
        self.completion_time_seconds = completion_time
        
        # Calculate score percentage for star rating
        max_score = self.scoring.calculate_max_possible_score()
        final_score = self.level_score_breakdown.get('final_score', 0)
        self.level_score_percentage = min(1.0, max(0.0, final_score / max_score)) if max_score > 0 else 0.0
        if success:
            self.profile_manager.update_active_profile_progress(self.level, self.scoring.get_total_score())
        
        # Initialize animated star rating if level succeeded
        if success:
            # Calculate star spacing (default is star_size * 1.2)
            star_spacing = int(config.LEVEL_COMPLETE_STAR_SIZE * 1.2)
            # Center the stars: first star center should be at screen_center - 2 * star_spacing
            # (since we have 5 stars, the middle star at index 2 should be at screen center)
            star_x = config.SCREEN_WIDTH // 2 - 2 * star_spacing
            star_y = config.SCREEN_HEIGHT // 2 - 50
            self.star_animation = AnimatedStarRating(
                self.level_score_percentage,
                star_x,
                star_y,
                star_size=config.LEVEL_COMPLETE_STAR_SIZE
            )
            # Set sound callback
            self.star_animation.set_sound_callback(self.sound_manager.play_tinkling)
        else:
            self.star_animation = None
        
        self.level_complete_time = current_time
        self.level_complete_quit_confirm = False
        self.state = config.STATE_LEVEL_COMPLETE
    
    def draw(self) -> None:
        """Draw game state."""
        self.screen.fill(config.COLOR_BACKGROUND)
        
        if self.state == config.STATE_SPLASH:
            if self.splash_screen:
                self.splash_screen.draw(self.screen)
        elif self.state == config.STATE_MENU:
            self.main_menu.draw()
        elif self.state == config.STATE_PROFILE_SELECTION:
            self.profile_selection_menu.draw()
        elif self.state == config.STATE_PLAYING:
            self.draw_game()
            if self.exit_explosion_active:
                self.draw_exit_explosion()
        elif self.state == config.STATE_QUIT_CONFIRM:
            self.draw_game()  # Draw game in background
            self.quit_confirmation_menu.draw_quit_confirmation(
                self.main_menu.menu_pulse_phase,
                self.quit_confirmation_selection
            )
        elif self.state == config.STATE_LEVEL_COMPLETE:
            self.level_complete_menu.draw(
                self.level,
                self.level_succeeded,
                self.completion_time_seconds,
                self.level_score_breakdown,
                self.star_animation,
                self.level_complete_quit_confirm,
                lambda: self.quit_confirmation_menu.draw_level_complete_quit_confirmation(
                    self.level_complete_menu.menu_pulse_phase,
                    self.quit_confirmation_selection
                )
            )
        
        pygame.display.flip()
    
    def draw_game(self) -> None:
        """Draw game play screen."""
        if not self.maze or not self.ship:
            return
        
        # Draw maze
        self.maze.draw(self.screen)
        
        # Draw enemies
        player_pos = (self.ship.x, self.ship.y) if self.ship else None
        for enemy in self.enemies:
            enemy.draw(self.screen, player_pos)
        
        # Draw replay enemies
        for replay_enemy in self.replay_enemies:
            if replay_enemy.active:
                replay_enemy.draw(self.screen)
        
        # Draw flocker enemies
        for flocker in self.flockers:
            if flocker.active:
                flocker.draw(self.screen)

        # Draw flighthouse enemies
        for flighthouse in self.flighthouses:
            if flighthouse.active:
                flighthouse.draw(self.screen)
        
        # Draw SplitBoss enemies
        for split_boss in self.split_bosses:
            if split_boss.active:
                split_boss.draw(self.screen)
        
        # Draw Mother Boss enemies
        for mother_boss in self.mother_bosses:
            if mother_boss.active:
                mother_boss.draw(self.screen)
        
        # Draw Baby enemies
        for baby in self.babies:
            if baby.active:
                baby.draw(self.screen)
        
        # Draw egg enemies
        for egg in self.eggs:
            if egg.active:
                egg.draw(self.screen)
        
        # Draw powerup crystals
        for crystal in self.powerup_crystals:
            if crystal.active:
                crystal.draw(self.screen)
        
        # Draw projectiles
        for projectile in self.projectiles:
            projectile.draw(self.screen)
        
        # Draw ship (hide during exit explosion)
        if not self.exit_explosion_active:
            self.ship.draw(self.screen)
        
        # Draw UI (hide during exit explosion)
        if not self.exit_explosion_active:
            current_time = time.time()
            potential = self.scoring.calculate_current_potential_score(
                current_time,
                self.ship.fuel,
                self.ship.ammo
            )
            elapsed = self.scoring.get_current_time(current_time)
            self.ship.draw_ui(
                self.screen,
                self.small_font,
                potential_score=potential['potential_score'],
                max_score=potential['max_score'],
                level=self.level,
                time_seconds=elapsed
            )
        
        # Draw game indicators using component (now only draws time, which is handled by ship.draw_ui)
        # GameIndicators is kept for potential future use but currently doesn't draw anything
        
        # Draw game over sequence (fade to black and text)
        if self.game_over_active:
            self._draw_game_over_sequence()
    
    
    def _draw_game_over_sequence(self) -> None:
        """Draw game over sequence: fade to black and GAME OVER text."""
        current_time = time.time()
        elapsed = current_time - self.game_over_start_time
        
        # Calculate fade progress (0.0 to 1.0)
        fade_progress = min(1.0, elapsed / self.game_over_fade_duration)
        
        # Create fade overlay (black with increasing alpha)
        fade_alpha = int(255 * fade_progress)
        if fade_alpha > 0:
            fade_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            fade_surface.fill((0, 0, 0, fade_alpha))
            self.screen.blit(fade_surface, (0, 0))
        
        # Show "GAME OVER" text after fade delay
        if elapsed >= self.game_over_fade_duration + self.game_over_text_delay:
            # Render "GAME OVER" text
            # Use large, bold font
            game_over_font = pygame.font.Font(None, 120)
            game_over_text = game_over_font.render("GAME OVER", True, (255, 255, 255))
            text_rect = game_over_text.get_rect(center=(self.screen.get_width() // 2, 
                                                         self.screen.get_height() // 2))
            self.screen.blit(game_over_text, text_rect)
    
    def draw_exit_explosion(self) -> None:
        """Draw spectacular exit explosion effect that fills the screen with light."""
        if not self.exit_explosion_pos:
            return
        
        # Calculate explosion progress (0.0 to 1.0)
        progress = min(1.0, self.exit_explosion_time / 1.5)
        
        # Create expanding light effect
        # Multiple expanding rings of light
        max_radius = max(config.SCREEN_WIDTH, config.SCREEN_HEIGHT) * 1.5
        
        # Draw multiple expanding layers
        for layer in range(5):
            layer_progress = progress - (layer * 0.15)
            if layer_progress < 0:
                continue
            
            # Calculate radius for this layer
            layer_radius = max_radius * layer_progress * (1.0 + layer * 0.2)
            
            # Calculate intensity (fades out as it expands)
            intensity = 1.0 - (layer_progress * 0.8)
            intensity = max(0.0, intensity)
            
            # Color varies by layer for spectacular effect
            if layer == 0:
                # Core: bright white/yellow
                color = (255, 255, 200)
            elif layer == 1:
                # Inner: bright yellow/orange
                color = (255, 220, 100)
            elif layer == 2:
                # Mid: orange/red
                color = (255, 150, 50)
            elif layer == 3:
                # Outer: red/purple
                color = (200, 100, 255)
            else:
                # Outermost: purple/blue
                color = (150, 150, 255)
            
            # Draw expanding circle with glow
            alpha = int(255 * intensity * 0.6)
            if alpha > 0 and layer_radius > 0:
                # Create surface for this layer
                size = int(layer_radius * 2) + 100
                if size > 0:
                    glow_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                    center = size // 2
                    
                    # Draw multiple concentric circles for smooth glow
                    for i in range(10):
                        circle_radius = layer_radius - (i * layer_radius / 10)
                        if circle_radius > 0:
                            circle_alpha = int(alpha * (1.0 - i / 10))
                            if circle_alpha > 0:
                                glow_color = (*color, circle_alpha)
                                pygame.draw.circle(glow_surf, glow_color, (center, center), int(circle_radius))
                    
                    # Blit to screen
                    pos_x = self.exit_explosion_pos[0] - center
                    pos_y = self.exit_explosion_pos[1] - center
                    self.screen.blit(glow_surf, (int(pos_x), int(pos_y)))
        
        # Draw bright flash overlay that fills screen
        flash_intensity = 1.0 - progress
        if flash_intensity > 0:
            flash_alpha = int(255 * flash_intensity * 0.4)
            if flash_alpha > 0:
                flash_overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
                flash_color = (255, 255, 255, flash_alpha)
                flash_overlay.fill(flash_color)
                self.screen.blit(flash_overlay, (0, 0))
    
    def reset_scoring_to_profile_state(self) -> None:
        """Reset scoring state using the explicit START_LEVEL override first, then profile progress, else default."""
        self.scoring = ScoringSystem()
        profile = self.profile_manager.get_active_profile()
        if profile:
            self.scoring.total_score = profile.total_score

        if self.initial_start_level is not None:
            resolved_level = self.initial_start_level
        elif profile and profile.level is not None:
            resolved_level = profile.level
        else:
            resolved_level = 1

        self.level = resolved_level

    def reset_quit_confirmation_selection(self) -> None:
        """Reset overlay selection back to the default option."""
        self.quit_confirmation_selection = 0

    def run(self) -> None:
        """Main game loop."""
        while self.running:
            dt_ms = self.clock.tick(config.FPS)
            # Normalize delta time: 1.0 = 60fps, scales movement for frame independence
            dt = dt_ms / (1000.0 / config.FPS)
            
            self.handle_events()
            self.update(dt)
            self.draw()

