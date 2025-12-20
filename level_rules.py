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
import config


@dataclass
class EnemyCounts:
    """Enemy count configuration for a level.
    
    Attributes:
        total: Total number of regular enemies
        static: Number of static enemies
        patrol: Number of patrol enemies
        aggressive: Number of aggressive enemies
        replay: Number of replay enemy ships
    """
    total: int
    static: int
    patrol: int
    aggressive: int
    replay: int


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
    return config.BASE_ENEMY_COUNT + (level - 1) * config.ENEMY_COUNT_INCREMENT


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
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Number of replay enemies (1-5, scaling up to 5 at level 10+).
    """
    if level >= 10:
        return 5
    else:
        # Scale from 1 to 4 for levels 1-9
        # Level 1=1, Level 2-3=2, Level 4-6=3, Level 7-9=4
        return min(1 + (level - 1) // 2, 4)


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
    
    # Scale speed by level: 10% increase per level (1.0 + (level - 1) * 0.1)
    speed_multiplier = 1.0 + (level - 1) * 0.1
    return base_speed * speed_multiplier


def get_enemy_damage(level: int) -> int:
    """Get damage value for enemies at a given level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Damage value for enemies at this level.
    """
    # Base damage from config, scaled by level
    # 10% increase per level (rounded to nearest int)
    damage_multiplier = 1.0 + (level - 1) * 0.1
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
    
    # Reduce interval by 5% per level (faster firing at higher levels)
    # Minimum interval is 60% of base (40% reduction max)
    reduction_factor = min(0.4, (level - 1) * 0.05)
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
    
    # Increase range by 5% per level
    range_multiplier = 1.0 + (level - 1) * 0.05
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
    
    return EnemyCounts(
        total=total,
        static=distribution['static'],
        patrol=distribution['patrol'],
        aggressive=distribution['aggressive'],
        replay=replay
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

