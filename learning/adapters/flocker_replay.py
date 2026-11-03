"""Rule-checked exact action replay for Flockers."""
import copy
from types import SimpleNamespace
from learning.replay import check_rules
from learning.flocker_rewards import recovered_settings


def metadata_args(path,manifest):
    return SimpleNamespace(horizon=manifest['horizon'],opponent=path/'opponent.npz',
                           **recovered_settings({'manifest':manifest}))


def open_environment(path,manifest):
    from learning.adapters import flocker_scenario as scenario
    if manifest.get('scenario_version') not in (5,6,8,9,10,11,12,13) or manifest['spec']['version']!=5:
        raise ValueError('unsupported Flocker physics/policy version')
    def recorded_flight(rules):
        # Historical size and the known version-1 propulsion are reconstructed by
        # environment_options. Every other rule remains strict.
        rules = copy.deepcopy(rules)
        rules['rewards'].setdefault('wall_collision_penalty',0.)
        rules['rewards'].setdefault('bunch_distance',35.)
        rules['rewards'].setdefault('contact_only',0.)
        rules['rewards'].setdefault('damage_penalty',0.)
        rules['rewards'].setdefault('threat_penalty',0.)
        rules['creature']['tuning']['size'] = manifest['creature']['tuning']['size']
        if manifest['scenario_version']==1:
            rules['scenario_version']=1
            rules['spec']['version']=1
            traits=dict(rules['creature']['traits'])
            traits['thrusters']=dict(manifest['creature']['traits'])['thrusters']
            rules['creature']['traits']=[[n,traits[n]] for n,_ in rules['creature']['traits']]
        return rules
    check_rules(path,manifest,scenario.metadata,effective_rules=recorded_flight,metadata_args=metadata_args)
    return scenario.environment(horizon=manifest['horizon'],arenas=manifest['arenas'],opponent=path/'opponent.npz',
                                **scenario.environment_options(manifest))


def status(env,job):
    e = env.events()
    return [f'FLOCKERS — stage {env.stage} — level {env.level} — {e["seconds"]:.1f}s',
            f'Alive {e["alive"]}/{env.team_size}   Hits {e.get("hits",0)}   Volleys {e["useful_volleys"]}',
            f'Perches {e.get("perches",0)}   Throttle {e["mean_throttle"]:.2f}']
