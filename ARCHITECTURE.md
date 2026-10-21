# ASTRO VOID Architecture Documentation

## Overview

ASTRO VOID is a skill-based space navigation game built with Pygame. The game combines classic Asteroids-style flight mechanics with procedurally-generated maze challenges. Players pilot a momentum-based spacecraft through increasingly complex mazes, balancing speed, fuel conservation, precision flying, and combat efficiency.

## System Design

The codebase follows SOLID principles and DRY (Don't Repeat Yourself) practices:

- **Single Responsibility Principle (SRP)**: Each class has a single, well-defined responsibility
- **Open/Closed Principle (OCP)**: An enemy built as a Creature is a catalogue entry naming a Body and Traits, so a new kind made of existing traits needs no new code
- **Dependency Inversion Principle (DIP)**: Abstractions (interfaces) are used where appropriate
- **DRY**: Common logic is extracted into reusable components

## Component Architecture

### Core Modules

#### `main.py`

Entry point of the application. Initializes Pygame and starts the game loop.

#### `game.py`

Main game coordinator class. Manages game state, level progression, and coordinates between different systems. While it still contains some state management logic, the architecture supports future extraction to a state machine.

#### `enemy_kinds.py`

The Enemy Kind catalogue, read from `config/enemies.json`: one entry per kind, in the order the editor palette and the
level counts use. `kind(key)` gives an `EnemyKind` (names, `anchored`, `replays_player`, `par_weight`, `spawn_radius`,
an enemy hunter's `pilot` and `hunter` numbers, and its own `tuning`); `kinds()`, `anchored()` and `hunters()` list
keys; `name()` and `plural()` give what the player reads. A missing or unknown field stops the game at startup.

#### `config.py`

Loads the centralized configuration from `config/settings.json`, and each Enemy Kind's own tuning from
`config/enemies.json` (see `enemy_kinds.py` below), and exposes both:

- A typed `config.SETTINGS` object with per-section dataclasses (`ScreenSettings`, `MazeSettings`, `PowerupSettings`, etc.)
- Legacy uppercase constants for backwards compatibility (e.g., `config.FPS`, `config.COLOR_BACKGROUND`)

The JSON file governs tunable sections such as:

- Screen dimensions and framerate
- Physics parameters (ship thrust, enemy speeds)
- Resource limits (fuel, ammo, shields)
- Difficulty scaling and maze presets
- Visual settings (colors, UI animation speeds)

### Entity System (`entities/`)

The entity system provides a foundation for all game objects:

#### Base Classes and Interfaces

- **`base.py`**: `GameEntity` - Abstract base class for all game entities

  - Common properties: position, velocity, radius, active state
  - Common methods: `update()`, `draw()`, `get_pos()`

- **`collidable.py`**: `Collidable` - Interface for collision detection

  - Methods: `check_wall_collision()`, `check_circle_collision()`

- **`drawable.py`**: `Drawable` - Interface for renderable objects
  - Method: `draw()`

#### Entity Implementations

- **`ship.py`**: `Ship` - Player-controlled spacecraft

  - Inherits from `GameEntity`, `Collidable`, `Drawable`
  - Manages fuel, ammo, rotation, thrust, and collision responses
  - Zero-G physics with low friction

- **`urchin.py`**, **`patrol_crab.py`**, **`jellyfish.py`**: the `urchin`, `crab` and `jelly` Bodies of the Urchin,
  Crab and Jelly Creatures (see `creatures/`): they animate and draw, and read only the creature's attributes
- **`squid.py`**: `Squid`, the `squid` Body of the Squiddler, Squidlet, Squiddler Boss and Mother: mantle, blinking
  eyes (a blink on the `flinch` event), trailing tentacles, the jet (on the `thrust` event) and the withdrawal on death
- **`egg.py`**: `EggBody`, the jelly sac with its embryos developing as the egg grows; it splits open when the egg
  hatches and bursts into blobs when it is shot (it hears `died`)
- **`anemone.py`**: `AnemoneBody`, the rooted anemone with its reach streaks, tentacles leaning toward a ship it is
  pulling and folding shut while it flinches; `pull_acceleration` and `apply_pull` are the pull maths `pullsShip` uses
- **`flocker.py`**: `FlockerBody`, the swallow; **`flocker_neighbor_cache.py`** is the spatial hash `flocks` uses
- **`flighthouse.py`**: `FlighthouseBody`, the lighthouse seen from above, its beam the size of what it can see,
  turning red while it sees the player and flashing when it launches

- **`explosion.py`**: `Blast`, `Explosions`, `Fireball` - reusable explosions (Belemnites now, bombs later)
  - A `Blast` is a reach, damage, push, wall hits and whom its kills count for; `fuse` delays it so chains ripple
  - `Explosions` (held by `CollisionHandler`) lights blasts and returns those going off; `CollisionHandler.handle_blast` applies one to the player, the hunter, the enemies (through the same path a shot takes, so each kind dies its own way) and the walls
  - A Creature with the `explodes` trait lights its blast when it is killed (through `Encounter.explode`); any other
    enemy with a `blast(source)` method does when `CollisionHandler.record_kill` counts it. So explosions chain
- **`belemnite.py`**: `BelemniteBody` - the `belemnite` Body of the Belemnite Creature, a gunless squid with a
  Jelly's chase brain that explodes when it dies

- **`projectile.py`**: `Projectile` - Weapons fired by the ship
  - Inherits from `GameEntity`, `Collidable`, `Drawable`
  - Manages lifetime and collision detection

### Maze System (`maze/`)

- **`generator.py`**: `Maze` - Procedural maze generation
  - Uses recursive backtracking algorithm
  - Generates wider corridors for better maneuverability
  - Provides spawn positions for enemies
  - Converts grid to wall segments for collision detection

### Creatures (`creatures/`)

Every enemy but the enemy hunters is a **Creature**: a Body (how it looks) and a list of Traits (what it does), named in
its `config/enemies.json` entry and run in the entry's order (see
`docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md`). The enemy hunters, which fly with a pilot, keep
their own classes.

- **`creature.py`**: `Creature`, a `GameEntity` holding kind, position, velocity, hit points, allegiance, its
  `Controls` this frame (`turn`, `thrust`, `fire`, `heading`, `aim`), its Body and Traits, and the state its traits
  keep. It does not act by itself. `deepcopy` (the death portrait) leaves out any Encounter.
- **`trait.py`**: `Trait`, whose hooks all do nothing by default: `on_spawn`, `on_frame`, `on_shot`, `on_death`,
  `on_event`, and `on_crowd` for a `CROWD` trait (once a frame per crowd: a kind, or a crowd the trait names, as
  Jellies and Belemnites share `chasers`). A trait is stateless; `REQUIRES` names traits it needs, and
  `from_params` builds it from its catalogue parameters.
- **`traits/`**: `brains.py` (`still`, `patrol`, `chase`, `replaysPlayer`), `propulsion.py` (`coasts`, `drift`,
  `thrusters`, which flies like a ship through `physics/thrust.py`), `combat.py` (`takesHits`, `shovedByShots`,
  `ramsShip`, `dropsPickup`, `bouncesOffWalls`, `gun`, `explodes`, `flinchesWhenHit`, which times a flinch its Body
  draws: a squid blinks, an anemone clamps shut), `crowd.py` (`keepsApart`, which also keeps a crowd out of the walls),
  `spawning.py` (`splitsOnDeath`, `laysEggs`), `growth.py` (`grows`, `hatches`: hatching is a plain death, not a
  kill), `rooted.py` (`anchored`, `pullsShip`, a crowd trait whose pulls together never exceed one at full strength,
  `flingsShip`), `flock.py` (`flocks`, a crowd brain that decides the whole flock's next frame, `tweets`) and
  `lighthouse.py` (`scans`, which watches the player's ship only, and `launchesFlock`)
- **`registry.py`**: `TRAITS` and `BODIES` by catalogue name; `validate(catalogue)` rejects an unknown body or trait,
  bad parameters or a missing requirement when the game starts
- **`__init__.py`**: `build(kind, pos, level, recorder)`; `SpawnManager.make_enemy` calls it for every kind but the
  enemy hunters
- **`encounter.py`**: `Encounter(roster, world)`. `step(dt)` runs each live creature's traits in roster order and then
  animates its Body, then each kind's crowd traits; `shoot(projectile)` offers a friendly shot to each live creature in
  roster order and stops at the first it reaches, handing a shot no creature took to `CollisionHandler.shoot_into`
  (the enemy hunters). `ready()` runs every newcomer's spawn hooks without a frame passing; the game calls it at level
  start, so creatures show their state (an anemone its reach) before the player moves.
  Traits reach the world through it (`ship`, `hunter`, `maze`, `scoring`, `target_for`, `kill`, `drop_pickup`,
  `add_shot`, `explode`, and `spawn`, which puts a new enemy of any kind on the roster). `Game` is its own world; `DuelEnemies` gives it a stand-in whose ship is the first hunter.

### Enemy Roster (`game_handlers/enemy_roster.py`)

- **`EnemyRoster`**: every enemy on the level, of every kind, in the order they were added
  - `add` (also `append`/`extend`, so spawning enemies can add to it as to a list), `clear`
  - `of_kind(*kinds)`: a new list of those kinds; `all()`, `alive()`, `positions()`, `counts()` (alive, by kind)
  - `update_dying(dt)`; `draw(screen)` draws each kind on its catalogue layer, then the death animations
- `Game`, `DuelEnemies` and `SpawnManager` hold one; `CollisionHandler.shoot_into` hits a shot against it

### Hunter System (`hunter/`)

The hunter is the allied ship that flies itself (see `GLOSSARY.md` for its terms).

- **`flight.py`**: `HunterFlight` - one hunter in play with its pilot, from its summons until it is closed
  - Built from the hunter's ship, a pilot (`WorkerPilot` for Jev or the rules pilot, `NeuralPilot` for the neural one) and its surroundings
  - `fly(dt)` flies one frame and returns the shots fired; `pause()` holds it still; `close()` ends it
  - Picks the observer the pilot reads, consults fire control, drops a burst no live decision backs, and settles the ship against the walls
  - The ship's settings are the flight's, fixed for its life
  - `on_observed(fn)` lets the lab record what the pilot is shown
- **`surroundings.py`**: what the hunter may perceive at the moment it looks (maze, enemies, threats, pickups, the visible friend)
  - `GameSurroundings` answers for a level; `DuelSurroundings` (in `duel.py`) for each side of a duel
- **`duel.py`**: `DuelArena` - two hunter flights fighting each other

`Game`, `DuelArena` and the experiments harness each hold a `HunterFlight` rather than wiring the ship, pilot and observers themselves.

### Scoring System (`scoring/`)

- **`system.py`**: `ScoringSystem` - Tracks game metrics

  - Records collisions, shots, fuel usage, enemy destructions
  - Delegates score calculation to `ScoreCalculator`
  - Manages level and total score tracking

- **`calculator.py`**: `ScoreCalculator` - Centralized score calculation
  - Eliminates duplication between real-time and final score calculations
  - Calculates penalties and bonuses
  - Returns score breakdowns

- **`stars.py`**: `StarTally`, `earned`, `describe` - the five stars from what the player did
  - Finish, half the enemies, every enemy, every crystal, par
  - Kills and crystals by the Jev hunter count as the player's

- **`par.py`**: `route_cells`, `par_seconds` - par time from the maze route, the enemies at the start and the crystals

### Rendering System (`rendering/`)

- **`renderer.py`**: `Renderer` - Centralized rendering operations

  - Provides common drawing operations
  - Reduces code duplication

- **`ui_elements.py`**: `UIElementRenderer` - UI component rendering
  - HUD dials and the energy gauge
  - `StarIndicator` (chimes as the live stars change) and `AnimatedStarRating` (the level-complete stars)

- **`star_row.py`**: `draw_star_row` - the five stars you'd get now, drawn above the level number during play
- **`stars.py`**: `draw_star`, `draw_glow`, `StarBurst` - the faceted star artwork shared by every star

- **`fonts.py`**: `get_font` - the bundled typeface (Chakra Petch, in `assets/fonts`); all text goes through it
- **`controls_menu.py`**: `ControlsMenu` - key and button mappings, reached from the main menu
- **`dial.py`**: Neon HUD instrument dials (time, power, ammo)
  - Segmented arc that fills clockwise, with a dim unlit track
  - Static layers drawn once per size and colour, then cached

### State Management (`states/`)

- **`state_machine.py`**: State machine infrastructure
  - `GameState` - Abstract base class for game states
  - `StateMachine` - Manages state transitions
  - Provides interface: `enter()`, `exit()`, `update()`, `draw()`, `handle_event()`

Note: Individual state implementations (menu, playing, level complete, etc.) are planned but not yet fully implemented. The current `game.py` still handles state management directly, but the architecture supports future extraction.

### Utilities (`utils/`)

- **`math_utils.py`**: Mathematical operations and collision detection
  - Distance calculations
  - Angle conversions
  - Point rotation
  - Collision detection (circle-circle, circle-line, circle-rectangle)
  - Vector operations (reflection, normalization)

## Data Flow

### Game Loop

1. **Event Handling**: `game.py` processes pygame events
2. **State Update**: Current state's `update()` method is called
3. **Entity Updates**: All active entities update their positions and state
4. **Collision Detection**: Entities check collisions with walls and each other
5. **Scoring Updates**: Scoring system tracks metrics in real-time
6. **Rendering**: Current state's `draw()` method renders all entities

### Level Progression

1. **Level Start**: `start_level()` generates maze, creates ship and enemies
   - What is on a level comes from `level_config.py`: the level's file in `levels/` if it has one (levels 1-24 all do), otherwise the formulas in `level_rules.py` (level 25 onward). See `levels/README.md`.
   - Enemies are placed at least `enemies.startClearance` pixels from the ship.
   - A level with a Split Boss or Mother Boss is a boss level: the exit stays locked until every enemy is dead (on other levels, only eggs lock it), ammo is infinite, and no Jev beacon appears, so no hunter flies.
2. **Gameplay**: Player navigates maze, avoids/fights enemies
3. **Level Complete**: Ship reaches exit or score reaches zero
4. **Score Calculation**: Final score calculated with penalties and bonuses
5. **State Transition**: Move to level complete screen or game over

### Scoring Flow

1. **Real-time Tracking**: `ScoringSystem` records events (collisions, shots, etc.)
2. **Potential Score**: `calculate_current_potential_score()` provides real-time feedback
3. **Final Calculation**: `calculate_level_score()` computes final score on completion
4. **Stars**: `Game.star_tally()` counts kills, enemies alive, crystals and play time against par (fixed at level
   start); the tally is frozen when the ship enters the exit and `scoring.stars.earned` turns it into the five stars

## Design Patterns

### Composition (Creatures)

- **Enemy Behaviours**: a `Creature` is composed from a Body and Traits named in its catalogue entry; Traits talk to
  each other and to the Body through `Controls` and events (`fired`, `hit`, `hit_wall`, `rammed`, `flinch`, `thrust`,
  `sighted`, `launched`; the Body alone also hears `died`)
- **Benefits**: behaviour is shared by naming a trait in another kind's entry, without a new class

### Template Method Pattern

- **GameEntity**: Base class defines structure, subclasses implement specifics
- **GameState**: Base state class defines interface, concrete states implement behavior

### Factory Pattern

- **`SpawnManager`** (`game_handlers/spawn_manager.py`): Creates every enemy for a level from its enemy counts and spawn positions

## Extension Points

### Adding New Enemy Types

1. Add an entry to `config/enemies.json`: its names, whether it is anchored or replays the player, its par weight,
   the room it needs, the layer it is drawn on and its own `tuning`. The editor palette, level files, exit policies,
   par, drawing and the names on screen all follow from the entry.
2. If it can be made of traits that exist, give the entry a `body` (one of `creatures/registry.BODIES`), an
   `allegiance` and its `traits` with their parameters, in the order they should run. That is all: `make_enemy` builds
   it, the Encounter runs it and offers it shots, and the roster keeps it with every other enemy. A new behaviour is a
   new `Trait` subclass in `creatures/traits/`, added to `TRAITS`; a new look is a new Body added to `BODIES`. Name
   a trait for what it does, not for one kind, so other kinds can take it too.
3. For a generated level, add a count for it to `EnemyCounts` (`level_rules.py`)

### Adding New Game States

1. Create new state class inheriting from `GameState`
2. Implement required methods: `enter()`, `exit()`, `update()`, `draw()`, `handle_event()`
3. Add state transition logic in appropriate places

### Modifying Scoring

1. Update constants in `config.py` for penalty/bonus rates
2. Modify `ScoreCalculator.calculate_score()` for calculation changes
3. `ScoringSystem` handles tracking, `ScoreCalculator` handles calculation (SRP)

## Dependencies

- **Pygame**: Graphics, input handling, game loop
- **Python Standard Library**: Math, typing, random, time

## File Structure

```
/
├── main.py                 # Entry point
├── game.py                 # Main game coordinator
├── config.py               # Configuration constants
├── requirements.txt         # Python dependencies
├── run.sh                   # Run script
├── entities/                # Game entities
│   ├── base.py
│   ├── collidable.py
│   ├── drawable.py
│   ├── ship.py
│   ├── urchin.py           # the Bodies of the Urchin, Crab and Jelly; squid.py the squids'
│   ├── patrol_crab.py
│   ├── jellyfish.py
│   ├── egg.py              # ... and of the Egg, Anemone, Flocker and Flighthouse
│   ├── anemone.py
│   ├── flocker.py
│   ├── flighthouse.py
│   └── projectile.py
├── creatures/               # Creature, Trait, Encounter, and the traits (see Creatures above)
├── maze/                    # Maze generation
│   └── generator.py
├── scoring/                 # Scoring system
│   ├── system.py
│   ├── calculator.py
│   ├── stars.py
│   └── par.py
├── rendering/               # Rendering system
│   ├── renderer.py
│   ├── ui_elements.py
│   ├── star_row.py
│   ├── stars.py
│   ├── dial.py
│   ├── fonts.py
│   └── controls_menu.py
├── states/                  # State management
│   └── state_machine.py
└── utils/                   # Utilities
    └── math_utils.py
```

## Future Improvements

1. **Complete State Machine**: Extract all state management from `game.py` to individual state classes
2. **Physics Engine**: Extract common physics calculations to dedicated module
3. **Collision System**: Centralize collision detection and response
4. **Save System**: Add save/load functionality for game progress
5. **Sound System**: Add sound effects and music
6. **Particle Effects**: Add visual effects for explosions, thrust, etc.
