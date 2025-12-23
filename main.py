"""Main entry point for ASTRO VOID.

This module initializes Pygame, creates the game window, and starts the main
game loop. It serves as the application entry point.

Dependencies:
    - pygame: Graphics and game loop
    - game: Main game coordinator
    - config: Configuration constants

Usage:
    Run this module directly to start the game:
        python main.py
    
    Or use the provided run script:
        ./run.sh
"""

import pygame
import sys
import os
import config

# Import Game - handle both development and PyInstaller
# In PyInstaller, we need to work around the game.py vs game/ package naming conflict
if getattr(sys, 'frozen', False):
    # In frozen mode, we need to import game.py before the game package loads
    # The challenge: game.py imports other modules (entities, maze, etc.)
    # Solution: Pre-import key modules to ensure they're available, then load game.py
    base_path = sys._MEIPASS
    
    # CRITICAL: Ensure base_path is in sys.path so PyInstaller's import system works
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    # Pre-import modules that game.py needs to ensure they're available
    # We need to import exactly what game.py imports, matching the import statements
    # This ensures PyInstaller's import system has loaded them into sys.modules
    try:
        # Import exactly as game.py does - this ensures modules are in sys.modules
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
    except ImportError as e:
        # If pre-import fails, continue anyway - might still work
        # But log it for debugging
        import traceback
        traceback.print_exc()
    
    # Save and remove the game package to avoid naming conflict
    original_game_package = sys.modules.pop('game', None)
    
    try:
        import importlib.util
        import importlib.machinery
        import types
        
        game_module_path = os.path.join(base_path, 'game.py')
        
        if os.path.exists(game_module_path):
            # Load game.py as a module
            # Now that we've pre-imported the modules, they should be available
            loader = importlib.machinery.SourceFileLoader('_root_game', game_module_path)
            game_module = types.ModuleType('_root_game')
            game_module.__file__ = game_module_path
            game_module.__package__ = None
            game_module.__name__ = '_root_game'
            
            # Store in sys.modules with a unique name
            sys.modules['_root_game'] = game_module
            
            # Execute the module - imports should now work because modules are pre-loaded
            loader.exec_module(game_module)
            Game = game_module.Game
        else:
            raise ImportError(f"game.py not found at {game_module_path}")
    finally:
        # Restore the game package
        if original_game_package:
            sys.modules['game'] = original_game_package
else:
    # Development mode - use package import
    from game import Game


def main():
    """Initialize and run the game."""
    pygame.init()
    
    # Initialize joystick support for game controllers
    pygame.joystick.init()
    
    # Initialize mixer for sound support
    if config.SOUND_ENABLED:
        pygame.mixer.init(
            frequency=config.SOUND_SAMPLE_RATE,
            size=-16,  # 16-bit signed samples
            channels=2,  # Stereo
            buffer=512  # Small buffer for low latency
        )
    
    # Check for windowed mode: environment variable overrides settings.json
    windowed_env = os.getenv('WINDOWED')
    if windowed_env is not None:
        # Environment variable is set, use it
        windowed = windowed_env.lower() in ('1', 'true', 'yes', 'on')
    else:
        # Use settings.json: fullscreen=false means windowed=true
        windowed = not config.SCREEN_FULLSCREEN
    
    if windowed:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    else:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN)
    
    pygame.display.set_caption("ASTRO VOID - Space Navigation Game")
    
    # Update config with actual screen size (fullscreen may use different resolution)
    actual_width, actual_height = screen.get_size()
    config.SCREEN_WIDTH = actual_width
    config.SCREEN_HEIGHT = actual_height
    
    game = Game(screen)
    game.run()
    
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

