# Squiddler

A skill-based space navigation game built with Pygame. Navigate procedurally-generated mazes using classic Asteroids-style momentum-based flight mechanics. Balance speed, fuel conservation, precision flying, and combat efficiency to achieve high scores.

## Features

- **Momentum-Based Physics**: Zero-G flight mechanics with realistic momentum and low friction
- **Procedural Maze Generation**: Each level features a unique procedurally-generated maze. Levels are deterministic - each level number always generates the same maze layout
- **Multiple Enemy Types**:
  - Static enemies that remain stationary (but move when hit by projectiles)
  - Patrol enemies that move in straight lines
  - Aggressive enemies that chase the player
  - Replay enemy ships that mimic your previous playthrough
  - Egg enemies that grow over time and spawn Baby enemies when they hatch
  - Baby enemies - small, fast versions of Replay enemies
  - Split Boss - large enemies that split into two Replay enemies when destroyed
  - Mother Boss - even larger enemies that continuously lay Egg enemies
  - Flockers that swarm together, Flighthouses that launch them, and Anemones that pull the ship in
- **Resource Management**: Limited fuel and ammunition require strategic decision-making
- **Scoring System**: Score based on completion time, collisions, resource usage, and enemy destructions
- **Visual Effects**: Ship glow, thrust particles, enemy pulsing, and more
- **Sound System**: Procedurally-generated sound effects for thrusters, shooting, enemy destruction, and portal activation/deactivation
- **Paced Levels**: A designed arc of 24 levels introduces one enemy type at a time, then an endless game that gets harder without getting more crowded
- **Boss Levels**: Every sixth level is a boss fight in an open arena
- **Momentum Physics**: Eggs and Static enemies gain momentum when hit by projectiles, moving with realistic physics and bouncing off walls
- **Exit Portal Lock**: Exit portal deactivates while any egg is alive, and on a boss level while any enemy is alive, requiring them to be destroyed before level completion

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

### Testing Switches

Set these in the environment when launching, for example `NO_POWER_DRAIN=1 ./run.sh`:

- `NO_POWER_DRAIN=1`: the power gauge stays full, so a level never fails and has no time limit. The score awarded on finishing a level is still calculated normally.
- `START_LEVEL=5`: start at the given level.
- `WINDOWED=1`: run in a window instead of fullscreen.

## Building Distributables

The project is set up to use PyInstaller to create standalone executables.

### Prerequisites

Install PyInstaller (included in requirements.txt):

```bash
pip install -r requirements.txt
```

### Building

**Windows:**
```bash
build.bat
```

**Linux/macOS:**
```bash
chmod +x build.sh
./build.sh
```

**Manual build:**
```bash
pyinstaller pyinstaller.spec
```

The executable will be created in the `dist/` folder. On Windows, it will be `dist/Squiddler/Squiddler.exe`. On Linux/macOS, it will be `dist/Squiddler/Squiddler`.

### Build Output

- **One-file executable**: The build creates a single executable file that includes all dependencies and data files (assets, config, levels).
- **No console window**: The executable runs without a console window (windowed application).
- **All resources bundled**: Assets, configuration files, and level data are automatically included in the executable.

### Notes

- The build process includes all necessary files (assets, config, levels) automatically.
- The executable is self-contained and doesn't require Python or any dependencies to be installed on the target system.
- For cross-platform builds, you must build on each target platform (Windows builds on Windows, Linux builds on Linux, etc.).

## Controls

- **Arrow Keys**: Rotate ship (Left/Right) and apply thrust (Up)
- **Space**: Fire projectile
- **ESC**: Pause/Quit menu

## Gameplay

### Objective

Navigate through each maze level, reaching the exit (green) while managing resources and avoiding or destroying enemies.

**Important**: The exit portal is locked while any Egg is alive. On a boss level it is locked until every enemy is destroyed: the bosses, their escorts, the two Replay ships a boss leaves behind when it dies, and any Babies that hatch. The portal dims and makes a power-down sound while it is locked, and brightens with a power-up sound when the last one is destroyed.

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
- **Ammunition**: Consumed when firing. Starts at 50 rounds. Infinite on boss levels.

### Enemy Types

- **Static**: Stationary enemies that fire at the player when in range. When hit by projectiles, they gain momentum and move with physics, bouncing off walls. Require multiple hits to destroy.
- **Patrol**: Move in straight lines, reversing direction on wall collision
- **Aggressive**: Actively chase the player when alerted
- **Replay**: Purple ships that replay your previous successful attempt
- **Egg**: Stationary enemies that grow over time. When they reach maximum size, they hatch and spawn 1-3 Baby enemies. Can be destroyed by projectiles before hatching (requires 2 hits). When hit, they gain momentum and move with physics.
- **Baby**: Small, fast versions of Replay enemies that spawn when Eggs hatch
- **Split Boss**: Large enemies (2x size) that split into two Replay enemies when destroyed. Require 8 hits to destroy.
- **Mother Boss**: Very large enemies (3x size) that continuously lay Egg enemies. Require 20 hits to destroy. When destroyed, they split into two Replay enemies like Split Boss.

### Level Progression

**Levels 1 to 24** are a designed arc. Each has its own file in `levels/` and introduces at most one new thing:

