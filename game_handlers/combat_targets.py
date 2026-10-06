"""Shared target selection for enemies; ties preserve the player target."""


def nearest_friendly(enemy, player, hunter=None):
    candidates = [obj for obj in (player,hunter) if obj is not None and obj.active]
    return min(candidates, key=lambda obj:(obj.x-enemy.x)**2+(obj.y-enemy.y)**2, default=None)
