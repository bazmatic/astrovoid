from types import SimpleNamespace

import pytest

import config
from game_handlers.fire_rate_calculator import calculate_fire_cooldown, shots_per_volley


def cooldown(level):
    return calculate_fire_cooldown(SimpleNamespace(get_gun_upgrade_level=lambda: level))


def firepower(level):
    """Projectiles per second."""
    return shots_per_volley(level) * 1000.0 / cooldown(level)


def test_base_gun_fires_at_the_base_cooldown():
    assert cooldown(0) == config.SETTINGS.powerups.fireRateBaseCooldown == 200


def test_first_levels():
    assert [cooldown(level) for level in range(4)] == [200, 100, 200, 150]
    assert [shots_per_volley(level) for level in range(4)] == [1, 1, 3, 3]


def test_every_powerup_adds_the_same_firepower():
    """Effects add up; they do not multiply."""
    # Cooldowns are whole milliseconds, hence the tolerance
    for level in range(9):
        assert firepower(level) == pytest.approx(firepower(0) * (1 + level), rel=0.03)


def test_firepower_never_falls_with_upgrade_level():
    levels = [firepower(level) for level in range(60)]
    assert levels == sorted(levels)


def test_cooldown_has_a_floor():
    assert cooldown(500) == config.SETTINGS.powerups.beyondLevel3.minFireCooldown
