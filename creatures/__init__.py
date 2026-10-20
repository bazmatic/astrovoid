"""Creatures: enemies assembled from config/enemies.json, a Body and a list of Traits.

A kind whose catalogue entry names a `body` is built here; the rest keep their own classes until they move over.
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
