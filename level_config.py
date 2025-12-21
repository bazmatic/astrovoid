"""Level configuration loader.

This module handles loading per-level configuration files that can override
default seed and enemy counts. Levels without config files use default behavior.
"""

import json
import os
from typing import Optional, Dict
from level_rules import EnemyCounts, get_enemy_counts, get_split_boss_count


def load_level_config(level: int) -> Optional[Dict]:
    """Load level configuration from JSON file.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Parsed JSON dictionary if file exists, None otherwise.
        Returns None on file not found or JSON parsing errors.
    """
    config_path = os.path.join("levels", f"{level}.json")
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Return None on any error to fall back to defaults
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
    
    # Calculate total from the sum of regular enemies
    total = static + patrol + aggressive
    
    return EnemyCounts(
        total=total,
        static=static,
        patrol=patrol,
        aggressive=aggressive,
        replay=replay
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

