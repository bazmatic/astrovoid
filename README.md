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
- **Destructible Rock**: Maze walls are solid blocks of rock that crack under fire and can be blasted away a block at a time
- **Powerup Crystals**: Short-lived gun upgrades dropped by destroyed enemies
- **Scoring System**: Score based on completion time, collisions, resource usage, and enemy destructions
- **Visual Effects**: Ship glow, thrust particles, enemy pulsing, and more
- **Animated Splash**: A giant squid chases the ship up the screen and settles over the title
- **Sound System**: Procedurally-generated sound effects for thrusters, shooting, enemy destruction, and portal activation/deactivation
- **Paced Levels**: A designed arc of 24 levels introduces one enemy type at a time, then an endless game that gets harder without getting more crowded
- **Boss Levels**: Every sixth level is a boss fight in an open arena
- **Momentum Physics**: Eggs and Static enemies gain momentum when hit by projectiles, moving with realistic physics and bouncing off walls
- **Exit Portal Lock**: Exit portal deactivates while any egg is alive, and on a boss level while any enemy is alive, requiring them to be destroyed before level completion

## Requirements

- Python 3.10 to 3.13 (3.13 recommended; see [Troubleshooting](#troubleshooting))
- pygame >= 2.5.0
- numpy >= 1.20.0

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd astrovoid
```

2. Create a virtual environment in `venv/` (the location `run.sh` expects) and install the dependencies:

```bash
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Check that sound is available, then start the game:

```bash
venv/bin/python -c "import pygame.mixer; pygame.mixer.init(); print('mixer ok')"
./run.sh
```

4. Optional: enable the Jev hunter ally. Install its SDK and add your TypeSafe API key:

```bash
venv/bin/python -m pip install -r requirements-hunter.txt
mkdir -p .astrovoid-local
printf '%s' 'YOUR_KEY_HERE' > .astrovoid-local/typesafe-api-key
chmod 600 .astrovoid-local/typesafe-api-key
```

`.astrovoid-local/` is git-ignored. `run.sh` reads the key file only when `TYPESAFE_API_KEY` is not already set, and running `python main.py` directly skips the file. Without a key the game still runs, but the hunter coasts. See [Jev hunter ally](#jev-hunter-ally).

### Troubleshooting

- **`NotImplementedError: mixer module not available`**: pygame was built from source without SDL2_mixer. This happens on Python 3.14, which has no prebuilt pygame wheels. Recreate the venv with Python 3.13 (`rm -rf venv && python3.13 -m venv venv`), then reinstall the requirements.
- **`objc: Class SDL... is implemented in both ...` warnings on macOS**: `opencv-python` bundles its own SDL2, which clashes with pygame's. The warnings are noisy but usually harmless.
- **`./run.sh: venv/bin/python: No such file or directory`**: create the virtual environment from step 2 first.

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

### Splash Screen

The game opens with a short animated splash (about five seconds) before the main menu. Any key or controller button skips it. To turn it off, set `ui.splashEnabled` to `false` in `config/settings.json`.

### Testing Switches

Set these in the environment when launching, for example `NO_POWER_DRAIN=1 ./run.sh`:

- `NO_POWER_DRAIN=1`: the power gauge stays full, so a level never fails and has no time limit. The score awarded on finishing a level is still calculated normally.
- `START_LEVEL=5`: start at the given level.
- `WINDOWED=1`: run in a window instead of fullscreen. The window shrinks to fit the screen (keeping its shape) when the configured size is too big; `WINDOW_SIZE=1352x878` sets an exact size instead.
- `ASTROVOID_OBSERVER=1`: the player becomes an invulnerable observer that enemies cannot see. Enemy shots, contacts and wall hits cost nothing (the ship still stops at walls), the ship is drawn only as a faint shape (so you can still steer by sight), enemies and the hunter do not see or target it, and power never drains. The ship still flies and fires. Combine it with `ASTROVOID_HUNTER_HOTKEY=1` and `game.hunterPilot` to watch a pilot fly.

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
- **Star Rating**: up to five stars, and under them the goals, each marked met or missed (see [Stars](#stars))
- **Score Breakdown**: Detailed breakdown of penalties and bonuses

A failed level shows the "LEVEL FAILED" banner flanked by two of the game's squids, with your progress score and the option to retry.

### Resources

- **Fuel**: Consumed when thrusting or using shield. Starts at 1000 units.
- **Ammunition**: Consumed when firing. Starts at 50 rounds. Infinite on boss levels.

### Powerup Crystals

A destroyed enemy has a 30% chance of leaving a green crystal. Flying near one pulls it in. Each crystal:

- **Upgrades the gun** by one level. The first doubles the fire rate; from the second, each pull of the trigger is a three-way spread. Every crystal adds the same amount of firepower (one base gun's worth of shots per second) rather than multiplying it, so a spread fires at a slower rhythm than the single shots before it. Upgraded shots are larger and faster, and the ship turns a little quicker.
- **Refills 25 rounds** of ammunition, up to the full 50.
- **Halves the cost of firing** while the upgrade lasts. A spread costs the same as a single shot. Ammunition is no longer unlimited, so an upgraded gun can still run dry.

Upgrades are temporary. They last 10 seconds from the most recent crystal, then all wear off together and the gun returns to normal. The bar under the "GUN UPGRADE" label on the HUD shows the time left. Upgrades are also cleared at the start of each level.

The numbers are in `config/settings.json` under `powerups`: `durationSeconds`, `firepowerPerCrystal`, `ammoRefill`, `ammoCostMultiplier` and `crystalSpawnChance`.

### Walls

The maze is built from solid blocks of rock. A block has walls only where it faces open space, so blocks packed together form one mass with nothing inside to fly through.

- Your shots wear a block down. It takes 4 hits from any side (`maze.wallHitPoints`), and each one knocks chips loose, darkens the rock and breaks a chunk out of the edge where it landed, with cracks running in from the wound. Shots in the same place open the same wound further. The last hit bursts the whole block into rubble.
- Destroying a block exposes the faces of its neighbours, so you can tunnel through thick rock one block at a time.
- The outer ring of blocks bounds the playing area. It chips and cracks under fire, but its last hit point never goes, so it can never be destroyed. Its damage is rougher than an inner block's: bites range from a chip to a deep gouge, and the rock is stained around each wound instead of darkening as a whole block.
- Enemy shots stop at walls without damaging them.

### Enemy Types

- **Static**: Stationary enemies that fire at the player when in range. When hit by projectiles, they gain momentum and move with physics, bouncing off walls. Require multiple hits to destroy.
- **Patrol**: Move in straight lines, reversing direction on wall collision
- **Aggressive**: Actively chase the player when alerted
- **Replay**: Purple ships that replay your previous successful attempt
- **Egg**: Stationary enemies that grow over time. When they reach maximum size, they hatch and spawn 1-3 Baby enemies. Can be destroyed by projectiles before hatching (requires 2 hits). When hit, they gain momentum and move with physics.
- **Baby**: Small, fast versions of Replay enemies that spawn when Eggs hatch (a level's layout can also place them)
- **Split Boss**: Large enemies (2x size) that split into two Replay enemies when destroyed. Require 8 hits to destroy.
- **Mother Boss**: Very large enemies (3x size) that continuously lay Egg enemies. Require 20 hits to destroy. When destroyed, they split into two Replay enemies like Split Boss.
- **Rules hunter**: The Rules pilot's hunter ship, flown as an enemy (`entities/rules_hunter.py`). It sees only its target (you, or in training the neural hunter) and fires only at it. Requires 12 hits.
- **Neural hunter**: The same as the Rules hunter, but flown by the neural pilot, in magenta (`entities/neural_hunter.py`). Placed by a level file or the level editor.

### Level Progression

**Levels 1 to 24** are a designed arc. Each has its own file in `levels/` and introduces at most one new thing:

| Level | New |
|---|---|
| 1 | Static enemies |
| 2 | Patrol enemies |
| 3 | Aggressive enemies |
| 4 | The Jev beacon, which summons the hunter, your ally |
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
- **Boss levels** are small open arenas with a boss and a few escorts. The exit stays locked until every enemy on the level is dead, ammo is infinite, and no Jev beacon appears, so the hunter does not fly.

**From level 25** the game is endless:

- **Level 25 is a boss level**: the **Rules hunter**, the Rules pilot's hunter ship flown as an enemy, in a dense 26-cell maze with nothing else in it: no escorts, no anemones. It hunts only you, takes 12 hits, and leaves no crystal. The exit stays locked until every enemy is dead, ammo is infinite and no Jev beacon appears. The every-sixth-level boss rotation from level 30 is unchanged.
- The enemy count starts at 25 and rises by one every two levels, stopping at 36. The maze stays at 32 cells across.
- Every sixth level (30, 36, 42, ...) is a boss level: Split Bosses, then a Mother Boss, then both, building up to three bosses on a level.
- Enemy speed and damage grow 5% a level after level 4 and stop at 2.5 times. Enemy fire range stops at 600 pixels.

On every level, no enemy starts within 300 pixels of your ship.

- **Deterministic Generation**: Each level uses a fixed random seed (100 + level for the arc, the level number after it), ensuring the same level always generates the same maze layout, enemy positions, and enemy distributions across playthroughs

The level file format and the pacing rules are described in [levels/README.md](levels/README.md).

### Gates

A gate is a plank on a pin at the centre of a cell, one cell long each way from the pin, that swings under real physics. There are two kinds:

- **Free gates** swing on their pin and settle wherever they are pushed.
- **Motor gates** turn steadily, clockwise or anticlockwise, and push back against whatever stops them.

Pushing a gate costs nothing: the ship, enemies and the Jev hunter shove them aside by flying into them, and a gate that turns into you pushes you in return. Bullets nudge a gate rather than passing through it. A wall jams a gate that is turned against it; shooting the wall away frees a motor gate again. The hunter and sighted enemies see gates and steer round them.

The `obstacles` section of `config/settings.json` tunes them: `gateMass`, `gateLengthCells` (3: a plank covers its pin's cell and the one either side), `gateThicknessCells`, `gateElasticity`, `motorRate` (radians per second), `motorMaxForce` (how hard a motor pushes), `bulletImpulse`, `substeps` and `moverReachMargin`. Gates are placed in the level editor and stored in a level's `layout` (see [levels/README.md](levels/README.md)).

### Level editor

Run with `LEVEL_EDITOR=1` (for example `LEVEL_EDITOR=1 ./run.sh`) and an **EDITOR** item appears in the main menu. Pick a level, then lay it out cell by cell: walls, every enemy type, the start, the exit, the Jev beacon and gates. The level opens as it plays today; saving writes an exact `layout` into `levels/N.json` (git is the undo), and reverting takes it out again.

| Key | Action |
|---|---|
| Arrows | Move the cursor (hold to repeat) |
| Tab, Shift+Tab (or `[` `]`) | Next or previous palette item |
| Space | Place the selected item |
| Delete, Backspace | Remove what is under the cursor |
| R | Turn the gate under the cursor 45 degrees (refused if the plank would cross a wall) |
| F | Flip a motor gate's direction (clockwise or anticlockwise) |
| S | Save |
| X | Revert to the generated level (asks first) |
| Esc | Back to the level list (asks first if there are unsaved edits) |

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

### Stars

Reaching the exit gives one star for each of these goals you met, filled in from the left; a level you don't finish
gives none:

| Star | Earned when |
|---|---|
| No hits | No enemy bullet struck your ship and no enemy touched it (shield up, nothing counts). |
| Half the enemies | At least half the level's enemies were killed. |
| Every enemy | No enemy is left alive when you reach the exit. |
| Every crystal | No powerup crystal is left uncollected (a level where none dropped earns it). |
| Par | You finished within the level's par time. |

- Enemies that appear during the level (babies, eggs, a boss's children) count too. Kills and crystals by the Jev
  hunter count as yours. The Jev beacon is not a crystal.
- Par is worked out when the level starts: the shortest route from the start to the exit flown at half top speed,
  plus 1.2 s for each enemy on the level (6 s instead for a Mother or a Squiddler Boss, for her and what she spawns),
  plus 0.6 s for each crystal as it drops. A level whose exit opens on a timer gets at least the timer plus 2 s. The
  clock is play time, from your first move. The numbers are `game.parSpeedShare`, `parSecondsPerEnemy`,
  `parSecondsPerSpawningBoss`, `parSecondsPerCrystal` and `parTimerMargin` in `config/settings.json`.
- During play, the stars you'd get by reaching the exit now are shown above the level number, filled from the left. A
  chime plays when a goal is met or lost, and the rightmost star pulses in the last 5 seconds before par.
- The score is still kept and shown, but no longer decides the stars. Your best star count for each level is
  never lowered.

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
│   ├── generator.py       # Procedural maze generation, wall blocks and their destruction
│   ├── converter.py       # Turns the grid into the exposed faces of each block
│   └── wall_segment.py    # One face of a wall block
├── scoring/               # Scoring system
│   ├── system.py         # Score tracking
│   ├── calculator.py      # Score calculation
│   ├── stars.py          # The five stars, from kills, crystals and par
│   └── par.py            # Par time from the maze route, the enemies and the crystals
├── rendering/             # Rendering system
│   ├── renderer.py       # Centralized rendering
│   ├── ui_elements.py    # UI components, the live star chimes and the level-complete stars
│   ├── star_row.py       # The stars drawn during play
│   ├── stars.py          # The faceted star artwork
│   ├── dial.py           # HUD instrument dials
│   ├── fonts.py          # The game typeface (Chakra Petch)
│   ├── controls_menu.py  # Key and button mappings screen
│   ├── level_complete_menu.py # Level complete and level failed screens
│   ├── splash_scene.py   # Splash animation: a squid chasing the ship to the title
│   ├── wall_renderer.py  # Rock drawing for wall blocks and their faces
│   └── visual_effects.py  # Visual effects
├── input/                 # Input handling
│   └── input_handler.py  # Keyboard input mapping
├── sounds/                # Sound system
│   └── sound_manager.py  # Procedural sound generation (thrusters, shooting, explosions, portal sounds)
├── states/                # State management
│   ├── splash_screen.py  # Splash screen timing, fades and skipping
│   └── state_machine.py  # State machine infrastructure
├── game_handlers/         # Game system handlers
│   ├── enemy_roster.py  # Every enemy on the level
│   ├── spawn_manager.py  # Enemy spawning system
│   ├── enemy_updater.py  # Enemy update logic
│   ├── fire_rate_calculator.py # Fire rate and spread for each gun upgrade level
│   └── collision_handler.py # Collision detection and response
├── utils/                 # Utilities
│   ├── math_utils.py     # Math and collision utilities
│   └── spatial_grid.py   # Spatial partitioning
└── tests/                 # Unit tests
    └── README.md          # Test documentation
```

## Configuration

- All the tuning constants (screen dimensions, enemy behavior, maze presets, UI colors, etc.) live in `config/settings.json`. Edit this file to tweak the experience and keep everything organized by section.
- Each kind of enemy (its names, how it behaves in the maze and its own tuning) has one entry in `config/enemies.json`.
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

Collecting a Jev beacon summons one independent allied ship piloted by TypeSafe's Jev model.
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

### Choosing the hunter's pilot

`game.hunterPilot` in `config/settings.json` chooses the hunter's pilot: `"jev"` (default),
`"rules"` (the same criteria written as plain code in `hunter/rules_pilot.py`: no key, model or
training), or `"neural"` (a network that flies with the basic controls only; see
`docs/superpowers/specs/2026-10-12-neural-student-design.md`).

The neural pilot decides every `game.neuralDecisionFrames` frames and turns at `game.neuralTurnRate` times the
player's rate. Its weights are `assets/neural/hunter.npz` (the hunter coasts and shows as unavailable if the
file is missing or does not match the senses layout). To rebuild them: record the rules pilot with
`venv/bin/python -m experiments.teach`, train with `venv/bin/python -m tools.train_neural --data DIR --out PATH`
(needs `requirements-train.txt`), then run corrected rounds with `venv/bin/python -m experiments.dagger` and
check the gate with `venv/bin/python -m experiments.neural_lab gate --weights PATH`. The experiments are
written up in `docs/experiments/012` to `014`. The shipped policy did not meet the gate (held-out score 0.58 of
the rules pilot's, about 6 times its wall hits); it is the starting point for learning from environmental feedback.

To try a pilot without hunting for a Jev beacon, start the game with `ASTROVOID_HUNTER_HOTKEY=1` (for example
`ASTROVOID_HUNTER_HOTKEY=1 ./run.sh`): pressing **H** during a level collects the beacon if one is still lying there, otherwise
calls the hunter in beside your ship (replacing one that is flying). The key does nothing without the variable.

The **FUN** item on the main menu holds experimental levels. The first is **Pilot fight: Rules vs Vibes**: the rules
pilot's hunter (green) and the neural pilot's hunter (magenta) fight in a rocky maze (COMPLEX, built like level 13) scattered with a few random enemies while you watch, each shown the
other as its enemy. It uses whatever policy is in `assets/neural/hunter.npz`; each hunter takes `game.duelHealth` hits (5),
and a fight not settled within `game.duelTimeoutSeconds` (120) is a draw. Escape leaves it. It does not touch your
profile.

#### Unattended data collection

`AUTOPLAY=1 ./run.sh` skips the menus and runs levels with no one at the controls. The player
ship stays parked and cannot fail or finish a level; a hunter is summoned beside it and flies
each level on its own. A level ends when the time limit passes, every enemy is destroyed, or
the hunter dies, and the next level starts at once, wrapping from `autoplay.lastLevel` back to
`autoplay.firstLevel`. Nothing is written to your profile. Esc or closing the window quits.
Set `WINDOW_SIZE=1352x878` to run in a window of that size (the whole game world scales to it).
The `autoplay` section of `config/settings.json` sets `firstLevel`, `lastLevel` and
`timeLimitSeconds`. By default (`hidePlayer`) the hunter cannot see the parked player, so it
explores the maze and meets enemies instead of sitting beside the player.
A level also ends when no enemy has been killed for `noKillSeconds` (20; 0 turns it off), so
a hunter caught in a loop or wandering lost does not fill the logs.

Opt in through a level's JSON file; see [level configuration](levels/README.md).
The beacon is the hunter's arrowhead inside a turning amber ring. One lies in the maze, a third of the
way from your start to the exit, on every level from level 4 (`game.hunterFirstLevel` in `config/settings.json`), except boss levels; `game.hunterLevelInterval` spaces them out. A level file can place one anywhere or forbid one.
Fly into it and the hunter appears beside you. On those levels a destroyed enemy can also drop a beacon
in place of a crystal (`powerups.jevBeaconSpawnChance`), but only while no hunter is flying and no other
beacon is waiting, so there is never more than one hunter. It is indestructible: enemy shots and contact knock it about without
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

A powerup crystal in the hunter's sight is a goal of its own (`collect_powerup` in the
pilot's readings and instructions): with no enemy to fight it flies onto the nearest one
before going back to the player. Crystals upgrade the hunter's guns as they do yours:
the first makes bursts come faster, the second turns each shot into a three-way spread,
and those beyond the third make the shots bigger and faster. Each crystal adds the same
amount of firepower rather than multiplying it, and the upgrades all wear off together
`powerups.durationSeconds` after the last crystal. A crystal the hunter takes is one you
do not get and does not count towards your score; you have first claim on one you both
touch. The hunter leaves Jev beacons alone, and a newly summoned hunter starts with no
upgrades.
Inputs expire 750 ms after their sensor snapshot; expired inputs stop turning,
thrust and firing while momentum continues. Requests time out after one second.
There is no local autopilot fallback. Constants are in `hunter/model.py`.

For the local setup, run `./run-hunter.sh` to select level 4, the first with the hunter. Both this launcher
and `./run.sh` read `.astrovoid-local/typesafe-api-key` when no API key is already
set in the environment. That directory is ignored by Git; the local key file
should remain readable only by its owner. The launcher reads it as plain data.
