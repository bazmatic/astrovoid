"""Creatures: enemies assembled from config/enemies.json, a Body and a list of Traits.

Every enemy kind is built here from its catalogue Body and Traits.
"""
import enemy_kinds
from creatures import registry
from creatures.creature import Creature


def build(kind_key: str, pos, level: int = 1, recorder=None, pilot_setup=None, angle=None) -> Creature:
    """A new Creature of this kind, its traits in catalogue order."""
    kind = enemy_kinds.kind(kind_key)
    settings = None
    if kind.pilot is not None:
        from dataclasses import replace
        from hunter.build import flight_kind
        from hunter.settings_for import hunter_settings_for
        settings = (pilot_setup.settings if pilot_setup is not None else
                    replace(hunter_settings_for(kind.pilot), indestructible=True))
        kind = flight_kind(kind, settings)
    traits = [registry.TRAITS[name].from_params(params) for name, params in kind.traits]
    creature = Creature(kind, pos, None, traits, level=level, recorder=recorder, angle=angle)
    creature.pilot_setup = pilot_setup
    if settings is not None:
        creature.settings = settings
    creature.body = registry.BODIES[kind.body](creature)
    return creature


registry.validate(enemy_kinds._CATALOGUE)
