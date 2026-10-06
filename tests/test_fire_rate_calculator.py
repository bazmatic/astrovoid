from types import SimpleNamespace
from game_handlers.fire_rate_calculator import calculate_fire_cooldown


def cooldown(level):
    return calculate_fire_cooldown(SimpleNamespace(get_gun_upgrade_level=lambda: level))


def test_configured_multipliers_set_the_first_three_levels():
    assert [cooldown(level) for level in range(4)] == [200, 133, 100, 66]


def test_upgrades_beyond_level_three_keep_getting_faster_down_to_the_floor():
    assert cooldown(4) == 60
    assert cooldown(5) == 55
    assert cooldown(50) == 40


def test_cooldown_never_rises_with_upgrade_level():
    cooldowns = [cooldown(level) for level in range(60)]
    assert cooldowns == sorted(cooldowns, reverse=True)
