"""Main game loop and state management."""

import pygame
import math
import time
import random
import os
from typing import List, Optional, Tuple
import config
from entities.ship import Ship
from maze import Maze
from entities.enemy import Enemy, create_enemies
import level_rules
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.split_boss import SplitBoss
from entities.projectile import Projectile
from entities.powerup_crystal import PowerupCrystal
from entities.command_recorder import CommandRecorder, CommandType
from input import InputHandler
from scoring import ScoringSystem
from rendering import Renderer
from rendering.ui_elements import AnimatedStarRating, StarIndicator
from sounds import SoundManager
from game_handlers.entity_manager import EntityManager
from game_handlers.spawn_manager import SpawnManager
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.collision_handler import CollisionHandler
from game_handlers.fire_rate_calculator import calculate_fire_cooldown
from game_handlers.state_handlers import StateHandlerRegistry


class Game:
    """Main game class managing state and game loop."""
    
    def __init__(self, screen: pygame.Surface):
        """Initialize game."""
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.renderer = Renderer(screen)
        
        self.state = config.STATE_MENU
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
        self.star_indicator = StarIndicator(
            on_star_lost=self.sound_manager.play_star_lost,
            on_star_gained=self.sound_manager.play_star_gained
        )
    
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
        
        # Set random seed based on level number for deterministic generation
        # Level 1 = seed 1, Level 2 = seed 2, etc.
        random.seed(self.level)
        
        # Generate maze
        self.maze = Maze(self.level)
        
        # Create ship at start position
        self.ship = Ship(self.maze.start_pos)
        # Activate shield at level start (initial activation, no fuel consumed)
        self.ship.shield_active = True
        # Reset gun upgrade state
        self.ship.reset_gun_upgrade()
        
        # Reset player movement flag - game loop won't start until first move
        self.player_has_moved = False
        self.ship.game_started = False  # Prevent shield timer countdown until first move
        
        # Spawn all enemies using SpawnManager
        enemy_counts = level_rules.get_enemy_counts(self.level)
        split_boss_count = level_rules.get_split_boss_count(self.level)
        spawn_positions = self.maze.get_valid_spawn_positions(
            enemy_counts.total + enemy_counts.replay + split_boss_count + 5  # Extra buffer for spawn positions
        )
        self.spawn_manager.spawn_all_enemies(self.level, spawn_positions, self.command_recorder)
        
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
                # Use state handler for controller events
                handler = self.state_handler_registry.get_handler(self.state)
                handler.handle_controller(event, self)
            elif event.type == pygame.KEYDOWN:
                # Use state handler for keyboard events
                handler = self.state_handler_registry.get_handler(self.state)
                handler.handle_keyboard(event, self)
    
    def update(self, dt: float) -> None:
        """Update game state."""
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
        
        # Process input and get commands
        keys = pygame.key.get_pressed()
        commands = self.input_handler.process_input(keys)
        
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
        fire_key_pressed = keys[pygame.K_SPACE]
        fire_controller_pressed = self.input_handler.is_controller_fire_pressed()
        fire_pressed = fire_key_pressed or fire_controller_pressed
        
        # Detect first move - only explicit movement actions count (rotate, thrust, or fire)
        # Shield activation does NOT count as first move
        # Ignore fire input for a short period after level start to avoid counting menu SPACE press
        current_time = time.time()
        ignore_fire_input = (current_time - self.level_start_time) < 0.3  # Ignore fire for 0.3 seconds after level start
        
        if not self.player_has_moved:
            # Check for explicit movement commands (not shield, not NO_ACTION)
            has_movement = False
            for cmd in commands:
                if cmd in (CommandType.ROTATE_LEFT, CommandType.ROTATE_RIGHT, CommandType.APPLY_THRUST):
                    has_movement = True
                    break
            
            # Fire also counts as first move, but ignore it if we just started the level
            if has_movement or (fire_pressed and not ignore_fire_input):
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
                projectile, self.enemies, self.replay_enemies, self.split_bosses, self.powerup_crystals
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
        
        if self.state == config.STATE_MENU:
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
        """Draw main menu."""
        title = self.font.render("ASTERDROIDS", True, config.COLOR_TEXT)
        subtitle = self.small_font.render("A Skill-Based Space Navigation Game", True, config.COLOR_TEXT)
        instructions = [
            "Controls:",
            "Keyboard:",
            "  Arrow Keys / WASD: Rotate and Thrust",
            "  Space: Fire Weapon",
            "  Down/S: Activate Shield",
            "",
            "Controller:",
            "  Left/Right Stick: Rotate",
            "  ZR / B: Thrust",
            "  ZL: Fire",
            "  A: Shield",
            "",
            "Objective:",
            "Navigate through mazes to reach the exit",
            "Balance speed, fuel, and ammo for high scores",
            "",
            "Press SPACE or A Button to Start",
            "Press ESC/Q or X Button to Quit"
        ]
        
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)
        
        subtitle_rect = subtitle.get_rect(center=(config.SCREEN_WIDTH // 2, 200))
        self.screen.blit(subtitle, subtitle_rect)
        
        y_offset = 280
        for line in instructions:
            text = self.small_font.render(line, True, config.COLOR_TEXT)
            text_rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, y_offset))
            self.screen.blit(text, text_rect)
            y_offset += 30
    
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
        """Draw simplified level complete or failed screen."""
        # Show different title based on success/failure
        if self.level_succeeded:
            title_text = f"LEVEL {self.level} COMPLETE"
            title_color = config.COLOR_TEXT
        else:
            title_text = "LEVEL FAILED"
            title_color = (255, 100, 100)  # Red for failure
        
        title = self.font.render(title_text, True, title_color)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 150))
        self.screen.blit(title, title_rect)
        
        # Format time as minutes:seconds with one decimal place
        minutes = int(self.completion_time_seconds // 60)
        seconds_with_decimal = self.completion_time_seconds % 60
        time_text = self.small_font.render(
            f"Time: {minutes}:{seconds_with_decimal:05.1f}",
            True, config.COLOR_TEXT
        )
        time_rect = time_text.get_rect(center=(config.SCREEN_WIDTH // 2, 200))
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
        
        # Draw action prompts
        y_offset = config.SCREEN_HEIGHT // 2 + 130
        if self.level_succeeded:
            prompts = [
                "Press SPACE/A to Continue",
                "Press R/B to Replay Level",
                "Press ESC/Q or X to Quit"
            ]
        else:
            prompts = [
                "Score reached zero!",
                "Press SPACE/A or R/B to Retry Level",
                "Press ESC/Q or X to Quit"
            ]
        
        for prompt in prompts:
            text = self.small_font.render(prompt, True, config.COLOR_TEXT)
            text_rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, y_offset))
            self.screen.blit(text, text_rect)
            y_offset += 30
        
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
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box
        dialog_width = 500
        dialog_height = 200
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, 
                        (dialog_x, dialog_y, dialog_width, dialog_height))
        pygame.draw.rect(self.screen, config.COLOR_TEXT, 
                        (dialog_x, dialog_y, dialog_width, dialog_height), 3)
        
        # Title
        title = self.font.render("Quit to Menu?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 50))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Progress will be saved.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 100))
        self.screen.blit(message, message_rect)
        
        # Options
        yes_text = self.small_font.render("Yes (Y/Enter/A)", True, config.COLOR_TEXT)
        no_text = self.small_font.render("No (N/ESC/B)", True, config.COLOR_TEXT)
        
        yes_rect = yes_text.get_rect(center=(config.SCREEN_WIDTH // 2 - 100, dialog_y + 150))
        no_rect = no_text.get_rect(center=(config.SCREEN_WIDTH // 2 + 100, dialog_y + 150))
        
        self.screen.blit(yes_text, yes_rect)
        self.screen.blit(no_text, no_rect)
    
    def draw_quit_confirmation(self) -> None:
        """Draw quit confirmation dialog overlay."""
        # Draw semi-transparent overlay
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Draw confirmation dialog box
        dialog_width = 500
        dialog_height = 220
        dialog_x = (config.SCREEN_WIDTH - dialog_width) // 2
        dialog_y = (config.SCREEN_HEIGHT - dialog_height) // 2
        
        # Dialog background
        pygame.draw.rect(self.screen, config.COLOR_UI_BG, 
                        (dialog_x, dialog_y, dialog_width, dialog_height))
        pygame.draw.rect(self.screen, config.COLOR_TEXT, 
                        (dialog_x, dialog_y, dialog_width, dialog_height), 3)
        
        # Title
        title = self.font.render("Quit Level?", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 50))
        self.screen.blit(title, title_rect)
        
        # Message
        message = self.small_font.render(
            "Are you sure you want to quit? Progress will be lost.",
            True, config.COLOR_TEXT
        )
        message_rect = message.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 100))
        self.screen.blit(message, message_rect)
        
        # Options
        yes_text = self.small_font.render("Return to Menu (Y/Enter/A)", True, config.COLOR_TEXT)
        no_text = self.small_font.render("Cancel (N/ESC)", True, config.COLOR_TEXT)
        quit_text = self.small_font.render("Quit Game (Q/B)", True, config.COLOR_TEXT)
        
        yes_rect = yes_text.get_rect(center=(config.SCREEN_WIDTH // 2, dialog_y + 130))
        no_rect = no_text.get_rect(center=(config.SCREEN_WIDTH // 2 - 100, dialog_y + 160))
        quit_rect = quit_text.get_rect(center=(config.SCREEN_WIDTH // 2 + 100, dialog_y + 160))
        
        self.screen.blit(yes_text, yes_rect)
        self.screen.blit(no_text, no_rect)
        self.screen.blit(quit_text, quit_rect)
    
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
        """Draw game over screen."""
        title = self.font.render("GAME OVER", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 300))
        self.screen.blit(title, title_rect)
        
        score_text = self.small_font.render(
            f"Final Score: {self.scoring.get_total_score()}",
            True, config.COLOR_TEXT
        )
        score_rect = score_text.get_rect(center=(config.SCREEN_WIDTH // 2, 350))
        self.screen.blit(score_text, score_rect)
        
        continue_text = self.small_font.render(
            "Press SPACE/A to Return to Menu",
            True, config.COLOR_TEXT
        )
        continue_rect = continue_text.get_rect(center=(config.SCREEN_WIDTH // 2, 400))
        self.screen.blit(continue_text, continue_rect)
    
    def run(self) -> None:
        """Main game loop."""
        while self.running:
            dt_ms = self.clock.tick(config.FPS)
            # Normalize delta time: 1.0 = 60fps, scales movement for frame independence
            dt = dt_ms / (1000.0 / config.FPS)
            
            self.handle_events()
            self.update(dt)
            self.draw()

