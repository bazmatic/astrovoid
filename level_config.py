"""Level configuration loader.

This module handles loading per-level configuration files that can override
default seed and enemy counts. Levels without config files use default behavior.
"""

import config
import json
import logging
import os
from typing import Optional, Dict
import level_rules
from level_rules import EnemyCounts, anemones_that_fit, get_anemone_count, get_enemy_counts, get_split_boss_count
from level_layout import Layout, LayoutError, parse_layout
from maze.config import MazeComplexity
from policies.ammo import AMMO_POLICIES, DEFAULT_AMMO_POLICY, AmmoPolicy
from policies.exit import DEFAULT_EXIT_POLICY, EXIT_POLICIES, ExitPolicy
from policies.registry import PolicyError, PolicyRegistry


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


_warned_layouts = set()


def get_level_layout(level: int) -> Optional[Layout]:
    """The level file's hand-made layout, or None if it has none or it cannot be played (that is logged)."""
    data = load_level_config(level)
    if not data or 'layout' not in data:
        return None
    try:
        return parse_layout(data['layout'], get_maze_grid_size(level))
    except (LayoutError, TypeError, ValueError, KeyError) as exc:
        if (level, str(exc)) not in _warned_layouts:       # every count reads the layout: say it once
            _warned_layouts.add((level, str(exc)))
            logging.getLogger(__name__).warning('Level %d: ignoring its layout: %s', level, exc)
        return None


_warned_policies = set()


def _level_policy(level: int, key: str, registry: PolicyRegistry, generated, default):
    """The policy the level's file names under `key` (or the generation rules give a level without a file)."""
    data = load_level_config(level)
    entry = data.get(key) if data is not None else generated(level)
    if entry is None:
        return default
    try:
        return registry.parse(entry)
    except PolicyError as exc:
        if (level, key, str(exc)) not in _warned_policies:   # asked for on every start: say it once
            _warned_policies.add((level, key, str(exc)))
            logging.getLogger(__name__).warning('Level %d: ignoring its %s: %s', level, registry.family, exc)
        return default


def get_level_exit_policy(level: int) -> ExitPolicy:
    """When the level's exit opens."""
    return _level_policy(level, 'exit_policy', EXIT_POLICIES, level_rules.generated_exit_policy,
                         DEFAULT_EXIT_POLICY)


def get_level_ammo_policy(level: int) -> AmmoPolicy:
    """Whether the level's ammo runs out."""
    return _level_policy(level, 'ammo_policy', AMMO_POLICIES, level_rules.generated_ammo_policy,
                         DEFAULT_AMMO_POLICY)


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
    layout = get_level_layout(level)
    if layout is not None:
        counts = layout.counts()
        return EnemyCounts(total=counts['static'] + counts['patrol'] + counts['aggressive'],
                           static=counts['static'], patrol=counts['patrol'], aggressive=counts['aggressive'],
                           replay=counts['replay'], flocker=counts['flocker'], flighthouse=counts['flighthouse'],
                           egg=counts['egg'], anemone=counts['anemone'])
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
    flocker = enemies_config.get('flocker', default_counts.flocker)
    flighthouse = enemies_config.get('flighthouse', default_counts.flighthouse)
    egg = enemies_config.get('egg', default_counts.egg)
    anemone = get_level_anemone_count(level)
    
    # Calculate total from the sum of regular enemies
    total = static + patrol + aggressive
    
    return EnemyCounts(
        total=total,
        static=static,
        patrol=patrol,
        aggressive=aggressive,
        replay=replay,
        flocker=flocker,
        flighthouse=flighthouse,
        egg=egg,
        anemone=anemone
    )


def get_level_anemone_count(level: int) -> int:
    """Get anemone count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        The number the level's config asks for, taken as given. Otherwise the
        number from level_rules, held to what the level's maze has room for.
    """
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['anemone']
    config = load_level_config(level)
    if config and 'anemone' in config.get('enemies', {}):
        return max(0, int(config['enemies']['anemone']))
    return min(get_anemone_count(level), anemones_that_fit(get_maze_grid_size(level)))


def get_level_split_boss_count(level: int) -> int:
    """Get split boss count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Split boss count from config if present, otherwise default from level_rules.
    """
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['split_boss']
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
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['mother_boss']
    from level_rules import get_mother_boss_count
    config = load_level_config(level)
    if config and 'enemies' in config and 'mother_boss' in config['enemies']:
        return int(config['enemies']['mother_boss'])
    return get_mother_boss_count(level)


def get_level_rules_hunter_count(level: int) -> int:
    """Rules hunters on a level: the level file's `rules_hunter` count, else none."""
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['rules_hunter']
    config = load_level_config(level)
    if config and 'enemies' in config and 'rules_hunter' in config['enemies']:
        return int(config['enemies']['rules_hunter'])
    return 0


def get_level_neural_hunter_count(level: int) -> int:
    """Neural hunters on a level: the level file's `neural_hunter` count, else none."""
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['neural_hunter']
    config = load_level_config(level)
    if config and 'enemies' in config and 'neural_hunter' in config['enemies']:
        return int(config['enemies']['neural_hunter'])
    return 0


def get_level_egg_count(level: int) -> int:
    """Get egg count for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Egg count from config if present, otherwise default from level_rules.
    """
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['egg']
    config = load_level_config(level)
    if config and 'enemies' in config and 'egg' in config['enemies']:
        return int(config['enemies']['egg'])
    return get_enemy_counts(level).egg


def get_maze_complexity(level: int) -> MazeComplexity:
    """Get maze complexity for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        MazeComplexity from config if present and valid, otherwise default from level_rules.
    """
    config = load_level_config(level)
    if config and 'maze' in config and 'complexity' in config['maze']:
        complexity_map = {
            'empty': MazeComplexity.EMPTY,
            'simple': MazeComplexity.SIMPLE,
            'normal': MazeComplexity.NORMAL,
            'complex': MazeComplexity.COMPLEX,
            'extreme': MazeComplexity.EXTREME,
        }
        complexity_str = str(config['maze']['complexity']).lower()
        if complexity_str in complexity_map:
            return complexity_map[complexity_str]
    
    return level_rules.get_maze_complexity(level)


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



def get_level_hunter_config(level: int):
    """Return the level file's hunter entry: a spawn override, False for no hunter, or None if absent."""
    layout = get_level_layout(level)
    if layout is not None:
        return {'spawn_cell': list(layout.beacon)} if layout.beacon is not None else False
    data = load_level_config(level)
    return data.get('hunter') if data else None


def level_has_hunter(level: int) -> bool:
    """Whether a level starts with a Jev beacon, the pickup that summons the hunter.

    A level file decides if it says anything: False forbids one, a spawn
    override places one. Otherwise there is none before HUNTER_FIRST_LEVEL,
    and one every HUNTER_LEVEL_INTERVAL levels from then on.
    """
    if get_level_hunter_config(level) is None:
        interval = config.HUNTER_LEVEL_INTERVAL
        return level_allows_jev_beacon(level) and interval > 0 and level % interval == 0
    return level_allows_jev_beacon(level)


def level_allows_jev_beacon(level: int) -> bool:
    """Whether a Jev beacon may appear on a level at all, placed or dropped by an enemy.

    False in a level file forbids it and a spawn override allows it. Otherwise
    there is none before HUNTER_FIRST_LEVEL.
    """
    hunter = get_level_hunter_config(level)
    if hunter is not None:
        return hunter is not False
    return level >= config.HUNTER_FIRST_LEVEL
