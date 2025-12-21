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
from rendering import Renderer
from rendering.ui_elements import AnimatedStarRating, StarIndicator
from rendering.menu_components import AnimatedBackground, NeonText, Button, ControllerIcon
from rendering.visual_effects import draw_button_glow
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
    
    def __init__(self, screen: pygame.Surface):
        """Initialize game."""
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.renderer = Renderer(screen)
        
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
        self.level = self.initial_start_level if self.initial_start_level else 1
        self.ship: Optional[Ship] = None
        self.maze: Optional[Maze] = None
        
        # Entity management
        self.entity_manager = EntityManager()
        self.enemies = self.entity_manager.enemies
        self.replay_enemies = self.entity_manager.replay_enemies
        self.split_bosses = self.entity_manager.split_bosses
        self.mother_bosses = self.entity_manager.mother_bosses
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
        
        # Menu UI components
        self.menu_background: Optional[AnimatedBackground] = None
        self.menu_title: Optional[NeonText] = None
        self.menu_buttons: List[Button] = []
        self.menu_selected_index = 0
        self.menu_pulse_phase = 0.0
        self.level_complete_background: Optional[AnimatedBackground] = None
        self.game_over_background: Optional[AnimatedBackground] = None
        self.splash_screen: Optional[SplashScreenState] = None
        self._initialize_menu_ui()
        self._initialize_splash_screen()
    
    def _initialize_menu_ui(self) -> None:
        """Initialize menu UI components."""
        # Create animated background
        self.menu_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        # Create title with neon effect
        title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
        self.menu_title = NeonText(
            "ASTER VOID",
            title_font,
            (config.SCREEN_WIDTH // 2, 180),
            config.COLOR_NEON_ASTER_START,
            config.COLOR_NEON_VOID_END,
            center=True
        )
        
        # Create buttons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        
        start_button = Button(
            "START GAME",
            (config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 50),
            button_font,
            width=400,
            height=60
        )
        start_button.selected = True
        
        self.menu_buttons = [start_button]
        self.menu_selected_index = 0
    
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
            enemy_counts.total + enemy_counts.replay + enemy_counts.egg + split_boss_count + mother_boss_count + 5  # Extra buffer for spawn positions
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
            if self.menu_background:
                self.menu_background.update(dt)
            if self.menu_title:
                self.menu_title.update(dt)
            # Update pulse phase for button glow
            self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
            if self.menu_pulse_phase >= 2 * math.pi:
                self.menu_pulse_phase -= 2 * math.pi
        elif self.state == config.STATE_LEVEL_COMPLETE:
            # Update level complete background
            if self.level_complete_background:
                self.level_complete_background.update(dt)
            # Update pulse phase for button glow
            self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
            if self.menu_pulse_phase >= 2 * math.pi:
                self.menu_pulse_phase -= 2 * math.pi
        elif self.state == config.STATE_GAME_OVER:
            # Update game over background
            if self.game_over_background:
                self.game_over_background.update(dt)
            # Update pulse phase for button glow
            self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
            if self.menu_pulse_phase >= 2 * math.pi:
                self.menu_pulse_phase -= 2 * math.pi
        
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
            self.enemy_updater.update_split_bosses(
                self.split_bosses, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles
            )
            self.enemy_updater.update_mother_bosses(
                self.mother_bosses, dt, player_pos, self.maze, self.ship, self.scoring, self.projectiles, self.eggs
            )
            self.enemy_updater.update_eggs(
                self.eggs, dt, self.maze, self.ship, self.scoring, self.command_recorder, self.replay_enemies
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
                projectile, self.enemies, self.replay_enemies, self.split_bosses, self.mother_bosses, self.eggs, self.powerup_crystals
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
            if self.collision_handler.handle_ship_crystal_collision(self.ship, crystal):
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
            return  # Don't update game during explosion
        
        # Check if score has reached zero (level failed)
        current_time = time.time()
        potential = self.scoring.calculate_current_potential_score(
            current_time,
            self.ship.fuel,
            self.ship.ammo
        )
        if potential['potential_score'] <= 0:
            self.complete_level(success=False)
            return
        
        # Update star indicator (handles change detection and audio feedback)
        score_percentage = potential.get('score_percentage', 0.0)
        self.star_indicator.update(score_percentage)
        
        # Check game over conditions
        if self.ship.fuel <= 0 and abs(self.ship.vx) < 0.1 and abs(self.ship.vy) < 0.1:
            # Out of fuel and stopped
            pass  # Could trigger game over here if desired
    
    def complete_level(self, success: bool = True) -> None:
        """Handle level completion or failure.
        
        Args:
            success: True if level was completed successfully (reached exit),
                     False if level failed (score reached zero)
        """
        current_time = time.time()
        completion_time = self.scoring.get_current_time(current_time)
        
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
        
        # Initialize animated star rating if level succeeded
        if success:
            star_x = config.SCREEN_WIDTH // 2 - (5 * int(config.LEVEL_COMPLETE_STAR_SIZE * 1.2)) // 2
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
            self.draw_menu()
        elif self.state == config.STATE_PLAYING:
            self.draw_game()
            if self.exit_explosion_active:
                self.draw_exit_explosion()
        elif self.state == config.STATE_QUIT_CONFIRM:
            self.draw_game()  # Draw game in background
            self.draw_quit_confirmation()
        elif self.state == config.STATE_LEVEL_COMPLETE:
            self.draw_level_complete()
        elif self.state == config.STATE_GAME_OVER:
            self.draw_game_over()
        
        pygame.display.flip()
    
    def draw_menu(self) -> None:
        """Draw main menu with animated background and neon effects."""
        # Draw animated background
        if self.menu_background:
            self.menu_background.draw(self.screen)
        
        # Draw title with neon effect
        if self.menu_title:
            self.menu_title.draw(self.screen)
        
        # Draw subtitle
        subtitle_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        subtitle = subtitle_font.render("A Skill-Based Space Navigation Game", True, config.COLOR_TEXT)
        subtitle_rect = subtitle.get_rect(center=(config.SCREEN_WIDTH // 2, 250))
        self.screen.blit(subtitle, subtitle_rect)
        
        # Draw buttons
        button_y = config.SCREEN_HEIGHT // 2 + 50
        for i, button in enumerate(self.menu_buttons):
            button.selected = (i == self.menu_selected_index)
            button.draw(self.screen, self.menu_pulse_phase)
            
            # Draw controller icon next to selected button
            if button.selected:
                icon_x = button.position[0] - button.width // 2 - 50
                icon_y = button.position[1]
                ControllerIcon.draw_a_button(self.screen, (icon_x, icon_y), size=35, selected=True)
        
        # Draw hints below buttons
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        hint_y = button_y + 80
        
        # Start hint
        start_hint = hint_font.render("Press SPACE/ENTER or A Button to Start", True, config.COLOR_TEXT)
        start_hint_rect = start_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
        self.screen.blit(start_hint, start_hint_rect)
        
        # Quit hint
        quit_hint = hint_font.render("Press ESC/Q or B Button to Quit", True, config.COLOR_TEXT)
        quit_hint_rect = quit_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
        self.screen.blit(quit_hint, quit_hint_rect)
        
        # Draw controls info at bottom (smaller, less prominent)
        controls_y = config.SCREEN_HEIGHT - 120
        controls_font = pygame.font.Font(None, 20)
        controls_text = [
            "Controls: Arrow Keys/WASD - Move | Space - Fire | Down/S - Shield",
            "Controller: Sticks - Move | R/ZR/B - Fire | A - Shield | L/ZL - Thrust"
        ]
        for i, line in enumerate(controls_text):
            text = controls_font.render(line, True, (150, 150, 150))
            text_rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, controls_y + i * 25))
            self.screen.blit(text, text_rect)
    
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
        
        # Draw SplitBoss enemies
        for split_boss in self.split_bosses:
            if split_boss.active:
                split_boss.draw(self.screen)
        
        # Draw Mother Boss enemies
        for mother_boss in self.mother_bosses:
            if mother_boss.active:
                mother_boss.draw(self.screen)
        
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
            self.ship.draw_ui(self.screen, self.small_font)
        
        # Draw score
        score_text = self.small_font.render(
            f"Score: {self.scoring.get_total_score()}", 
            True, config.COLOR_TEXT
        )
        self.screen.blit(score_text, (config.SCREEN_WIDTH - 200, 10))
        
        # Draw level
        level_text = self.small_font.render(
            f"Level: {self.level}", 
            True, config.COLOR_TEXT
        )
        self.screen.blit(level_text, (config.SCREEN_WIDTH - 200, 40))
        
        # Draw time
        current_time = time.time()
        elapsed = self.scoring.get_current_time(current_time)
        time_text = self.small_font.render(
            f"Time: {elapsed:.1f}s", 
            True, config.COLOR_TEXT
        )
        self.screen.blit(time_text, (config.SCREEN_WIDTH - 200, 70))
        
        # Draw 5-star potential score display
        if self.ship:
            potential = self.scoring.calculate_current_potential_score(
                current_time,
                self.ship.fuel,
                self.ship.ammo
            )
            self.draw_star_rating(potential['score_percentage'], config.SCREEN_WIDTH - 200, 110)
    
    def draw_level_complete(self) -> None:
        """Draw level complete or failed screen with enhanced UI."""
        # Initialize background if needed
        if not self.level_complete_background:
            self.level_complete_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        # Draw animated background
        if self.level_complete_background:
            self.level_complete_background.draw(self.screen)
        
        # Show different title based on success/failure
        title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
        if self.level_succeeded:
            title_text = f"LEVEL {self.level} COMPLETE"
            title = NeonText(
                title_text,
                title_font,
                (config.SCREEN_WIDTH // 2, 150),
                config.COLOR_NEON_ASTER_START,
                config.COLOR_NEON_VOID_END,
                center=True
            )
            title.pulse_phase = self.menu_pulse_phase
            title.draw(self.screen)
        else:
            title_text = "LEVEL FAILED"
            title = title_font.render(title_text, True, (255, 100, 100))
            title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
            self.screen.blit(title, title_rect)
        
        # Format time as minutes:seconds with one decimal place
        minutes = int(self.completion_time_seconds // 60)
        seconds_with_decimal = self.completion_time_seconds % 60
        time_text = self.small_font.render(
            f"Time: {minutes}:{seconds_with_decimal:05.1f}",
            True, config.COLOR_TEXT
        )
        time_rect = time_text.get_rect(center=(config.SCREEN_WIDTH // 2, 220))
        self.screen.blit(time_text, time_rect)
        
        # Draw animated star rating (centered, large)
        if self.star_animation:
            self.star_animation.draw(self.screen)
        
        # Draw total score
        total_score = int(self.level_score_breakdown.get('total_score', 0))
        score_text = self.small_font.render(
            f"Total Score: {total_score}",
            True, config.COLOR_TEXT
        )
        score_rect = score_text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 + 80))
        self.screen.blit(score_text, score_rect)
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = config.SCREEN_HEIGHT // 2 + 150
        
        if self.level_succeeded:
            # Continue button
            continue_button = Button(
                "CONTINUE",
                (config.SCREEN_WIDTH // 2, button_y),
                button_font,
                width=350,
                height=60
            )
            continue_button.selected = True
            continue_button.draw(self.screen, self.menu_pulse_phase)
            
            # Controller icon
            icon_x = continue_button.position[0] - continue_button.width // 2 - 50
            ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=35, selected=True)
            
            # Hints
            hint_y = button_y + 70
            continue_hint = hint_font.render("Press SPACE/ENTER or A Button", True, config.COLOR_TEXT)
            continue_hint_rect = continue_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
            self.screen.blit(continue_hint, continue_hint_rect)
            
            back_hint = hint_font.render("Press ESC/Q or B Button to Return to Menu", True, config.COLOR_TEXT)
            back_hint_rect = back_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
            self.screen.blit(back_hint, back_hint_rect)
        else:
            # Retry button
            retry_button = Button(
                "RETRY LEVEL",
                (config.SCREEN_WIDTH // 2, button_y),
                button_font,
                width=350,
                height=60
            )
            retry_button.selected = True
            retry_button.draw(self.screen, self.menu_pulse_phase)
            
            # Controller icon
            icon_x = retry_button.position[0] - retry_button.width // 2 - 50
            ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=35, selected=True)
            
            # Hints
            hint_y = button_y + 70
            retry_hint = hint_font.render("Press SPACE/ENTER or A Button", True, config.COLOR_TEXT)
            retry_hint_rect = retry_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y))
            self.screen.blit(retry_hint, retry_hint_rect)
            
            back_hint = hint_font.render("Press ESC/Q or B Button to Return to Menu", True, config.COLOR_TEXT)
            back_hint_rect = back_hint.get_rect(center=(config.SCREEN_WIDTH // 2, hint_y + 35))
            self.screen.blit(back_hint, back_hint_rect)
        
        # Draw quit confirmation overlay if active
        if self.level_complete_quit_confirm:
            self.draw_level_complete_quit_confirmation()
    
    def draw_star_rating(self, score_percentage: float, x: int, y: int) -> None:
        """Draw 5 stars that fill/drain based on score percentage."""
        self.renderer.draw_star_rating(score_percentage, x, y)
    
    def draw_level_complete_quit_confirmation(self) -> None:
        """Draw quit confirmation dialog overlay for level complete screen."""
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box with glow
        dialog_width = 550
        dialog_height = 240
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
        
        # Draw glow effect
        draw_button_glow(
            self.screen,
            dialog_rect,
            config.COLOR_BUTTON_GLOW,
            config.BUTTON_GLOW_INTENSITY * 1.5,
            self.menu_pulse_phase
        )
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, dialog_rect)
        pygame.draw.rect(self.screen, config.COLOR_BUTTON_GLOW, dialog_rect, 3)
        
        # Title
        title_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        title = title_font.render("Quit to Menu?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 50))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Progress will be saved.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 100))
        self.screen.blit(message, message_rect)
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = dialog_y + 150
        
        # Yes button
        yes_button = Button(
            "YES",
            (config.SCREEN_WIDTH // 2 - 120, button_y),
            button_font,
            width=180,
            height=50
        )
        yes_button.selected = True
        yes_button.draw(self.screen, self.menu_pulse_phase)
        
        # A button icon for Yes
        icon_x = yes_button.position[0] - yes_button.width // 2 - 35
        ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=30, selected=True)
        
        # No button
        no_button = Button(
            "NO",
            (config.SCREEN_WIDTH // 2 + 120, button_y),
            button_font,
            width=180,
            height=50
        )
        no_button.draw(self.screen, self.menu_pulse_phase)
        
        # B button icon for No
        icon_x = no_button.position[0] + no_button.width // 2 + 35
        ControllerIcon.draw_b_button(self.screen, (icon_x, button_y), size=30, selected=False)
        
        # Button hints
        yes_hint = hint_font.render("Y/Enter/A", True, config.COLOR_TEXT)
        no_hint = hint_font.render("N/ESC/B", True, config.COLOR_TEXT)
        
        yes_hint_rect = yes_hint.get_rect(center=(config.SCREEN_WIDTH // 2 - 120, button_y + 50))
        no_hint_rect = no_hint.get_rect(center=(config.SCREEN_WIDTH // 2 + 120, button_y + 50))
        
        self.screen.blit(yes_hint, yes_hint_rect)
        self.screen.blit(no_hint, no_hint_rect)
    
    def draw_quit_confirmation(self) -> None:
        """Draw quit confirmation dialog overlay with modern design."""
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box with glow
        dialog_width = 600
        dialog_height = 300
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_width, dialog_height)
        
        # Draw glow effect
        draw_button_glow(
            self.screen,
            dialog_rect,
            config.COLOR_BUTTON_GLOW,
            config.BUTTON_GLOW_INTENSITY * 1.5,
            self.menu_pulse_phase
        )
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, dialog_rect)
        pygame.draw.rect(self.screen, config.COLOR_BUTTON_GLOW, dialog_rect, 3)
        
        # Title
        title_font = pygame.font.Font(None, config.FONT_SIZE_SUBTITLE)
        title = title_font.render("Quit Level?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 40))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Are you sure you want to quit? Progress will be lost.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 90))
        self.screen.blit(message, message_rect)
        
        # Draw buttons with controller icons
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = dialog_y + 150
        
        # Return to menu button
        return_button = Button(
            "RETURN TO MENU",
            (config.SCREEN_WIDTH // 2, button_y),
            button_font,
            width=400,
            height=50
        )
        return_button.selected = True
        return_button.draw(self.screen, self.menu_pulse_phase)
        
        # A button icon
        icon_x = return_button.position[0] - return_button.width // 2 - 35
        ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=30, selected=True)
        
        # Return button hint
        return_hint = hint_font.render("Y/Enter/A Button", True, config.COLOR_TEXT)
        return_hint_rect = return_hint.get_rect(center=(config.SCREEN_WIDTH // 2, button_y + 40))
        self.screen.blit(return_hint, return_hint_rect)
        
        # Cancel button
        cancel_button = Button(
            "CANCEL",
            (config.SCREEN_WIDTH // 2, button_y + 100),
            button_font,
            width=400,
            height=50
        )
        cancel_button.draw(self.screen, self.menu_pulse_phase)
        
        # B button icon
        icon_x = cancel_button.position[0] - cancel_button.width // 2 - 35
        ControllerIcon.draw_b_button(self.screen, (icon_x, button_y + 100), size=30, selected=False)
        
        # Cancel button hint
        cancel_hint = hint_font.render("N/ESC/B Button", True, config.COLOR_TEXT)
        cancel_hint_rect = cancel_hint.get_rect(center=(config.SCREEN_WIDTH // 2, button_y + 140))
        self.screen.blit(cancel_hint, cancel_hint_rect)
    
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
    
    def draw_game_over(self) -> None:
        """Draw game over screen with enhanced UI."""
        # Initialize background if needed
        if not self.game_over_background:
            self.game_over_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        
        # Draw animated background
        if self.game_over_background:
            self.game_over_background.draw(self.screen)
        
        # Draw title with neon effect
        title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
        title = NeonText(
            "GAME OVER",
            title_font,
            (config.SCREEN_WIDTH // 2, 300),
            (255, 100, 100),  # Red for game over
            (255, 50, 50),
            center=True
        )
        title.pulse_phase = self.menu_pulse_phase
        title.draw(self.screen)
        
        # Draw final score
        score_text = self.small_font.render(
            f"Final Score: {self.scoring.get_total_score()}",
            True, config.COLOR_TEXT
        )
        score_rect = score_text.get_rect(center=(config.SCREEN_WIDTH // 2, 380))
        self.screen.blit(score_text, score_rect)
        
        # Draw button with controller icon
        button_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        hint_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        button_y = 450
        
        return_button = Button(
            "RETURN TO MENU",
            (config.SCREEN_WIDTH // 2, button_y),
            button_font,
            width=400,
            height=60
        )
        return_button.selected = True
        return_button.draw(self.screen, self.menu_pulse_phase)
        
        # Controller icon
        icon_x = return_button.position[0] - return_button.width // 2 - 50
        ControllerIcon.draw_a_button(self.screen, (icon_x, button_y), size=35, selected=True)
        
        # Hint
        continue_hint = hint_font.render(
            "Press SPACE/ENTER or A Button",
            True, config.COLOR_TEXT
        )
        continue_hint_rect = continue_hint.get_rect(center=(config.SCREEN_WIDTH // 2, button_y + 70))
        self.screen.blit(continue_hint, continue_hint_rect)
    
    def run(self) -> None:
        """Main game loop."""
        while self.running:
            dt_ms = self.clock.tick(config.FPS)
            # Normalize delta time: 1.0 = 60fps, scales movement for frame independence
            dt = dt_ms / (1000.0 / config.FPS)
            
            self.handle_events()
            self.update(dt)
            self.draw()

