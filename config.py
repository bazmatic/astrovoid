"""Game configuration and constants.

This module centralizes all game configuration values including screen settings,
physics parameters, resource limits, scoring weights, difficulty scaling, and
visual settings. All constants should be defined here to make tuning easy.

Dependencies:
    - pygame: For color constants

Architecture:
    This module follows the Configuration Object pattern, providing a single
    source of truth for all game parameters. This makes it easy to:
    - Tune game balance
    - Adjust difficulty
    - Modify visual appearance
    - Test different configurations
"""

import pygame

# Screen settings
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# Ship physics
SHIP_SIZE = 6  # Ship radius (affects both collision and visual size)
SHIP_ROTATION_SPEED = 4.0  # Degrees per frame (how fast the ship rotates)
SHIP_THRUST_FORCE = 0.15  # Thrust power (acceleration per frame when thrusting)
SHIP_FRICTION = 0.998  # Very low friction for zero-G environment
SHIP_MAX_SPEED = 8.0

# Resources
INITIAL_FUEL = 1000
INITIAL_AMMO = 50
FUEL_CONSUMPTION_PER_THRUST = 1
AMMO_CONSUMPTION_PER_SHOT = 1

# Scoring system (100 point maximum per level)
MAX_LEVEL_SCORE = 100  # Maximum score per level
TIME_PENALTY_RATE = 1  # Points deducted per second of elapsed time
COLLISION_PENALTY = 5  # Points deducted per collision (wall or enemy)
AMMO_PENALTY_RATE = 0.1  # Points deducted per shot fired
FUEL_PENALTY_RATE = 0.01  # Points deducted per unit of fuel used

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
ENEMY_STUCK_DETECTION_THRESHOLD = 0.1  # Minimum distance change to consider enemy moving
ENEMY_SHIFT_ANGLE_MIN = 45  # Minimum angle shift in degrees (45-90 range)
ENEMY_SHIFT_ANGLE_MAX = 90  # Maximum angle shift in degrees
ENEMY_SHIFT_DURATION_MIN = 10  # Minimum frames to maintain shifted direction
ENEMY_SHIFT_DURATION_MAX = 100  # Maximum frames to maintain shifted direction
ENEMY_FIRE_INTERVAL_MIN = 60  # Minimum frames between shots (1 second at 60 FPS)
ENEMY_FIRE_INTERVAL_MAX = 300  # Maximum frames between shots (5 seconds at 60 FPS)
ENEMY_FIRE_RANGE = 400  # Maximum distance to player for firing (pixels)

# Projectile settings
PROJECTILE_SPEED = 10.0
PROJECTILE_SIZE = 4
PROJECTILE_LIFETIME = 120  # frames
COLOR_ENEMY_PROJECTILE = (255, 100, 100)  # Red/orange color for enemy bullets

# Visual effects
SHIP_GLOW_INTENSITY = 0.3
SHIP_GLOW_RADIUS_MULTIPLIER = 1.5
ENEMY_PULSE_SPEED = 0.05
ENEMY_PULSE_AMPLITUDE = 0.1
THRUST_PLUME_LENGTH = 15
THRUST_PLUME_PARTICLES = 5

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

# Gradient colors for ship
COLOR_SHIP_NOSE = (150, 220, 255)
COLOR_SHIP_REAR = (50, 150, 200)
COLOR_SHIP_DAMAGED_NOSE = (255, 150, 150)
COLOR_SHIP_DAMAGED_REAR = (200, 50, 50)

# Game states
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_LEVEL_COMPLETE = "level_complete"
STATE_GAME_OVER = "game_over"
STATE_QUIT_CONFIRM = "quit_confirm"

