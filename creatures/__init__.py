"""Creatures: enemies assembled from config/enemies.json, a Body and a list of Traits.

Every enemy kind is built here from its catalogue Body and Traits.
"""
import enemy_kinds
from creatures import registry
from creatures.creature import Creature


def build(kind_key: str, pos, level: int = 1, recorder=None) -> Creature:
    """A new Creature of this kind, its traits in catalogue order."""
    kind = enemy_kinds.kind(kind_key)
    traits = [registry.TRAITS[name].from_params(params) for name, params in kind.traits]
    creature = Creature(kind, pos, None, traits, level=level, recorder=recorder)
    creature.body = registry.BODIES[kind.body](creature)
    return creature


registry.validate(enemy_kinds._CATALOGUE)
