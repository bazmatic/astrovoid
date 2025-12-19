# Asterdroids API Documentation

## Public Interfaces

### Entity System

#### `entities.base.GameEntity`

Base class for all game entities.

**Attributes:**
- `x`, `y` (float): Position coordinates
- `vx`, `vy` (float): Velocity components
- `radius` (float): Collision radius
- `active` (bool): Whether entity is active

**Methods:**
- `get_pos() -> Tuple[float, float]`: Get current position
- `get_radius() -> float`: Get collision radius
- `update(dt: float) -> None`: Update entity (abstract)
- `draw(screen: pygame.Surface) -> None`: Draw entity (abstract)

#### `entities.ship.Ship`

Player-controlled spacecraft.

**Methods:**
- `rotate_left() -> None`: Rotate counter-clockwise
- `rotate_right() -> None`: Rotate clockwise
- `apply_thrust() -> bool`: Apply thrust, returns True if fuel consumed
- `fire() -> Optional[Projectile]`: Fire projectile, returns None if no ammo
- `check_wall_collision(walls: List) -> bool`: Check wall collision
- `check_circle_collision(pos: Tuple, radius: float) -> bool`: Check entity collision
- `draw_ui(screen: pygame.Surface, font: pygame.font.Font) -> None`: Draw fuel/ammo UI

**Attributes:**
- `fuel` (int): Current fuel remaining
- `ammo` (int): Current ammunition remaining
- `angle` (float): Facing angle in degrees

#### `entities.enemy.Enemy`

Enemy entity with configurable behavior.

**Methods:**
- `update(dt: float, player_pos: Optional[Tuple], walls: Optional[List]) -> None`: Update enemy
- `destroy() -> None`: Destroy the enemy
- `check_wall_collision(walls: List) -> bool`: Check wall collision
- `check_circle_collision(pos: Tuple, radius: float) -> bool`: Check entity collision

**Attributes:**
- `type` (str): Enemy type ("static", "patrol", "aggressive")
- `strategy` (EnemyStrategy): Behavior strategy
- `speed` (float): Movement speed
- `angle` (float): Facing angle

#### `entities.projectile.Projectile`

Projectile fired from ship.

**Methods:**
- `check_wall_collision(walls: List) -> bool`: Check wall collision
- `check_enemy_collision(pos: Tuple, radius: float) -> bool`: Check enemy collision

**Attributes:**
- `lifetime` (int): Remaining lifetime in frames
- `angle` (float): Firing angle

### Maze System

#### `maze.Maze`

Procedurally generated maze.

**Methods:**
- `get_valid_spawn_positions(count: int) -> List[Tuple[float, float]]`: Get spawn positions
- `check_exit_collision(pos: Tuple, radius: float) -> bool`: Check if at exit
- `draw(screen: pygame.Surface) -> None`: Draw maze

**Attributes:**
- `start_pos` (Tuple[float, float]): Starting position
- `exit_pos` (Tuple[float, float]): Exit position
- `walls` (List): List of wall segments

### Scoring System

#### `scoring.ScoringSystem`

Manages scoring and metrics tracking.

**Methods:**
- `start_level(current_time: float) -> None`: Start tracking new level
- `record_wall_collision() -> None`: Record wall collision
- `record_enemy_collision() -> None`: Record enemy collision
- `record_shot() -> None`: Record shot fired
- `record_enemy_destroyed() -> None`: Record enemy destroyed
- `calculate_level_score(completion_time: float, remaining_fuel: int, remaining_ammo: int) -> Dict`: Calculate final score
- `calculate_current_potential_score(current_time: float, remaining_fuel: int, remaining_ammo: int) -> Dict`: Calculate real-time score
- `get_total_score() -> int`: Get total accumulated score
- `get_level_score() -> int`: Get current level score

**Return Format:**
```python
{
    "time_penalty": float,
    "collision_penalty": float,
    "enemy_destruction_bonus": float,
    "ammo_penalty": float,
    "fuel_penalty": float,
    "final_score": float,  # or "potential_score" for real-time
    "total_score": int,    # only in final score
    "score_percentage": float,  # only in potential score
    "max_score": float     # only in potential score
}
```

#### `scoring.calculator.ScoreCalculator`

Static methods for score calculation.

