"""Build one Creature-backed hunter flight with explicit pilot dependencies."""
from dataclasses import dataclass, replace

import config
from hunter.model import HunterSettings


@dataclass(frozen=True)
class PilotSetup:
    settings: HunterSettings
    pilot: object
    surroundings: object
    owns_worker: bool = False


def flight_kind(kind, settings):
    """Resolve one flight's fixed settings into its reusable traits, without mutating the catalogue."""
    overrides = {
        'energy': {'health': settings.health, 'indestructible': settings.indestructible,
                   'immunity': settings.damage_immunity, 'wallEnergy': settings.wall_energy},
        'thrusters': {'speedShare': 1, 'thrust': config.SHIP_THRUST_FORCE * settings.thrust_multiplier,
                      'turnRate': config.SHIP_ROTATION_SPEED * settings.turn_rate_multiplier, 'mode': 'hunter'},
        'burstFire': {'rounds': settings.burst_size, 'spacing': settings.burst_spacing,
                      'interval': settings.fire_interval},
    }
    return replace(kind, traits=tuple((name, {**params, **overrides.get(name, {})}) for name, params in kind.traits))


def make_hunter(pos, *, world, setup, angle=0.0):
    """Return a flight whose fully spawned allied Creature stays outside the world's enemy roster."""
    import creatures
    from creatures.encounter import Encounter
    from game_handlers.enemy_roster import EnemyRoster
    creature = creatures.build('allied_hunter', pos, pilot_setup=setup, angle=angle)
    creature.angle = angle
    roster = EnemyRoster()
    roster.add(creature)
    enc = Encounter(roster, world)
    enc.ready()
    return creature.flight
