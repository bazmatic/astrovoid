"""Main entry point for the Asteroids Maze Game.

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
    
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Asterdroids - Space Navigation Game")
    
    game = Game(screen)
    game.run()
    
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

