"""Main entry point for the Asteroids Maze Game."""

import pygame
import sys
from game import Game
import config


def main():
    """Initialize and run the game."""
    pygame.init()
    
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Asterdroids - Space Navigation Game")
    
    game = Game(screen)
    game.run()
    
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