| Level | New |
|---|---|
| 1 | Static enemies |
| 2 | Patrol enemies |
| 3 | Aggressive enemies |
| 4 | The Jev hunter, your ally |
| 5 | Replay ships |
| 6 | **Boss level**: Split Boss |
| 7 | Anemones |
| 8 | Flocker swarms |
| 10 | Flighthouses |
| 12 | **Boss level**: two Split Bosses |
| 13 | Eggs |
| 18 | **Boss level**: Mother Boss |
| 24 | **Boss level**: Mother Boss and Split Boss |

- The maze grows from 10 cells across to 32, and the enemy count from 4 to 24, rising by no more than 2 from one ordinary level to the next.
- **Boss levels** are small open arenas with a boss and a few escorts. The exit stays locked until every enemy on the level is dead, ammo is infinite, and the hunter does not fly.

**From level 25** the game is endless:

- The enemy count starts at 25 and rises by one every two levels, stopping at 36. The maze stays at 32 cells across.
- Every sixth level (30, 36, 42, ...) is a boss level: Split Bosses, then a Mother Boss, then both, building up to three bosses on a level.
- Enemy speed and damage grow 5% a level after level 4 and stop at 2.5 times. Enemy fire range stops at 600 pixels.

On every level, no enemy starts within 300 pixels of your ship.

- **Deterministic Generation**: Each level uses a fixed random seed (100 + level for the arc, the level number after it), ensuring the same level always generates the same maze layout, enemy positions, and enemy distributions across playthroughs

The level file format and the pacing rules are described in [levels/README.md](levels/README.md).

### Replaying and personal bests

**LEVELS** on the main menu opens a grid of unlocked levels, with best stars and
score/time records for each. Replaying an earlier level can improve these records
without adding to your progress score or changing your furthest level. CONTINUE moves
to the next level and resumes ordinary progress when you reach your furthest level.

Press **R** or controller **Y** during play to restart immediately. During power-out,
any other key or button skips to the failed screen. Each successful clear records
independent bests for score, time, and stars; the completion screen shows the gaps
or celebrates new records. Existing profiles pick up records as levels are cleared.
Records set before the levels were re-paced are cleared once, the first time the game
loads the profile; your furthest level and total score are kept.

Stars require at least **20 / 40 / 60 / 80 / 95 points** for one through five
stars respectively. Below 20 points earns no stars. Previously earned star records
are retained when the balance changes.

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
│   ├── anemone.py         # Anemone enemy that pulls the ship toward it
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
│   ├── dial.py           # HUD instrument dials
│   ├── fonts.py          # The game typeface (Chakra Petch)
│   ├── controls_menu.py  # Key and button mappings screen
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

## Configuration

- All the tuning constants (screen dimensions, enemy behavior, maze presets, UI colors, etc.) live in `config/settings.json`. Edit this file to tweak the experience and keep everything organized by section.
- `config.py` loads the JSON into typed dataclasses and exposes the legacy uppercase names for backward compatibility (e.g., `config.SCREEN_WIDTH`) while also providing `config.SETTINGS` for new code that prefers structured access.
- When updating `config/settings.json`, rerun the game or tests to reload the new configuration.

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

## Jev hunter ally

A level can include one independent allied ship piloted by TypeSafe's Jev model.
Jev chooses turning, thrust and firing from local sensors and remembered sightings.
Enemies can target and destroy it. It has three hit points, no friendly fire, and
starts with fresh memory each level. Hunter kills do not award personal kill points.

The optional pilot requires Python 3.10+ (the base game does not require the SDK):

```bash
venv/bin/python -m pip install -r requirements-hunter.txt
```

Set `TYPESAFE_API_KEY` in the launch environment. `TYPESAFE_DEFAULT_MODEL` optionally
selects a model; the default is `jev-latest`. To enter the key privately for one run:

```bash
venv/bin/python -c 'import getpass, os, runpy; os.environ["TYPESAFE_API_KEY"] = getpass.getpass("TypeSafe API key: "); runpy.run_path("main.py", run_name="__main__")'
```

Opt in through a level's JSON file; see [level configuration](levels/README.md).
One hunter appears on every level from level 4 (`game.hunterFirstLevel` in `config/settings.json`), except boss levels; `game.hunterLevelInterval` spaces them out. A level file can place one anywhere or forbid one. It starts when you make your
first move. It is indestructible: enemy shots and contact knock it about without
damaging it. Without a key/SDK, the hunter coasts with an unavailable pilot.

Decisions are requested at most four times per second, with one request in flight.
Steering is held like a key: a turn continues until a later decision releases or
reverses it, and the held steering is part of what the pilot is told. The hunter
turns at half the player's rate so that decisions arriving a few times a second
can stop a turn on target.

Alongside its sensor readings the pilot is given worked calculations: time to wall
impact when coasting, a braking solution (safe speed for the wall on its course and
the attitude needed to slow down), and a lead-aim firing solution for each visible enemy.

Whenever no enemy is in sight the hunter follows the player: it is given the next
waypoint on a route through the maze to the player's ship and holds station when it
arrives. It does not explore on its own.
Inputs expire 750 ms after their sensor snapshot; expired inputs stop turning,
thrust and firing while momentum continues. Requests time out after one second.
There is no local autopilot fallback. Constants are in `hunter/model.py`.

For the local setup, run `./run-hunter.sh` to select level 4, the first with the hunter. Both this launcher
and `./run.sh` read `.astrovoid-local/typesafe-api-key` when no API key is already
set in the environment. That directory is ignored by Git; the local key file
should remain readable only by its owner. The launcher reads it as plain data.
