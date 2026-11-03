"""Run-scoped Flocker reward settings; shared by CLI, replay and dashboard."""
import math

DEFAULTS = dict(hit_reward=1., kill_reward=5., shot_cost=.05, death_penalty=5.,
                progress_reward=.002, aim_progress_reward=.2, cohesion_reward=.02, bunch_penalty=.01,
                stuck_penalty=.05, perch_reward=.1, volley_reward=.5, wall_collision_penalty=.1, bunch_distance=22., contact_only=1.,
                damage_penalty=2., threat_penalty=.05)
SETTINGS = tuple('flocker_'+n for n in DEFAULTS)


def validate(values):
    result = dict(DEFAULTS, **values)
    if any(not math.isfinite(v) or v < 0 for v in result.values()):
        raise ValueError('Flocker reward settings must be finite and nonnegative')
    if result['contact_only'] not in (0.,1.):
        raise ValueError('contact_only must be 0 or 1')
    if result['volley_reward'] >= result['hit_reward'] and result['volley_reward'] != 0:
        raise ValueError('volley reward must remain below one accepted hit reward')
    return result


def from_args(args):
    return validate({n:getattr(args,'flocker_'+n,v) for n,v in DEFAULTS.items()})


def from_manifest(manifest):
    # Older recordings paid no impact penalty and used a fixed 35-pixel proximity threshold, rather than contact-only credit.
    return validate({'wall_collision_penalty':0., 'aim_progress_reward':0., 'bunch_distance':35., 'contact_only':0., 'damage_penalty':0., 'threat_penalty':0., **manifest.get('rewards',{})})


def recovered_settings(config):
    return {'flocker_'+n:v for n,v in from_manifest(config.get('manifest',{})).items()}
