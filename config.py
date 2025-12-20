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
SCREEN_WIDTH = 1480
SCREEN_HEIGHT = 900
FPS = 60

# Ship physics
SHIP_SIZE = 8  # Ship radius (affects both collision and visual size)
SHIP_ROTATION_SPEED = 5.0  # Degrees per frame (how fast the ship rotates)
SHIP_THRUST_FORCE = 0.15  # Thrust power (acceleration per frame when thrusting)
SHIP_FRICTION = 0.998  # Very low friction for zero-G environment
SHIP_MAX_SPEED = 8.0
COLLISION_RESTITUTION = 0.85  # Coefficient of restitution for ship-enemy collisions (0.0 = inelastic, 1.0 = elastic)

# Resources
INITIAL_FUEL = 1000
INITIAL_AMMO = 50
FUEL_CONSUMPTION_PER_THRUST = 1
AMMO_CONSUMPTION_PER_SHOT = 1
SHIELD_FUEL_CONSUMPTION_PER_FRAME = 2  # Fuel consumed per frame while shield is active

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
WALL_HIT_POINTS = 2  # Number of hits required to destroy a wall block

# Enemy settings
STATIC_ENEMY_SIZE = 10
DYNAMIC_ENEMY_SIZE = 8
ENEMY_PATROL_SPEED = 1
ENEMY_AGGRESSIVE_SPEED = 1.0
ENEMY_DAMAGE = 10
ENEMY_STUCK_DETECTION_THRESHOLD = 0.1  # Minimum distance change to consider enemy moving
ENEMY_SHIFT_ANGLE_MIN = 45  # Minimum angle shift in degrees (45-90 range)
ENEMY_SHIFT_ANGLE_MAX = 90  # Maximum angle shift in degrees
ENEMY_SHIFT_DURATION_MIN = 10  # Minimum frames to maintain shifted direction
ENEMY_SHIFT_DURATION_MAX = 100  # Maximum frames to maintain shifted direction
ENEMY_FIRE_INTERVAL_MIN = 60  # Minimum frames between shots (1 second at 60 FPS)
ENEMY_FIRE_INTERVAL_MAX = 300  # Maximum frames between shots (5 seconds at 60 FPS)
ENEMY_FIRE_RANGE = 400  # Maximum distance to player for firing (pixels)
REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE = 30.0  # Degrees - enemy fires when pointing within this angle of player

# Replay enemy settings
REPLAY_ENEMY_WINDOW_SIZE = 100  # Number of actions to store and replay
REPLAY_ENEMY_SIZE = 15  # Size/radius of replay enemy
REPLAY_ENEMY_COLOR = (150, 100, 255)  # Visual color for replay enemy (purple/violet)

# Projectile settings
PROJECTILE_SPEED = 8.0
PROJECTILE_SIZE = 3
PROJECTILE_LIFETIME = 120  # frames
COLOR_ENEMY_PROJECTILE = (255, 100, 100)  # Red/orange color for enemy bullets
PROJECTILE_IMPACT_FORCE = 0.3  # Velocity impulse applied to ship when hit by projectile (small effect)

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

# Exit portal settings
EXIT_PORTAL_ATTRACTION_RADIUS = 150  # Distance at which portal starts attracting player
EXIT_PORTAL_ATTRACTION_FORCE_MULTIPLIER = 0.5  # Attraction force as multiplier of ship thruster force (0.5 = half)
EXIT_PORTAL_GLOW_MULTIPLIER = 2.0  # Multiplier for glow size when player is nearby
COLOR_TEXT = (255, 255, 255)
COLOR_UI_BG = (20, 20, 30)

# Gradient colors for ship
COLOR_SHIP_NOSE = (150, 220, 255)
COLOR_SHIP_REAR = (50, 150, 200)
COLOR_SHIP_DAMAGED_NOSE = (255, 150, 150)
COLOR_SHIP_DAMAGED_REAR = (200, 50, 50)

