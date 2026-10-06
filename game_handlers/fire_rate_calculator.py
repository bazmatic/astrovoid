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
    
    Each power-up increases firing rate by 10%, which means cooldown is reduced by 10%.
    Formula: cooldown = base_cooldown / (1.1^upgrade_level)
    
    Args:
        ship: The player ship.
        
    Returns:
        Fire cooldown in milliseconds.
    """
    base_cooldown = config.SETTINGS.powerups.fireRateBaseCooldown
    upgrade_level = ship.get_gun_upgrade_level()
    
    # Each power-up increases firing rate by 10% (reduces cooldown by 10%)
    # Level 0: 1.0, Level 1: 1.1, Level 2: 1.21, Level 3: 1.331, etc.
    rate_multiplier = 1.1 ** upgrade_level
    
    return int(base_cooldown / rate_multiplier)

