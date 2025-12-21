# ASTRO VOID

A skill-based space navigation game built with Pygame. Navigate procedurally-generated mazes using classic Asteroids-style momentum-based flight mechanics. Balance speed, fuel conservation, precision flying, and combat efficiency to achieve high scores.

## Features

- **Momentum-Based Physics**: Zero-G flight mechanics with realistic momentum and low friction
- **Procedural Maze Generation**: Each level features a unique procedurally-generated maze. Levels are deterministic - each level number always generates the same maze layout (Level 1 = seed 1, Level 2 = seed 2, etc.)
- **Multiple Enemy Types**:
  - Static enemies that remain stationary (but move when hit by projectiles)
  - Patrol enemies that move in straight lines
  - Aggressive enemies that chase the player
  - Replay enemy ships that mimic your previous playthrough
  - Egg enemies that grow over time and spawn Baby enemies when they hatch
  - Baby enemies - small, fast versions of Replay enemies
  - Split Boss - large enemies that split into two Replay enemies when destroyed
  - Mother Boss - even larger enemies that continuously lay Egg enemies
- **Resource Management**: Limited fuel and ammunition require strategic decision-making
- **Scoring System**: Score based on completion time, collisions, resource usage, and enemy destructions
- **Visual Effects**: Ship glow, thrust particles, enemy pulsing, and more
- **Sound System**: Procedurally-generated sound effects for thrusters, shooting, enemy destruction, and portal activation/deactivation
- **Progressive Difficulty**: Enemy count, speed, and strength scale with level
- **Momentum Physics**: Eggs and Static enemies gain momentum when hit by projectiles, moving with realistic physics and bouncing off walls
- **Exit Portal Lock**: Exit portal deactivates when eggs are present, requiring all eggs to be destroyed before level completion

## Requirements

- Python 3.8+
- pygame >= 2.5.0
- numpy >= 1.20.0

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd astrovoid
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Game

### Direct Execution

```bash
python main.py
```

### Using the Run Script

```bash
./run.sh
```

Note: The run script assumes a virtual environment at `venv/`. If you don't have one, create it first:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Controls

- **Arrow Keys**: Rotate ship (Left/Right) and apply thrust (Up)
- **Space**: Fire projectile
- **ESC**: Pause/Quit menu

## Gameplay

### Objective

Navigate through each maze level, reaching the exit (green) while managing resources and avoiding or destroying enemies.

**Important**: The exit portal is locked when any Egg enemies are present. You must destroy all eggs before the exit portal activates and allows level completion. The portal will dim and make a power-down sound when eggs are present, and brighten with a power-up sound when all eggs are destroyed.

### Scoring

Each level has a maximum score of 100 points. Your score is reduced by:

- **Time Penalty**: 1 point per second elapsed
- **Collision Penalty**: 5 points per collision (wall or enemy)
- **Ammo Penalty**: 0.1 points per shot fired
- **Fuel Penalty**: 0.01 points per unit of fuel used

**Bonuses**:

- Destroying enemies provides score bonuses

### Level Completion

When you complete a level, the screen displays:

- **Level Number**: "LEVEL {level} COMPLETE" (e.g., "LEVEL 1 COMPLETE")
- **Completion Time**: Shown with one decimal place (e.g., "Time: 1:23.4")
- **Star Rating**: 5-star rating based on score percentage
- **Score Breakdown**: Detailed breakdown of penalties and bonuses

### Resources

- **Fuel**: Consumed when thrusting or using shield. Starts at 1000 units.
- **Ammunition**: Consumed when firing. Starts at 50 rounds.

### Enemy Types

- **Static**: Stationary enemies that fire at the player when in range. When hit by projectiles, they gain momentum and move with physics, bouncing off walls. Require multiple hits to destroy.
- **Patrol**: Move in straight lines, reversing direction on wall collision
- **Aggressive**: Actively chase the player when alerted
- **Replay**: Purple ships that replay your previous successful attempt
- **Egg**: Stationary enemies that grow over time. When they reach maximum size, they hatch and spawn 1-3 Baby enemies. Can be destroyed by projectiles before hatching (requires 2 hits). When hit, they gain momentum and move with physics.
- **Baby**: Small, fast versions of Replay enemies that spawn when Eggs hatch
- **Split Boss**: Large enemies (2x size) that split into two Replay enemies when destroyed. Require 3 hits to destroy.
- **Mother Boss**: Very large enemies (3x size) that continuously lay Egg enemies. Require 5 hits to destroy. When destroyed, they split into two Replay enemies like Split Boss.

### Level Progression

- Maze size increases with level
- Enemy count and strength scale with level
- Replay enemy ships appear starting at level 1, increasing in count up to level 10
- **Deterministic Generation**: Each level uses its level number as the random seed, ensuring the same level always generates the same maze layout, enemy positions, and enemy distributions across playthroughs

## Project Structure

```
asterdroids/
├── main.py                 # Entry point
├── game.py                 # Main game coordinator
├── config.py               # Configuration constants
├── level_rules.py          # Level-based enemy scaling
├── requirements.txt        # Python dependencies
├── run.sh                  # Run script
├── entities/               # Game entities
│   ├── base.py            # Base entity class
│   ├── ship.py            # Player ship
│   ├── enemy.py           # Enemy entities
│   ├── enemy_strategies.py # Enemy behavior strategies
│   ├── replay_enemy_ship.py # Replay enemy implementation
│   ├── rotating_thruster_ship.py # Ship with rotating thrusters
│   ├── projectile.py      # Projectiles
│   ├── command_recorder.py # Command recording for replay
│   ├── egg.py             # Egg enemy that grows and spawns babies
│   ├── baby.py            # Baby enemy (small, fast replay enemy)
│   ├── split_boss.py      # Split Boss enemy
│   ├── mother_boss.py     # Mother Boss enemy that lays eggs
│   └── exit.py            # Exit portal with activation system
├── maze/                   # Maze generation
│   ├── generator.py       # Procedural maze generation
│   └── wall_segment.py    # Wall representation
├── scoring/               # Scoring system
│   ├── system.py         # Score tracking
│   └── calculator.py      # Score calculation
├── rendering/             # Rendering system
│   ├── renderer.py       # Centralized rendering
│   ├── ui_elements.py    # UI components
│   └── visual_effects.py  # Visual effects
├── input/                 # Input handling
│   └── input_handler.py  # Keyboard input mapping
├── sounds/                # Sound system
│   └── sound_manager.py  # Procedural sound generation (thrusters, shooting, explosions, portal sounds)
├── states/                # State management
│   └── state_machine.py  # State machine infrastructure
├── game_handlers/         # Game system handlers
│   ├── entity_manager.py # Entity management
│   ├── spawn_manager.py  # Enemy spawning system
│   ├── enemy_updater.py  # Enemy update logic
│   └── collision_handler.py # Collision detection and response
├── utils/                 # Utilities
│   ├── math_utils.py     # Math and collision utilities
│   └── spatial_grid.py   # Spatial partitioning
└── tests/                 # Unit tests
    └── README.md          # Test documentation
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Detailed architecture documentation
- **[API.md](API.md)**: API reference for public interfaces
- **[tests/README.md](tests/README.md)**: Test documentation

## Development

### Running Tests

```bash
pytest tests/
```

See [tests/README.md](tests/README.md) for detailed test documentation.

### Code Style

The codebase follows:

- SOLID principles
- DRY (Don't Repeat Yourself)
- Type hints for clarity
- Comprehensive docstrings

## License

MIT License

Copyright (c) 2025 Barry Earsman

See [LICENSE](LICENSE) file for details.
