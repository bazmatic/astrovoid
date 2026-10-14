"""The hunter's settings for the pilot that flies it."""
from dataclasses import replace
from hunter.model import HunterSettings
from hunter.rule_params import RULES


def hunter_settings_for(mode):
    """The settings the game builds the hunter with when `game.hunterPilot` is `mode`.

    Jev's hunter is the default one: its held left and right turns for a whole decision, so the turn
    rate is set so that stays controllable. The rules pilot steers by exact
    angle (course and track modes), so its hunter takes the turn rate the lab found best
    (docs/experiments/010-turn-rate.md). Both are otherwise the same hunter.
    """
    if mode == 'neural':
        import config
        return replace(HunterSettings(), turn_rate_multiplier=config.SETTINGS.game.neuralTurnRate,
                       indestructible=False, health=config.SETTINGS.game.neuralHunterHealth,
                       wall_energy=config.SETTINGS.game.neuralWallEnergy)
    if mode == 'rules':
        return replace(HunterSettings(), thrust_multiplier=RULES.thrust_multiplier,
                       sensor_range_fraction=RULES.sensor_range_fraction,
                       turn_rate_multiplier=RULES.turn_rate_multiplier)
    return HunterSettings()
