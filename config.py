"""Game configuration and constants."""

import pygame

# Screen settings
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Ship physics
SHIP_SIZE = 10  # Ship radius (affects both collision and visual size)
SHIP_ROTATION_SPEED = 3.0  # Degrees per frame (how fast the ship rotates)
SHIP_THRUST_FORCE = 0.15  # Thrust power (acceleration per frame when thrusting)
SHIP_FRICTION = 0.998  # Very low friction for zero-G environment
SHIP_MAX_SPEED = 8.0

# Resources
INITIAL_FUEL = 1000
INITIAL_AMMO = 50
FUEL_CONSUMPTION_PER_THRUST = 1
AMMO_CONSUMPTION_PER_SHOT = 1

# Scoring weights
SCORE_TIME_WEIGHT = 1000
SCORE_FUEL_WEIGHT = 10
SCORE_AMMO_WEIGHT = 20
SCORE_COLLISION_PENALTY = 50

# Difficulty scaling
BASE_MAZE_SIZE = 15  # Larger base maze to fill screen
MAZE_SIZE_INCREMENT = 2
BASE_ENEMY_COUNT = 2
ENEMY_COUNT_INCREMENT = 1

# Maze settings
WALL_THICKNESS = 6
# Cell size will be calculated dynamically to fill screen
CELL_SIZE = None  # Will be calculated based on screen size
MIN_PASSAGE_WIDTH = 3  # Wider passages (3+ cells wide)

# Enemy settings
STATIC_ENEMY_SIZE = 15
DYNAMIC_ENEMY_SIZE = 12
ENEMY_PATROL_SPEED = 1.5
ENEMY_AGGRESSIVE_SPEED = 2.0
ENEMY_DAMAGE = 10

# Projectile settings
PROJECTILE_SPEED = 10.0
PROJECTILE_SIZE = 4
PROJECTILE_LIFETIME = 120  # frames

# Colors
COLOR_BACKGROUND = (10, 10, 20)
COLOR_SHIP = (100, 200, 255)
COLOR_WALLS = (150, 150, 150)
COLOR_ENEMY_STATIC = (255, 100, 100)
COLOR_ENEMY_DYNAMIC = (255, 150, 50)
COLOR_PROJECTILE = (255, 255, 100)
COLOR_EXIT = (50, 255, 50)
COLOR_START = (50, 150, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_UI_BG = (20, 20, 30)

# Game states
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_LEVEL_COMPLETE = "level_complete"
STATE_GAME_OVER = "game_over"

