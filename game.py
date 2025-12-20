"""Main game loop and state management."""

import pygame
import time
import random
from typing import List, Optional, Tuple
import config
from entities.ship import Ship
from maze import Maze
from entities.enemy import Enemy, create_enemies
import level_rules
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.projectile import Projectile
from entities.powerup_crystal import PowerupCrystal
from entities.command_recorder import CommandRecorder, CommandType
from input import InputHandler
from scoring import ScoringSystem
from rendering import Renderer
from rendering.ui_elements import AnimatedStarRating
from sounds import SoundManager


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
        self.level = 1
        self.ship: Optional[Ship] = None
        self.maze: Optional[Maze] = None
        self.enemies: List[Enemy] = []
        self.replay_enemies: List[ReplayEnemyShip] = []
        self.projectiles: List[Projectile] = []
        self.powerup_crystals: List[PowerupCrystal] = []
        self.scoring = ScoringSystem()
        self.sound_manager = SoundManager()  # Game-level sound manager for enemy destruction
        self.command_recorder = CommandRecorder()  # Record player commands for replay enemy
        self.input_handler = InputHandler()  # Handle keyboard input and map to commands
        
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
        
        # Create enemies
        enemy_counts = level_rules.get_enemy_counts(self.level)
        spawn_positions = self.maze.get_valid_spawn_positions(
            enemy_counts.total + enemy_counts.replay + 5  # Extra buffer for spawn positions
        )
        self.enemies = create_enemies(self.level, spawn_positions)
        
        # Create replay enemy ships
        replay_enemy_count = enemy_counts.replay
        self.replay_enemies = []
        
        if len(spawn_positions) > 0 and replay_enemy_count > 0:
            # Use available spawn positions for replay enemies
            # Skip positions already used by regular enemies
            used_positions = [e.get_pos() for e in self.enemies]
            available_positions = [pos for pos in spawn_positions if pos not in used_positions]
            
            # Create replay enemies at available positions
            for i in range(min(replay_enemy_count, len(available_positions))):
                replay_spawn = available_positions[i]
                replay_enemy = ReplayEnemyShip(replay_spawn, self.command_recorder)
                replay_enemy.current_replay_index = 0  # Reset replay index
                self.replay_enemies.append(replay_enemy)
        
        # Clear projectiles and crystals
        self.projectiles = []
        self.powerup_crystals = []
        
        # Start scoring
        current_time = time.time()
        self.scoring.start_level(current_time)
        
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
                # Handle controller button presses for menu navigation
                if self.state == config.STATE_MENU:
                    if self.input_handler.is_controller_menu_confirm_pressed(event.button):
                        self.state = config.STATE_PLAYING
                        self.level = 1
                        self.start_level()
                    elif self.input_handler.is_controller_menu_cancel_pressed(event.button):
                        # Quit game from menu
                        self.running = False
                elif self.state == config.STATE_PLAYING:
                    if self.input_handler.is_controller_quit_pressed(event.button):
                        # Show quit confirmation
                        self.state = config.STATE_QUIT_CONFIRM
                elif self.state == config.STATE_QUIT_CONFIRM:
                    if self.input_handler.is_controller_menu_confirm_pressed(event.button):
                        # Confirm quit - return to menu and reset progress
                        self.state = config.STATE_MENU
                        self.level = 1
                        self.scoring = ScoringSystem()
                    elif event.button == 1:  # B button - quit game completely
                        # Quit game completely
                        self.running = False
                    elif self.input_handler.is_controller_menu_cancel_pressed(event.button):
                        # Cancel quit - return to playing
                        self.state = config.STATE_PLAYING
                elif self.state == config.STATE_LEVEL_COMPLETE:
                    if self.level_complete_quit_confirm:
                        # Handle quit confirmation
                        if self.input_handler.is_controller_menu_confirm_pressed(event.button):
                            # Confirm quit - return to menu, keep progress
                            self.state = config.STATE_MENU
                            self.level_complete_quit_confirm = False
                        elif self.input_handler.is_controller_menu_cancel_pressed(event.button):
                            # Cancel quit - return to level complete
                            self.level_complete_quit_confirm = False
                    else:
                        # Normal level complete screen
                        if self.input_handler.is_controller_menu_confirm_pressed(event.button):
                            # Continue to next level (only if level succeeded)
                            if self.level_succeeded:
                                self.level += 1
                                self.state = config.STATE_PLAYING
                                self.start_level()
                            else:
                                # If failed, replay is the only option
                                self.scoring.total_score = self.total_score_before_level
                                self.state = config.STATE_PLAYING
                                self.start_level()
                        elif event.button == 1:  # B button for replay
                            # Replay current level - restore score and restart
                            self.scoring.total_score = self.total_score_before_level
                            self.state = config.STATE_PLAYING
                            self.start_level()
                        elif self.input_handler.is_controller_menu_cancel_pressed(event.button):
                            # Show quit confirmation
                            self.level_complete_quit_confirm = True
                elif self.state == config.STATE_GAME_OVER:
                    if self.input_handler.is_controller_menu_confirm_pressed(event.button):
                        self.state = config.STATE_MENU
                        self.level = 1
                        self.scoring = ScoringSystem()
            elif event.type == pygame.KEYDOWN:
                if self.state == config.STATE_MENU:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.state = config.STATE_PLAYING
                        self.level = 1
                        self.start_level()
                    elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                        # Quit game from menu
                        self.running = False
                elif self.state == config.STATE_PLAYING:
                    if event.key == pygame.K_ESCAPE:
                        # Show quit confirmation
                        self.state = config.STATE_QUIT_CONFIRM
                elif self.state == config.STATE_QUIT_CONFIRM:
                    if event.key == pygame.K_y or event.key == pygame.K_RETURN:
                        # Confirm quit - return to menu and reset progress
                        self.state = config.STATE_MENU
                        self.level = 1
                        self.scoring = ScoringSystem()
                    elif event.key == pygame.K_q:
                        # Quit game completely
                        self.running = False
                    elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
                        # Cancel quit - return to playing
                        self.state = config.STATE_PLAYING
                elif self.state == config.STATE_LEVEL_COMPLETE:
                    if self.level_complete_quit_confirm:
                        # Handle quit confirmation
                        if event.key == pygame.K_y or event.key == pygame.K_RETURN:
                            # Confirm quit - return to menu, keep progress
                            self.state = config.STATE_MENU
                            self.level_complete_quit_confirm = False
                        elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
                            # Cancel quit - return to level complete
                            self.level_complete_quit_confirm = False
                    else:
                        # Normal level complete screen
                        if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                            # Continue to next level (only if level succeeded)
                            if self.level_succeeded:
                                self.level += 1
                                self.state = config.STATE_PLAYING
                                self.start_level()
                            else:
                                # If failed, replay is the only option
                                self.scoring.total_score = self.total_score_before_level
                                self.state = config.STATE_PLAYING
                                self.start_level()
                        elif event.key == pygame.K_r:
                            # Replay current level - restore score and restart
                            self.scoring.total_score = self.total_score_before_level
                            self.state = config.STATE_PLAYING
                            self.start_level()
                        elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                            # Show quit confirmation
                            self.level_complete_quit_confirm = True
                elif self.state == config.STATE_GAME_OVER:
                    if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        self.state = config.STATE_MENU
                        self.level = 1
                        self.scoring = ScoringSystem()
    
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
        
        # Execute movement commands on ship and record them
        # Filter out shield command since it's handled separately above
        for cmd in commands:
            if cmd == CommandType.ACTIVATE_SHIELD:
                continue  # Shield already handled above
            self._execute_ship_command(cmd)
            self.command_recorder.record_command(cmd)
        
        # Handle fire separately (has rate limiting)
        # Check both keyboard and controller for fire input
        fire_key_pressed = keys[pygame.K_SPACE]
        fire_controller_pressed = self.input_handler.is_controller_fire_pressed()
        fire_pressed = fire_key_pressed or fire_controller_pressed
        
        if fire_pressed:
            if not hasattr(self, 'last_shot_time'):
                self.last_shot_time = 0
            current_time = pygame.time.get_ticks()
            # Adjust fire rate based on upgrade status
            fire_cooldown = 200  # Default 200ms between shots
            if self.ship.is_gun_upgraded_active():
                fire_cooldown = int(200 / config.UPGRADED_FIRE_RATE_MULTIPLIER)  # Faster when upgraded
            
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
        
        # Update enemies
        player_pos = (self.ship.x, self.ship.y) if self.ship else None
        for enemy in self.enemies:
            if enemy.active:
                enemy.update(dt, player_pos, self.maze.walls)
                
                # Check enemy-ship collision (skip if shield is active)
                if not self.ship.is_shield_active():
                    if self.ship.check_circle_collision(enemy.get_pos(), enemy.radius, enemy):
                        self.scoring.record_enemy_collision()
                
                # Check if enemy fired a projectile
                fired_projectile = enemy.get_fired_projectile(player_pos)
                if fired_projectile:
                    self.projectiles.append(fired_projectile)
        
        # Update replay enemies
        # Replay enemies update independently from the player ship.
        # They replay commands but handle collisions based on their own position/velocity state.
        # Pass player position for NO_ACTION behavior (rotate towards player) and firing.
        for replay_enemy in self.replay_enemies:
            if not replay_enemy.active:
                continue
            
            replay_enemy.update(dt, player_pos)
            
            # Check replay enemy-wall collision
            # This uses the replay enemy's own state (prev_x, prev_y, x, y, vx, vy)
            # and is completely independent from the player ship's collisions.
            # The replay enemy only bounces when it actually hits a wall at its position.
            if replay_enemy.check_wall_collision(self.maze.walls, self.maze.spatial_grid):
                pass  # Replay enemy bounces off walls (handled in base class using its own state)
            
            # Check replay enemy-ship collision (skip if shield is active)
            if not self.ship.is_shield_active():
                if self.ship.check_circle_collision(replay_enemy.get_pos(), replay_enemy.radius, replay_enemy):
                    self.scoring.record_enemy_collision()
            
            # Check if replay enemy fired a projectile
            fired_projectile = replay_enemy.get_fired_projectile(player_pos)
            if fired_projectile:
                self.projectiles.append(fired_projectile)
        
        # Update projectiles (use list comprehension instead of remove)
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
            
            # Check enemy projectile-ship collision (skip if shield is active)
            if projectile.is_enemy and projectile.active:
                if not self.ship.is_shield_active():
                    if projectile.check_circle_collision((self.ship.x, self.ship.y), self.ship.radius):
                        self.scoring.record_enemy_collision()  # Apply collision penalty
                        # Apply small velocity impulse to ship from projectile impact
                        # Transfer momentum in direction projectile was traveling
                        self.ship.vx += projectile.vx * config.PROJECTILE_IMPACT_FORCE
                        self.ship.vy += projectile.vy * config.PROJECTILE_IMPACT_FORCE
                        # Projectile is deactivated by collision, skip adding to active list
                        continue
            
            # Check projectile-enemy collision (only for player projectiles)
            if not projectile.is_enemy:
                for enemy in self.enemies:
                    if enemy.active and projectile.active:
                        if projectile.check_circle_collision(enemy.get_pos(), enemy.radius):
                            enemy_pos = enemy.get_pos()
                            enemy.destroy()
                            self.sound_manager.play_enemy_destroy()  # Play destruction sound
                            self.scoring.record_enemy_destroyed()  # Award bonus points
                            
                            # Spawn powerup crystal with probability
                            if random.random() < config.POWERUP_CRYSTAL_SPAWN_CHANCE:
                                crystal = PowerupCrystal(enemy_pos)
                                self.powerup_crystals.append(crystal)
                            
                            # Projectile is deactivated by collision, break
                            break
                
                # Check projectile-replay enemy collision
                for replay_enemy in self.replay_enemies:
                    if replay_enemy.active and projectile.active:
                        if projectile.check_circle_collision(replay_enemy.get_pos(), replay_enemy.radius):
                            enemy_pos = replay_enemy.get_pos()
                            replay_enemy.active = False  # Destroy replay enemy
                            self.sound_manager.play_enemy_destroy()  # Play destruction sound
                            self.scoring.record_enemy_destroyed()  # Award bonus points
                            
                            # Spawn powerup crystal with probability
                            if random.random() < config.POWERUP_CRYSTAL_SPAWN_CHANCE:
                                crystal = PowerupCrystal(enemy_pos)
                                self.powerup_crystals.append(crystal)
                            
                            break  # Projectile destroyed, stop checking
            
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
            if crystal.check_circle_collision((self.ship.x, self.ship.y), self.ship.radius):
                # Collect crystal and activate upgrade
                self.ship.activate_gun_upgrade()
                continue  # Don't add to active list
            
            if crystal.active:
                active_crystals.append(crystal)
        
        self.powerup_crystals = active_crystals
        
        # Check exit reached
        if self.maze.check_exit_reached((self.ship.x, self.ship.y), self.ship.radius):
            if not self.exit_explosion_active:
                # Start exit explosion
                self.exit_explosion_active = True
                self.exit_explosion_time = 0.0
                self.exit_explosion_pos = self.maze.exit_pos
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

