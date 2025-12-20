# Asterdroids

A skill-based space navigation game built with Pygame. Navigate procedurally-generated mazes using classic Asteroids-style momentum-based flight mechanics. Balance speed, fuel conservation, precision flying, and combat efficiency to achieve high scores.

## Features

- **Momentum-Based Physics**: Zero-G flight mechanics with realistic momentum and low friction
- **Procedural Maze Generation**: Each level features a unique procedurally-generated maze
- **Multiple Enemy Types**:
  - Static enemies that remain stationary
  - Patrol enemies that move in straight lines
  - Aggressive enemies that chase the player
  - Replay enemy ships that mimic your previous playthrough
- **Resource Management**: Limited fuel and ammunition require strategic decision-making
- **Scoring System**: Score based on completion time, collisions, resource usage, and enemy destructions
- **Visual Effects**: Ship glow, thrust particles, enemy pulsing, and more
- **Sound System**: Procedurally-generated sound effects for thrusters, shooting, and enemy destruction
- **Progressive Difficulty**: Enemy count, speed, and strength scale with level

## Requirements

- Python 3.8+
- pygame >= 2.5.0
- numpy >= 1.20.0

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd asterdroids
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

### Scoring

Each level has a maximum score of 100 points. Your score is reduced by:

- **Time Penalty**: 1 point per second elapsed
- **Collision Penalty**: 5 points per collision (wall or enemy)
- **Ammo Penalty**: 0.1 points per shot fired
- **Fuel Penalty**: 0.01 points per unit of fuel used

**Bonuses**:

- Destroying enemies provides score bonuses

### Resources

- **Fuel**: Consumed when thrusting or using shield. Starts at 1000 units.
- **Ammunition**: Consumed when firing. Starts at 50 rounds.

### Enemy Types

- **Static**: Stationary enemies that fire at the player when in range
- **Patrol**: Move in straight lines, reversing direction on wall collision
- **Aggressive**: Actively chase the player when alerted
- **Replay**: Purple ships that replay your previous successful attempt

### Level Progression

- Maze size increases with level
- Enemy count and strength scale with level
- Replay enemy ships appear starting at level 1, increasing in count up to level 10

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
│   └── command_recorder.py # Command recording for replay
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
│   └── sound_manager.py  # Procedural sound generation
├── states/                # State management
│   └── state_machine.py  # State machine infrastructure
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

[Add your license here]
