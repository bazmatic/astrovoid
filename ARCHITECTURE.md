# ASTER VOID Architecture Documentation

## Overview

ASTER VOID is a skill-based space navigation game built with Pygame. The game combines classic Asteroids-style flight mechanics with procedurally-generated maze challenges. Players pilot a momentum-based spacecraft through increasingly complex mazes, balancing speed, fuel conservation, precision flying, and combat efficiency.

## System Design

The codebase follows SOLID principles and DRY (Don't Repeat Yourself) practices:

- **Single Responsibility Principle (SRP)**: Each class has a single, well-defined responsibility
- **Open/Closed Principle (OCP)**: Enemy behaviors use the Strategy pattern, allowing new enemy types without modifying existing code
- **Dependency Inversion Principle (DIP)**: Abstractions (interfaces) are used where appropriate
- **DRY**: Common logic is extracted into reusable components

## Component Architecture

### Core Modules

#### `main.py`

Entry point of the application. Initializes Pygame and starts the game loop.

#### `game.py`

Main game coordinator class. Manages game state, level progression, and coordinates between different systems. While it still contains some state management logic, the architecture supports future extraction to a state machine.

#### `config.py`

Centralized configuration file containing all game constants, including:

- Screen dimensions
- Physics parameters (ship speed, rotation, thrust)
- Resource limits (fuel, ammo)
- Scoring weights and penalties
- Difficulty scaling
- Visual settings (colors, sizes)

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

- **`enemy.py`**: `Enemy` - Enemy entities

  - Uses Strategy pattern for behaviors (see `enemy_strategies.py`)
  - Supports static, patrol, and aggressive enemy types
  - Follows OCP - new enemy types can be added without modifying `Enemy`

- **`enemy_strategies.py`**: Enemy behavior strategies

  - `StaticEnemyStrategy`: Enemies that don't move
  - `PatrolEnemyStrategy`: Enemies that patrol in straight lines
  - `AggressiveEnemyStrategy`: Enemies that chase the player
  - Demonstrates Strategy pattern and OCP

- **`projectile.py`**: `Projectile` - Weapons fired by the ship
  - Inherits from `GameEntity`, `Collidable`, `Drawable`
  - Manages lifetime and collision detection

### Maze System (`maze/`)

- **`generator.py`**: `Maze` - Procedural maze generation
  - Uses recursive backtracking algorithm
  - Generates wider corridors for better maneuverability
  - Provides spawn positions for enemies
  - Converts grid to wall segments for collision detection

### Scoring System (`scoring/`)

- **`system.py`**: `ScoringSystem` - Tracks game metrics

  - Records collisions, shots, fuel usage, enemy destructions
  - Delegates score calculation to `ScoreCalculator`
  - Manages level and total score tracking

- **`calculator.py`**: `ScoreCalculator` - Centralized score calculation
  - Eliminates duplication between real-time and final score calculations
  - Calculates penalties and bonuses
  - Returns score breakdowns

### Rendering System (`rendering/`)

- **`renderer.py`**: `Renderer` - Centralized rendering operations

  - Provides common drawing operations
  - Reduces code duplication

- **`ui_elements.py`**: `UIElementRenderer` - UI component rendering
  - Star rating display
  - Progress bars
  - Reusable UI components

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
2. **Gameplay**: Player navigates maze, avoids/fights enemies
3. **Level Complete**: Ship reaches exit or score reaches zero
4. **Score Calculation**: Final score calculated with penalties and bonuses
5. **State Transition**: Move to level complete screen or game over

### Scoring Flow

1. **Real-time Tracking**: `ScoringSystem` records events (collisions, shots, etc.)
2. **Potential Score**: `calculate_current_potential_score()` provides real-time feedback
3. **Final Calculation**: `calculate_level_score()` computes final score on completion
4. **Score Display**: Star rating shows score percentage (0-100%)

## Design Patterns

### Strategy Pattern

- **Enemy Behaviors**: `Enemy` uses composition with `EnemyStrategy` implementations
- **Benefits**: New enemy types can be added without modifying `Enemy` class (OCP)

### Template Method Pattern

- **GameEntity**: Base class defines structure, subclasses implement specifics
- **GameState**: Base state class defines interface, concrete states implement behavior

### Factory Pattern

- **`create_enemies()`**: Factory function creates enemies based on level and spawn positions

## Extension Points

### Adding New Enemy Types

1. Create new strategy class inheriting from `EnemyStrategy`
2. Implement `update()` method with desired behavior
3. Add enemy type to `create_enemies()` factory function
4. No modification to `Enemy` class needed (OCP)

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
asterdroids/
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
│   ├── enemy.py
│   ├── enemy_strategies.py
│   └── projectile.py
├── maze/                    # Maze generation
│   └── generator.py
├── scoring/                 # Scoring system
│   ├── system.py
│   └── calculator.py
├── rendering/               # Rendering system
│   ├── renderer.py
│   └── ui_elements.py
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

