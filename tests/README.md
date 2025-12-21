# Unit Tests for ASTER VOID

This directory contains unit tests for key functions in the ASTER VOID game.

## Running Tests

To run all tests:

```bash
pytest tests/
```

To run a specific test file:

```bash
pytest tests/test_utils.py
```

To run with verbose output:

```bash
pytest tests/ -v
```

To run with coverage:

```bash
pytest tests/ --cov=. --cov-report=html
```

## Test Coverage

### `test_utils.py`

Tests for utility functions:

- Distance calculations
- Angle conversions and normalization
- Point rotation
- Collision detection (circle-circle, circle-line, circle-rectangle, line-line)
- Vector operations (reflection, wall normals)

### `test_scoring.py`

Tests for scoring system:

- Score calculation with various penalties
- Enemy destruction bonuses
- Score percentage calculations
- Edge cases (zero score, exceeding maximum)

### `test_ship.py`

Tests for ship physics:

- Rotation (left/right, wrapping)
- Thrust mechanics (direction, fuel consumption, speed limits)
- Update behavior (friction, particle creation)
- Collision detection
- Projectile firing

### `test_enemy_strategies.py`

Tests for enemy behaviors:

- Static enemy (no movement)
- Patrol enemy (movement and wall reversal)
- Aggressive enemy (chasing player, alert state)

### `test_projectile.py`

Tests for projectile behavior:

- Movement and direction
- Lifetime management
- Collision detection (walls, enemies)
- Deactivation conditions

### `test_ccd.py`

Tests for continuous collision detection (swept collision):

- Swept circle-line collision detection
- Movement through walls
- Edge cases and boundary conditions
- Collision time calculations

## Adding New Tests

When adding new functionality, create corresponding test cases:

1. Create a test file in `tests/` directory
2. Follow naming convention: `test_*.py`
3. Use descriptive test class and method names
4. Test both normal cases and edge cases
5. Use assertions to verify expected behavior

Example:

```python
def test_new_functionality():
    """Test description."""
    # Arrange
    obj = SomeClass()

    # Act
    result = obj.some_method()

    # Assert
    assert result == expected_value
```

