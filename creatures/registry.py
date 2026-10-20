"""Every Trait and Body by the name config/enemies.json gives it, and the check that the catalogue's creatures can be
built."""
from typing import Dict, Mapping, Type

from creatures.trait import Trait
from creatures.traits import brains, combat, crowd, propulsion
from entities.belemnite import BelemniteBody
from entities.jellyfish import Jellyfish
from entities.patrol_crab import PatrolCrab
from entities.urchin import Urchin

TRAITS: Dict[str, Type[Trait]] = {trait.NAME: trait for trait in (
    brains.Still, brains.Patrol, brains.Chase,
    propulsion.Coasts, propulsion.Drift,
    combat.TakesHits, combat.ShovedByShots, combat.RamsShip, combat.DropsPickup, combat.BouncesOffWalls, combat.Gun, combat.Explodes,
    crowd.KeepsApart,
)}
BODIES: Dict[str, type] = {'urchin': Urchin, 'crab': PatrolCrab, 'jelly': Jellyfish, 'belemnite': BelemniteBody}


def validate(catalogue: Mapping) -> None:
    """Raise ValueError, naming the kind, for an unknown body or trait, bad parameters, or a missing requirement."""
    for key, kind in catalogue.items():
        if kind.body is None:
            continue
        if kind.body not in BODIES:
            raise ValueError(f'enemy kind {key!r}: unknown body {kind.body!r}')
        names = [name for name, _ in kind.traits]
        for name, params in kind.traits:
            if name not in TRAITS:
                raise ValueError(f'enemy kind {key!r}: unknown trait {name!r}')
            try:
                TRAITS[name].from_params(params)
            except ValueError as error:
                raise ValueError(f'enemy kind {key!r}: {error}') from None
            missing = [needed for needed in TRAITS[name].REQUIRES if needed not in names]
            if missing:
                raise ValueError(f'enemy kind {key!r}: trait {name!r} requires {missing}')
