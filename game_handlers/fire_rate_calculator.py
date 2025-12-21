"""Fire rate calculation for player ship.

This module provides fire rate calculation based on gun upgrade level,
following Single Responsibility Principle.
"""

import config
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from entities.ship import Ship


def calculate_fire_cooldown(ship: 'Ship') -> int:
    """Calculate fire cooldown based on ship's gun upgrade level.
    
    Args:
        ship: The player ship.
        
    Returns:
        Fire cooldown in milliseconds.
    """
    base_cooldown = 200  # Default 200ms between shots
    upgrade_level = ship.get_gun_upgrade_level()
    
    if upgrade_level == 1:
        return int(base_cooldown / config.POWERUP_LEVEL_1_FIRE_RATE_MULTIPLIER)
    elif upgrade_level == 2:
        return int(base_cooldown / config.POWERUP_LEVEL_2_FIRE_RATE_MULTIPLIER)
    elif upgrade_level == 3:
        return int(base_cooldown / config.POWERUP_LEVEL_3_FIRE_RATE_MULTIPLIER)
    
    return base_cooldown