# Sound settings
SOUND_ENABLED = True
SOUND_SAMPLE_RATE = 44100  # Standard CD quality
THRUSTER_SOUND_VOLUME = 0.05  # Volume level for thruster (0.0 to 1.0)
SHOOT_SOUND_VOLUME = 0.5  # Volume level for shoot sound (0.0 to 1.0)
ENEMY_DESTROY_SOUND_VOLUME = 0.6  # Volume level for enemy destruction sound (0.0 to 1.0)
EXIT_WARBLE_SOUND_VOLUME = 0.65  # Volume level for exit cosmic warble
POWERUP_ACTIVATION_SOUND_VOLUME = 0.6  # Volume level for powerup pickup phase sound
THRUSTER_NOISE_DURATION = 0.1  # Duration of white noise loop in seconds
SHOOT_BLIP_FREQUENCY = 800  # Frequency in Hz for 8-bit blip sound
SHOOT_BLIP_DURATION = 0.05  # Duration of blip sound in seconds

# Controller settings
CONTROLLER_DEADZONE = 0.2  # Deadzone threshold for analog sticks (0.0 to 1.0)
CONTROLLER_TRIGGER_THRESHOLD = 0.0  # Threshold for trigger activation (0.0 to 1.0)

# Powerup crystal settings
POWERUP_CRYSTAL_SIZE = 6
POWERUP_CRYSTAL_SPAWN_CHANCE = 0.3  # 30% chance to drop
POWERUP_CRYSTAL_ROTATION_SPEED = 2.0  # Degrees per frame
POWERUP_CRYSTAL_GLOW_INTENSITY = 0.6
COLOR_POWERUP_CRYSTAL = (150, 100, 255)  # Purple/cyan
POWERUP_CRYSTAL_ATTRACTION_RADIUS = 50  # Distance at which crystal starts moving towards player
POWERUP_CRYSTAL_ATTRACTION_SPEED = 1.0  # Speed at which crystal moves towards player
POWERUP_FLASH_DURATION_FRAMES = 18  # Frames the ship flashes when a powerup is collected
POWERUP_FLASH_TINT_STRENGTH = 0.85  # 0-1 blend of ship colors toward white during flash
POWERUP_FLASH_GLOW_MULTIPLIER = 1.6  # Extra glow intensity while flashing

# Gun upgrade settings
POWERUP_LEVEL_1_FIRE_RATE_MULTIPLIER = 1.5  # Level 1: 1.5x faster fire rate
POWERUP_LEVEL_2_FIRE_RATE_MULTIPLIER = 2.0  # Level 2: 2x faster fire rate
POWERUP_LEVEL_3_FIRE_RATE_MULTIPLIER = 3.0  # Level 3: 3x faster fire rate
UPGRADED_FIRE_RATE_MULTIPLIER = 2.0  # Deprecated: kept for backwards compatibility
UPGRADED_PROJECTILE_SPREAD_ANGLE = 15.0  # Degrees for 3-way spread (level 2+)
UPGRADED_PROJECTILE_SIZE_MULTIPLIER = 1.5
UPGRADED_PROJECTILE_SPEED_MULTIPLIER = 1.2
COLOR_UPGRADED_PROJECTILE = (150, 220, 255)  # Bright cyan
COLOR_UPGRADED_SHIP_GLOW = (150, 200, 255)  # Cyan glow

# Star animation settings
STAR_APPEAR_DURATION = 0.4  # Seconds per star appearance animation
STAR_TWINKLE_SPEED = 8.0  # Twinkle animation speed (radians per second)
STAR_TWINKLE_INTENSITY = 0.3  # Twinkle brightness variation (0.0 to 1.0)
STAR_TINKLE_BASE_PITCH = 800  # Hz for first star tinkling sound
STAR_TINKLE_PITCH_INCREMENT = 200  # Hz increase per star
LEVEL_COMPLETE_STAR_SIZE = 45  # Size of stars on level complete screen (pixels)

# Game states
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_LEVEL_COMPLETE = "level_complete"
STATE_GAME_OVER = "game_over"
STATE_QUIT_CONFIRM = "quit_confirm"

