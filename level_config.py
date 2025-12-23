"""Level configuration loader.

This module handles loading per-level configuration files that can override
default seed and enemy counts. Levels without config files use default behavior.
"""

import json
import os
from typing import Optional, Dict
import level_rules
from level_rules import EnemyCounts, get_enemy_counts, get_split_boss_count, get_egg_count
from maze.config import MazeComplexity


def load_level_config(level: int) -> Optional[Dict]:
    """Load level configuration from JSON file.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Parsed JSON dictionary if file exists, None otherwise.
        Returns None on file not found or JSON parsing errors.
    """
    from utils.resource_path import resource_path
    config_path = resource_path(f"levels/{level}.json")
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # Return None on any error to fall back to defaults
        # Silently fail to avoid disrupting gameplay
        return None


def get_level_seed(level: int) -> int:
    """Get random seed for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Seed value from config if present, otherwise level number (default).
    """
    config = load_level_config(level)
    if config and 'seed' in config:
        return int(config['seed'])
    return level


def get_level_enemy_counts(level: int) -> Optional[EnemyCounts]:
    """Get enemy counts for a level with partial override support.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        EnemyCounts dataclass with config overrides applied, or None if no config exists.
        Unspecified enemy counts use defaults from level_rules.
    """
    config = load_level_config(level)
    if not config or 'enemies' not in config:
        return None
    
    # Get defaults
    default_counts = get_enemy_counts(level)
    enemies_config = config['enemies']
    
    # Apply partial overrides
    static = enemies_config.get('static', default_counts.static)
    patrol = enemies_config.get('patrol', default_counts.patrol)
    aggressive = enemies_config.get('aggressive', default_counts.aggressive)
    replay = enemies_config.get('replay', default_counts.replay)
    egg = enemies_config.get('egg', default_counts.egg)
    
    # Calculate total from the sum of regular enemies
    total = static + patrol + aggressive
    
    return EnemyCounts(
        total=total,
        static=static,
        patrol=patrol,
        aggressive=aggressive,
        replay=replay,
        egg=egg
    )


def get_level_split_boss_count(level: int) -> int:
    """Get split boss count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Split boss count from config if present, otherwise default from level_rules.
    """
    config = load_level_config(level)
    if config and 'enemies' in config and 'split_boss' in config['enemies']:
        return int(config['enemies']['split_boss'])
    return get_split_boss_count(level)


def get_level_mother_boss_count(level: int) -> int:
    """Get mother boss count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Mother boss count from config if present, otherwise default from level_rules.
    """
    from level_rules import get_mother_boss_count
    config = load_level_config(level)
    if config and 'enemies' in config and 'mother_boss' in config['enemies']:
        return int(config['enemies']['mother_boss'])
    return get_mother_boss_count(level)


def get_level_egg_count(level: int) -> int:
    """Get egg count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Egg count from config if present, otherwise default from level_rules.
    """
    config = load_level_config(level)
    if config and 'enemies' in config and 'egg' in config['enemies']:
        return int(config['enemies']['egg'])
    return get_egg_count(level)


def get_maze_complexity(level: int) -> Optional[MazeComplexity]:
    """Get maze complexity for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        MazeComplexity from config if present, None otherwise (will use level-based default).
    """
    config = load_level_config(level)
    if not config or 'maze' not in config or 'complexity' not in config['maze']:
        return None
    
    complexity_str = config['maze']['complexity'].lower()
    
    # Map string values to enum
    complexity_map = {
        'empty': MazeComplexity.EMPTY,
        'simple': MazeComplexity.SIMPLE,
        'normal': MazeComplexity.NORMAL,
        'complex': MazeComplexity.COMPLEX,
        'extreme': MazeComplexity.EXTREME,
    }
    
    if complexity_str in complexity_map:
        return complexity_map[complexity_str]
    
    # Invalid value, return None to use default
    return None


def get_maze_grid_size(level: int) -> int:
    """Get maze grid size for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Grid size from config if present, otherwise calculated from level_rules.
        Grid size is the width/height of the maze in cells (maze is always square).
    """
    level_config = load_level_config(level)
    if level_config and 'maze' in level_config and 'grid_size' in level_config['maze']:
        grid_size = int(level_config['maze']['grid_size'])
        
        # Validate grid size is reasonable (minimum 5, maximum 100)
        if 5 <= grid_size <= 100:
            return grid_size
    
    # Fetch default grid size from level_rules
    return level_rules.get_maze_grid_size(level)

