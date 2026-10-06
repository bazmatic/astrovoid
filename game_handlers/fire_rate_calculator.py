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
    
    Levels 1-3 use the configured fire rate multipliers. Each level beyond 3
    multiplies the level 3 rate by a further growth factor, down to a minimum
    cooldown, so every upgrade keeps the gun at least as fast as before.
    
    Args:
        ship: The player ship.
        
    Returns:
        Fire cooldown in milliseconds.
    """
    powerups = config.SETTINGS.powerups
    base_cooldown = powerups.fireRateBaseCooldown
    upgrade_level = ship.get_gun_upgrade_level()
    
    multipliers = powerups.fireRateMultipliers
    if upgrade_level <= 0:
        return base_cooldown
    if upgrade_level == 1:
        return int(base_cooldown / multipliers.level1)
    if upgrade_level == 2:
        return int(base_cooldown / multipliers.level2)
    
    beyond = powerups.beyondLevel3
    rate_multiplier = multipliers.level3 * beyond.fireRateGrowth ** (upgrade_level - 3)
    level3_cooldown = int(base_cooldown / multipliers.level3)
    floor = min(beyond.minFireCooldown, level3_cooldown)
    return max(floor, int(base_cooldown / rate_multiplier))
