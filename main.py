"""Main entry point for ASTER VOID.

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
from game import Game
import config


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
    
    # Check for windowed mode via environment variable
    windowed = os.getenv('WINDOWED', '').lower() in ('1', 'true', 'yes', 'on')
    
    if windowed:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    else:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN)
    
    pygame.display.set_caption("ASTER VOID - Space Navigation Game")
    
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

