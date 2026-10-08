"""Fire rate calculation for player ship.

This module provides fire rate calculation based on gun upgrade level,
following Single Responsibility Principle.
"""

import config
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from entities.ship import Ship

SPREAD_LEVEL = 2  # Upgrade level from which each volley is a spread
SPREAD_SHOTS = 3


def shots_per_volley(upgrade_level: int) -> int:
    """How many projectiles one pull of the trigger releases at an upgrade level."""
    return SPREAD_SHOTS if upgrade_level >= SPREAD_LEVEL else 1


def calculate_fire_cooldown(ship: 'Ship') -> int:
    """Calculate fire cooldown based on ship's gun upgrade level.
    
    Every powerup adds the same amount of firepower: a fixed share of the
    base gun's projectiles per second. The effects do not compound, so once
    volleys become a spread they come more slowly than single shots did,
    though more projectiles leave the gun each second. The cooldown never
    drops below a minimum.
    
    Args:
        ship: The player ship.
        
    Returns:
        Fire cooldown in milliseconds.
    """
    powerups = config.SETTINGS.powerups
    base_cooldown = powerups.fireRateBaseCooldown
    upgrade_level = ship.get_gun_upgrade_level()
    if upgrade_level <= 0:
        return base_cooldown
    
    firepower = 1.0 + upgrade_level * powerups.firepowerPerCrystal
    cooldown = int(base_cooldown * shots_per_volley(upgrade_level) / firepower)
    return max(min(powerups.beyondLevel3.minFireCooldown, base_cooldown), cooldown)
