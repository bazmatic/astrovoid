"""Level-based enemy rules and scaling.

This module centralizes all rules for enemy counts and strength scaling based on level.
It provides a single source of truth for level-based difficulty adjustments.

Architecture:
    This module follows the Configuration Object pattern, providing functions that
    calculate enemy properties based on level. This makes it easy to:
    - Tune game balance
    - Adjust difficulty curves
    - Modify enemy scaling formulas
    - Test different configurations
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import math
import config
from maze.config import MazeComplexity, MazeComplexityPresets


@dataclass
class EnemyCounts:
    """Enemy count configuration for a level.
    
    Attributes:
        total: Total number of regular enemies
        static: Number of static enemies
        patrol: Number of patrol enemies
        aggressive: Number of aggressive enemies
        replay: Number of replay enemy ships
        flocker: Number of flocker enemy ships
        egg: Number of egg enemies
    """
    total: int
    static: int
    patrol: int
    aggressive: int
    replay: int
    flocker: int
    egg: int


@dataclass
class EnemyStrength:
    """Enemy strength configuration for a level.
    
    Attributes:
        patrol_speed: Movement speed for patrol enemies
        aggressive_speed: Movement speed for aggressive enemies
        damage: Damage dealt by enemies
        fire_interval_min: Minimum frames between enemy shots
        fire_interval_max: Maximum frames between enemy shots
        fire_range: Maximum distance to player for firing (pixels)
    """
    patrol_speed: float
    aggressive_speed: float
    damage: int
    fire_interval_min: int
    fire_interval_max: int
    fire_range: float


def get_enemy_count(level: int) -> int:
    """Get total enemy count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Total number of enemies for the level.
    """
    if level <= config.TUTORIAL_LEVELS:
        return 2
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    return config.BASE_ENEMY_COUNT + (effective_level - 1) * config.ENEMY_COUNT_INCREMENT


def get_enemy_type_distribution(level: int, total_count: int) -> Dict[str, int]:
    """Get distribution of enemy types for a level.
    
    Args:
        level: Current level number (1-based).
        total_count: Total number of enemies.
        
    Returns:
        Dictionary with keys 'static', 'patrol', 'aggressive' and their counts.
    """
    # Static enemies: at least 1, up to half of total
    static_count = max(1, total_count // 2)
    dynamic_count = total_count - static_count
    
    # Dynamic enemies split between patrol and aggressive
    patrol_count = dynamic_count // 2
    aggressive_count = dynamic_count - patrol_count
    
    return {
        'static': static_count,
        'patrol': patrol_count,
        'aggressive': aggressive_count
    }


def get_replay_enemy_count(level: int) -> int:
    """Get number of replay enemy ships for a level.
    
    Uses continuous scaling formula: base + scale_factor * sqrt(effective_level)
    This provides slow, diminishing returns scaling that continues indefinitely.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of replay enemies (0 for tutorial levels, then continuous scaling).
    """
    if level <= config.TUTORIAL_LEVELS:
        return 0
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    # Continuous scaling with square root for diminishing returns
    count = config.REPLAY_ENEMY_BASE_COUNT + config.REPLAY_ENEMY_SCALE_FACTOR * math.sqrt(effective_level)
    return round(count)


def get_split_boss_count(level: int) -> int:
    """Get number of SplitBoss enemies for a level.
    
    Uses continuous scaling formula: base + scale_factor * sqrt(effective_level)
    This provides slow, diminishing returns scaling that continues indefinitely.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of SplitBoss enemies (0 for tutorial levels, then continuous scaling).
    """
    if level <= config.TUTORIAL_LEVELS:
        return 0
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    # Continuous scaling with square root for diminishing returns
    count = config.SPLIT_BOSS_BASE_COUNT + config.SPLIT_BOSS_SCALE_FACTOR * math.sqrt(effective_level)
    return round(count)


def get_flocker_count(level: int) -> int:
    """Get number of flocker enemy ships for a level.
    
    Uses continuous scaling formula: base + scale_factor * sqrt(effective_level)
    This provides slow, diminishing returns scaling that continues indefinitely.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of flocker enemies (0 for tutorial levels, then continuous scaling).
    """
    if level <= config.TUTORIAL_LEVELS:
        return 0
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    # Continuous scaling with square root for diminishing returns
    count = config.FLOCKER_ENEMY_BASE_COUNT + config.FLOCKER_ENEMY_SCALE_FACTOR * math.sqrt(effective_level)
    return round(count)


def get_egg_count(level: int) -> int:
    """Get number of egg enemies for a level.
    
    Uses continuous scaling formula: base + scale_factor * sqrt(effective_level)
    This provides slow, diminishing returns scaling that continues indefinitely.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of egg enemies (0 for tutorial levels, then continuous scaling).
    """
    if level <= config.TUTORIAL_LEVELS:
        return 0
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    # Continuous scaling with square root for diminishing returns
    count = config.EGG_BASE_COUNT + config.EGG_SCALE_FACTOR * math.sqrt(effective_level)
    return round(count)


def get_mother_boss_count(level: int) -> int:
    """Get number of Mother Boss enemies for a level.
    
    Uses continuous scaling formula: base + scale_factor * sqrt(effective_level)
    This provides slow, diminishing returns scaling that continues indefinitely.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of Mother Boss enemies (0 for tutorial levels, then continuous scaling).
    """
    if level <= config.TUTORIAL_LEVELS:
        return 0
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    # Continuous scaling with square root for diminishing returns
    count = config.MOTHER_BOSS_BASE_COUNT + config.MOTHER_BOSS_SCALE_FACTOR * math.sqrt(effective_level)
    return round(count)


def get_enemy_speed(level: int, enemy_type: str) -> float:
    """Get movement speed for an enemy type at a given level.
    
    Args:
        level: Current level number (1-based).
        enemy_type: Type of enemy ('static', 'patrol', or 'aggressive').
        
    Returns:
        Movement speed for the enemy type at this level.
    """
    if enemy_type == "static":
        return 0.0
    
    # Base speed from config
    if enemy_type == "patrol":
        base_speed = config.ENEMY_PATROL_SPEED
    elif enemy_type == "aggressive":
        base_speed = config.ENEMY_AGGRESSIVE_SPEED
    else:
        raise ValueError(f"Unknown enemy type: {enemy_type}")
    
    # Tutorial levels use base speed, scaling starts after
    if level <= config.TUTORIAL_LEVELS:
        return base_speed
    
    # Scale speed by effective level: 10% increase per effective level
    effective_level = level - config.TUTORIAL_LEVELS
    speed_multiplier = 1.0 + (effective_level - 1) * 0.1
    return base_speed * speed_multiplier


def get_enemy_damage(level: int) -> int:
    """Get damage value for enemies at a given level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Damage value for enemies at this level.
    """
    # Tutorial levels use base damage, scaling starts after
    if level <= config.TUTORIAL_LEVELS:
        return config.ENEMY_DAMAGE
    
    # Base damage from config, scaled by effective level
    # 10% increase per effective level (rounded to nearest int)
    effective_level = level - config.TUTORIAL_LEVELS
    damage_multiplier = 1.0 + (effective_level - 1) * 0.1
    return int(config.ENEMY_DAMAGE * damage_multiplier)


def get_enemy_fire_interval(level: int) -> Tuple[int, int]:
    """Get fire interval range for enemies at a given level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Tuple of (min_interval, max_interval) in frames.
        Intervals decrease (faster firing) as level increases.
    """
    # Base intervals from config
    base_min = config.ENEMY_FIRE_INTERVAL_MIN
    base_max = config.ENEMY_FIRE_INTERVAL_MAX
    
    # Tutorial levels use base intervals, scaling starts after
    if level <= config.TUTORIAL_LEVELS:
        return (base_min, base_max)
    
    # Reduce interval by 5% per effective level (faster firing at higher levels)
    # Minimum interval is 60% of base (40% reduction max)
    effective_level = level - config.TUTORIAL_LEVELS
    reduction_factor = min(0.4, (effective_level - 1) * 0.05)
    interval_multiplier = 1.0 - reduction_factor
    
    min_interval = int(base_min * interval_multiplier)
    max_interval = int(base_max * interval_multiplier)
    
    # Ensure minimum values
    min_interval = max(min_interval, 30)  # At least 0.5 seconds at 60 FPS
    max_interval = max(max_interval, min_interval + 60)  # At least 1 second range
    
    return (min_interval, max_interval)


def get_enemy_fire_range(level: int) -> float:
    """Get fire range for enemies at a given level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Maximum distance to player for firing (pixels).
        Range increases as level increases.
    """
    # Base range from config
    base_range = config.ENEMY_FIRE_RANGE
    
    # Tutorial levels use base range, scaling starts after
    if level <= config.TUTORIAL_LEVELS:
        return base_range
    
    # Increase range by 5% per effective level
    effective_level = level - config.TUTORIAL_LEVELS
    range_multiplier = 1.0 + (effective_level - 1) * 0.05
    return base_range * range_multiplier


def get_enemy_counts(level: int) -> EnemyCounts:
    """Get complete enemy count configuration for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        EnemyCounts dataclass with all enemy counts.
    """
    total = get_enemy_count(level)
    distribution = get_enemy_type_distribution(level, total)
    replay = get_replay_enemy_count(level)
    flocker = get_flocker_count(level)
    egg = get_egg_count(level)
    
    return EnemyCounts(
        total=total,
        static=distribution['static'],
        patrol=distribution['patrol'],
        aggressive=distribution['aggressive'],
        replay=replay,
        flocker=flocker,
        egg=egg
    )


def get_enemy_strength(level: int) -> EnemyStrength:
    """Get complete enemy strength configuration for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        EnemyStrength dataclass with all strength properties.
    """
    fire_interval_min, fire_interval_max = get_enemy_fire_interval(level)
    
    return EnemyStrength(
        patrol_speed=get_enemy_speed(level, "patrol"),
        aggressive_speed=get_enemy_speed(level, "aggressive"),
        damage=get_enemy_damage(level),
        fire_interval_min=fire_interval_min,
        fire_interval_max=fire_interval_max,
        fire_range=get_enemy_fire_range(level)
    )


def get_maze_complexity(level: int) -> MazeComplexity:
    """Get default maze complexity for a level.
    
    Tutorial levels use simpler complexities, scaling starts after tutorial levels.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        MazeComplexity based on level:
        - Tutorial levels (1-6):
          - Level 1: EMPTY (perimeter only, no obstacles)
          - Levels 2-3: SIMPLE
          - Levels 4-6: NORMAL
        - After tutorial levels:
          - Effective level 1-2: NORMAL
          - Effective level 3-4: COMPLEX
          - Effective level 5+: EXTREME
    """
    # Tutorial levels use simpler complexities
    if level <= config.TUTORIAL_LEVELS:
        return MazeComplexity.EMPTY
    
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    
    # Scale complexity based on effective level
    if effective_level <= 5:
        print(f"Level {level} is NORMAL")
        return MazeComplexity.NORMAL
    elif effective_level <= 12:
        print(f"Level {level} is COMPLEX")
        return MazeComplexity.COMPLEX
    else:
        print(f"Level {level} is EXTREME")
        return MazeComplexity.EXTREME


def get_maze_grid_size(level: int) -> int:
    """Get default maze grid size for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Grid size (width/height in cells). Maze is always square.
        Tutorial levels use base size, scaling starts after tutorial levels.
        Capped at MAX_MAZE_SIZE to prevent excessive cells at high levels.
    """
    if level <= config.TUTORIAL_LEVELS:
        return config.BASE_MAZE_SIZE
    # Difficulty scaling starts after tutorial levels
    effective_level = level - config.TUTORIAL_LEVELS
    calculated_size = config.BASE_MAZE_SIZE + (effective_level - 1) * config.MAZE_SIZE_INCREMENT
    # Cap at maximum to prevent excessive cells at high levels
    return min(calculated_size, config.MAX_MAZE_SIZE)


