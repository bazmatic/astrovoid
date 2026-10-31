"""Matched closed-loop crawler evaluation with body recoil ablated in isolated workers."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import multiprocessing
from pathlib import Path
import numpy as np


@contextmanager
def body_recoil(enabled):
    """Keep muzzle velocity inheritance; remove only body impulses and recoil events."""
    from physics import recoil
    original = recoil.apply_firing_recoil
    def without_impulse(body, shot, launch_velocity=None, launch_spin=None):
        velocity = body.vx, body.vy
        spin = getattr(body, 'wall_angular_velocity', None)
        original(body, shot, launch_velocity, launch_spin)
        body.vx, body.vy = velocity
        if spin is not None:
            body.wall_angular_velocity = spin
        return False
    try:
        if not enabled:
            recoil.apply_firing_recoil = without_impulse
        yield
    finally:
        recoil.apply_firing_recoil = original


def phase_metrics(fired, accepted):
    result = {}
    for phase in ('attached','airborne'):
        shots = [shot for shot,launch_phase in fired.items() if launch_phase == phase]
        hits = sum(shot in accepted for shot in shots)
        result.update({phase+'_shots':len(shots), phase+'_hits':hits})
    return result


def rollout(job):
    from learning.replay import open_environment
    from learning.policy import RecurrentPolicy
    from learning.adapters.wallcrawler import SPEC
    from learning.adapters.crawler_scenario import BATTLE_ALIVE_RATE
    env = open_environment(job['run'])
    try:
        with body_recoil(job['recoil']):
            try:
                snap = env.reset(**job['case'])
            except ValueError as error:
                if not str(error).startswith(('arena has insufficient','pursuit arena lacks')):
                    raise
                return dict(case=job['case'],recoil=job['recoil'],invalid_start=str(error))
            policy = RecurrentPolicy.load(job['weights'], SPEC)
            states = {i:policy.initial_state() for i in snap.observations}
            fired = {}
            original_add = env.enc.add_shot
            def add_shot(shot):
                owner = next((c for c in env.world.roster.all()
                              if c.agent_id == getattr(shot,'actor_id',None)), None)
                if owner is not None:
                    fired[shot] = 'attached' if owner.wall_state == 'attached' else 'airborne'
                original_add(shot)
            env.enc.add_shot = add_shot
            while True:
                actions = {}
                for i,x in snap.observations.items():
                    actions[i], states[i] = policy.choose(x,states[i],snap.masks[i],greedy=True)
                transition = env.step(actions)
                snap = transition.snapshot
                if transition.terminated or transition.truncated:
                    break
            events = transition.events
            return dict(case=job['case'], recoil=job['recoil'],
                        survival=events['alive']/job['case']['team_size'],
                        success=float(events['battle_success']),
                        jellies_killed=events['battle_jelly_kills'],
                        mean_lifetime=events['battle_alive_reward']/BATTLE_ALIVE_RATE/job['case']['team_size'],
                        seconds=events['seconds'],hits=events['hits'],shots=events['shots'],
                        contacts=events['contact_hits_taken'],bullets=events['bullet_hits_taken'],
                        **phase_metrics(fired,env._accepted))
    finally:
        env.close()


def summarise(rows):
    result = {key:float(np.mean([r[key] for r in rows]))
              for key in ('survival','success','jellies_killed','mean_lifetime','seconds','contacts','bullets')}
    result['trials'] = len(rows)
    result['accuracy'] = sum(r['hits'] for r in rows)/max(1,sum(r['shots'] for r in rows))
    result['hits_per_minute'] = sum(r['hits'] for r in rows)*60/max(.001,sum(r['seconds'] for r in rows))
    total = sum(r['attached_shots']+r['airborne_shots'] for r in rows)
    for phase in ('attached','airborne'):
        shots = sum(r[phase+'_shots'] for r in rows)
        result[phase+'_shots'] = shots
        result[phase+'_accuracy'] = sum(r[phase+'_hits'] for r in rows)/max(1,shots)
    result['airborne_shot_fraction'] = result['airborne_shots']/max(1,total)
    return result


def compare(rows):
    if not rows:
        raise ValueError('no valid matched cases remain')
    on = [r for r in rows if r['recoil']]
    off = [r for r in rows if not r['recoil']]
    assert [r['case'] for r in on] == [r['case'] for r in off]
    rng = np.random.default_rng(0)
    indices = rng.integers(0,len(on),(5000,len(on)))
    differences = {}
    for key in ('survival','success','jellies_killed','mean_lifetime'):
        delta = np.array([a[key]-b[key] for a,b in zip(on,off)])
        bootstrap = delta[indices].mean(axis=1)
        differences[key] = dict(mean=float(delta.mean()),lower_95=float(np.quantile(bootstrap,.025)),
                                upper_95=float(np.quantile(bootstrap,.975)))
    return dict(recoil_on=summarise(on),recoil_off=summarise(off),paired_on_minus_off=differences)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--seeds',type=int,default=10,help='held-out seeds per arena and encounter')
    parser.add_argument('--out',type=Path,required=True)
    options = parser.parse_args()
    if options.seeds<1 or options.workers<1:
        parser.error('seeds and workers must be positive')
    from learning.run import _worker_init
    from learning.replay import open_environment
    env = open_environment(options.run);env.close()
    source = options.checkpoint if options.checkpoint.is_absolute() else options.run/options.checkpoint
    payload = source.read_bytes();digest = hashlib.sha256(payload).hexdigest()
    weights = options.run/f'evaluation-{digest}.npz'
    if not weights.exists():weights.write_bytes(payload)
    manifest = json.loads((options.run/'config.json').read_text())['manifest']
    cases = [dict(seed=seed,level=level,team_size=4,opponents='practice',practice_stage='pursuit',
                  jelly_count=4,neural_hunter=hunter)
             for hunter in (False,True) for level in manifest['holdout_levels']
             for seed in range(1000,1000+options.seeds)]
    jobs = [dict(run=str(options.run),weights=str(weights),case=case,recoil=enabled)
            for case in cases for enabled in (True,False)]
    with ProcessPoolExecutor(max_workers=options.workers,mp_context=multiprocessing.get_context('spawn'),
                             initializer=_worker_init) as pool:
        rows = []
        partial = options.out.with_suffix('.partial.jsonl')
        with partial.open('w') as progress:
            for row in pool.map(rollout,jobs):
                rows.append(row)
                progress.write(json.dumps(row)+'\n');progress.flush()
                if len(rows)%20==0:print(f'{len(rows)}/{len(jobs)} trials complete',flush=True)
    invalid = [r for r in rows if 'invalid_start' in r]
    invalid_on = [r['case'] for r in invalid if r['recoil']]
    invalid_off = [r['case'] for r in invalid if not r['recoil']]
    if invalid_on != invalid_off:
        raise ValueError('placement failed in only one condition; refusing an unmatched comparison')
    rows = [r for r in rows if 'invalid_start' not in r]
    reports = {name:compare([r for r in rows if r['case']['neural_hunter']==hunter])
               for name,hunter in (('jellies_only',False),('armed_hunter',True))}
    output = dict(checkpoint=str(source),checkpoint_sha256=digest,
                  intervention='disable_body_impulses_and_recoil_events_preserve_bullet_inheritance',
                  control='greedy_closed_loop',skipped_cases=invalid_on,reports=reports,episodes=rows)
    options.out.write_text(json.dumps(output,indent=2))
    print(json.dumps(reports,indent=2))
    print(options.out)


if __name__=='__main__':
    main()
