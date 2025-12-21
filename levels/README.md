# Level Configuration Files

This directory contains per-level configuration files that can override default game settings.

## File Format

Each level can have its own configuration file named `{level}.json` (e.g., `1.json`, `2.json`, etc.).

## Configuration Structure

```json
{
  "seed": 42,
  "maze": {
    "complexity": "normal",
    "grid_size": 25
  },
  "enemies": {
    "static": 5,
    "patrol": 3,
    "aggressive": 2,
    "replay": 1,
    "split_boss": 0
  }
}
```

### Fields

- **seed** (optional): Random seed for level generation. If not specified, defaults to the level number.
- **maze** (optional): Object containing maze configuration overrides.
  - **complexity** (optional): Maze complexity level. Valid values: `"empty"`, `"simple"`, `"normal"`, `"complex"`, `"extreme"`. If not specified, complexity is calculated from level number:
    - Level 1: `empty` (perimeter only, no obstacles)
    - Levels 2-3: `simple`
    - Levels 4-7: `normal`
    - Levels 8-11: `complex`
    - Levels 12+: `extreme`
  - **grid_size** (optional): Grid size (width/height in cells). The maze is always square. If not specified, calculated as `BASE_MAZE_SIZE + (level - 1) * MAZE_SIZE_INCREMENT` (default: 15 + (level-1) \* 2). Valid range: 5-100. Larger values create more, smaller blocks.
- **enemies** (optional): Object containing enemy count overrides. If not specified, uses default calculations from `level_rules.py`.
  - **static** (optional): Number of static enemies. Defaults to calculated value.
  - **patrol** (optional): Number of patrol enemies. Defaults to calculated value.
  - **aggressive** (optional): Number of aggressive enemies. Defaults to calculated value.
  - **replay** (optional): Number of replay enemy ships. Defaults to calculated value.
  - **split_boss** (optional): Number of SplitBoss enemies. Defaults to calculated value (0 for levels < 11, 1 for level 11+).

## Partial Overrides

You can specify only the fields you want to override. Unspecified fields will use their default values.

### Example: Only override seed

```json
{
  "seed": 999
}
```

### Example: Only override some enemy counts

```json
{
  "enemies": {
    "static": 10,
    "replay": 2
  }
}
```

### Example: Override maze complexity

```json
{
  "maze": {
    "complexity": "extreme"
  }
}
```

### Example: Override maze grid size

```json
{
  "maze": {
    "grid_size": 50
  }
}
```

### Example: Override both maze complexity and grid size

```json
{
  "maze": {
    "complexity": "extreme",
    "grid_size": 50
  }
}
```

## Default Behavior

If a level has no configuration file, the game will:

- Use the level number as the random seed
- Calculate enemy counts using the formulas in `level_rules.py`
