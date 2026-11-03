"""Run-scoped coefficients; potential progress is signed to prevent oscillation farming."""
import math

DEFAULTS = dict(progress_reward=.04, bite_reward=2., success_reward=4., death_penalty=5.,
                effort_cost=.03, airborne_cost=.08, time_cost=.002, action_change_cost=.01)
SETTINGS = tuple('inchworm_'+n for n in DEFAULTS)


def validate(values):
    if set(values)-set(DEFAULTS):
        raise ValueError('unknown inchworm reward setting')
    result = dict(DEFAULTS, **values)
    if any(not math.isfinite(v) or v < 0 for v in result.values()):
        raise ValueError('inchworm rewards must be finite and nonnegative')
    return result


def from_args(args):
    return validate({n:getattr(args,'inchworm_'+n,v) for n,v in DEFAULTS.items()})


def recovered_settings(config):
    return {'inchworm_'+n:v for n,v in validate(config.get('manifest',{}).get('rewards',{})).items()}
