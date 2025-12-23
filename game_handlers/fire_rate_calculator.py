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
    base_cooldown = config.SETTINGS.powerups.fireRateBaseCooldown
    upgrade_level = ship.get_gun_upgrade_level()
    
    multipliers = config.SETTINGS.powerups.fireRateMultipliers
    if upgrade_level == 1:
        return int(base_cooldown / multipliers.level1)
    elif upgrade_level == 2:
        return int(base_cooldown / multipliers.level2)
    elif upgrade_level == 3:
        return int(base_cooldown / multipliers.level3)
    
    return base_cooldown