**Methods:**
- `calculate_score(elapsed_time: float, enemy_collisions: int, enemies_destroyed: int, shots_fired: int, fuel_used: int) -> Dict`: Calculate score
- `calculate_score_percentage(score: float, max_score: float) -> float`: Calculate percentage

### Rendering System

#### `rendering.Renderer`

Centralized rendering operations.

**Methods:**
- `clear() -> None`: Clear screen
- `draw_text(text: str, position: Tuple, font: pygame.font.Font, color: Tuple, center: bool) -> None`: Draw text
- `draw_star_rating(score_percentage: float, x: int, y: int) -> None`: Draw 5-star rating
- `draw_progress_bar(x: int, y: int, width: int, height: int, value: float, max_value: float, fill_color: Tuple, empty_color: Tuple, border_color: Optional[Tuple]) -> None`: Draw progress bar

#### `rendering.ui_elements.UIElementRenderer`

Static methods for UI element rendering.

**Methods:**
- `draw_star_rating(screen: pygame.Surface, score_percentage: float, x: int, y: int, ...) -> None`: Draw star rating

### Utilities

#### `utils` Module

Mathematical and collision utilities.

**Functions:**
- `distance(pos1: Tuple, pos2: Tuple) -> float`: Calculate distance
- `angle_to_radians(angle: float) -> float`: Convert degrees to radians
- `normalize_angle(angle: float) -> float`: Normalize to 0-360 range
- `rotate_point(point: Tuple, center: Tuple, angle: float) -> Tuple`: Rotate point
- `circle_circle_collision(pos1: Tuple, radius1: float, pos2: Tuple, radius2: float) -> bool`: Check circle collision
- `circle_line_collision(circle_pos: Tuple, radius: float, line_start: Tuple, line_end: Tuple) -> bool`: Check circle-line collision
- `get_angle_to_point(from_pos: Tuple, to_pos: Tuple) -> float`: Get angle to point
- `get_wall_normal(circle_pos: Tuple, line_start: Tuple, line_end: Tuple) -> Tuple`: Get wall normal vector
- `reflect_velocity(velocity: Tuple, normal: Tuple, bounce_factor: float) -> Tuple`: Reflect velocity vector

### Configuration

#### `config` Module

All game constants and configuration values.

**Key Constants:**
- `SCREEN_WIDTH`, `SCREEN_HEIGHT`: Screen dimensions
- `SHIP_SIZE`, `SHIP_ROTATION_SPEED`, `SHIP_THRUST_FORCE`: Ship parameters
- `INITIAL_FUEL`, `INITIAL_AMMO`: Resource limits
- `MAX_LEVEL_SCORE`: Maximum score per level (100)
- `TIME_PENALTY_RATE`, `COLLISION_PENALTY`, etc.: Scoring parameters
- `STATE_MENU`, `STATE_PLAYING`, etc.: Game state constants
- Color constants: `COLOR_BACKGROUND`, `COLOR_SHIP`, etc.

## Usage Examples

### Creating and Updating Entities

```python
from entities.ship import Ship
from entities.enemy import Enemy

# Create ship
ship = Ship((100, 100))

# Update ship
ship.update(dt)

# Rotate and thrust
ship.rotate_left()
if keys[pygame.K_UP]:
    ship.apply_thrust()

# Fire projectile
projectile = ship.fire()
if projectile:
    projectiles.append(projectile)
```

### Scoring

```python
from scoring import ScoringSystem

scoring = ScoringSystem()
scoring.start_level(time.time())

# Record events
scoring.record_enemy_collision()
scoring.record_shot()

# Get real-time score
potential = scoring.calculate_current_potential_score(
    time.time(), ship.fuel, ship.ammo
)
print(f"Potential score: {potential['potential_score']}")

# Calculate final score
final = scoring.calculate_level_score(
    completion_time, ship.fuel, ship.ammo
)
print(f"Final score: {final['final_score']}")
```

### Rendering

```python
from rendering import Renderer

renderer = Renderer(screen)
renderer.clear()
renderer.draw_text("Score", (100, 100), font)
renderer.draw_star_rating(0.85, 200, 100)  # 85% score
```

### Enemy Creation

```python
from entities.enemy import create_enemies

# Create enemies for level
spawn_positions = maze.get_valid_spawn_positions(10)
enemies = create_enemies(level=1, spawn_positions=spawn_positions)

# Update enemies
for enemy in enemies:
    enemy.update(dt, player_pos=ship.get_pos(), walls=maze.walls)
```

