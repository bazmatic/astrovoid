"""Task-registered training lifecycle, bounded runs, evaluation and reproducible replays."""
import json
import os
from pathlib import Path
import time
import numpy as np


def _worker_init():
    os.environ['SDL_VIDEODRIVER'] = os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = '1'


def rollout_job(job):
    from learning.tasks import task
    from learning.policy import RecurrentPolicy
    from learning.training import collect
    adapter = task(job['task']).adapter()
    config_path = Path(job['weights']).parent/'config.json'
    recorded = json.loads(config_path.read_text()) if config_path.exists() else {}
    env = adapter.environment(opponent=job['opponent'], horizon=job['horizon'], muted=job['muted'],
                              arenas=recorded.get('manifest', {}).get('arenas'), scripted=job['mode']=='scripted')
    policy = RecurrentPolicy.load(job['weights'], adapter.SPEC)
    teacher = env.adapter.teacher_action if job['mode'] == 'teacher' else None
    case = dict(job['case']); seed = case.pop('seed')
    try:
        return collect(env, policy, seed, case, greedy=job['mode'] != 'sample', teacher=teacher)
    finally:
        env.close()


class Rollouts:
    def __init__(self, workers):
        import multiprocessing
        self.deadline = float('inf')
        self.pool = multiprocessing.get_context('spawn').Pool(workers, initializer=_worker_init) if workers > 1 else None
    def __call__(self, jobs):
        if self.pool is None:
            _worker_init()
            results = []
            for job in jobs:
                if time.monotonic() >= self.deadline:
                    raise TimeoutError('training wall-clock budget exhausted')
                results.append(rollout_job(job))
            return results
        return self.pool.map_async(rollout_job, jobs).get(timeout=max(.001,self.deadline-time.monotonic()))
    def close(self):
        if self.pool:
            self.pool.terminate(); self.pool.join()


def make_jobs(args, weights, cases, mode='sample', muted=False):
    return [dict(task=args.task,weights=str(weights),opponent=args.opponent,horizon=args.horizon,
                 case=case,mode=mode,muted=muted) for case in cases]


def evaluate(pool, args, weights, cases, mode='greedy', muted=False):
    from learning.tasks import task
    adapter = task(args.task).adapter()
    flown = pool(make_jobs(args,weights,cases,mode,muted))
    rows = [dict(result[1],**case) for result,case in zip(flown,cases)]
    return dict(summary=adapter.metrics(rows),episodes=rows)


def train(args):
    entered = time.monotonic()
    import torch
    import shutil
    from learning.tasks import task
    from learning.policy import random_policy, RecurrentPolicy
    from learning.models import export
    from learning.training import build_network, clone_behaviour
    from learning.ppo import update_team
    from tools.ppo_neural import write_state, PAUSE_FILE
    adapter = task(args.task).adapter()
    torch.set_num_threads(1)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.resume:
        args.opponent = str((out/'opponent.npz').resolve())
    expected = json.loads(json.dumps(adapter.metadata(args)))
    expected['training'] = {k:getattr(args,k) for k in ('seed','lr','gamma','gae_lambda','episodes','bootstrap_episodes')}
    config_path = out/'config.json'
    resume_path = out/'resume.pt'
    if args.resume:
        recorded = json.loads(config_path.read_text())
        if recorded['manifest'] != expected:
            raise ValueError('resume task, rules, schemas, opponent or arenas changed')
        saved = torch.load(resume_path, map_location='cpu', weights_only=False)
        policy = RecurrentPolicy.load(out/saved['policy'], adapter.SPEC)
    else:
        saved = None
        if resume_path.exists() or (out/'train.log').exists():
            raise ValueError('run already exists; use resume')
        if args.start and Path(args.start).resolve() != Path(args.opponent).resolve():
            policy = RecurrentPolicy.load(args.start, adapter.SPEC)
        else:
            policy = random_policy(adapter.SPEC, args.seed)
        shutil.copyfile(args.opponent, out/'opponent.npz')
        (out/'initial.npz').parent.mkdir(parents=True, exist_ok=True)
        policy.save(out/'initial.npz')
        config_path.write_text(json.dumps(dict(task=args.task, args=vars(args), manifest=expected,
                                              shaping=expected['rewards'], episode={'horizon_seconds':args.horizon},
                                              start=args.start), indent=2))
    # Use the immutable copy in every worker/replay, never whichever model is later installed in assets.
    args.opponent = str((out/'opponent.npz').resolve())
    torch.manual_seed(args.seed)
    net = build_network(policy, adapter.CRITIC_SIZE)
    optimiser = torch.optim.Adam(net.parameters(), lr=args.lr)
    rng = np.random.default_rng(args.seed)
    first, elapsed, team_size, best_score, current = 0, 0., adapter.INITIAL_STAGE, -float('inf'), 'initial.npz'
    if saved:
        net.load_state_dict(saved['net']); optimiser.load_state_dict(saved['optimiser'])
        rng.bit_generator.state = saved['rng']; torch.set_rng_state(saved['torch_rng'])
        first, elapsed, team_size = saved['iteration'], saved['elapsed'], saved['team_size']
        best_score, current = saved['best_score'], saved['policy']
    else:
        torch.manual_seed(args.seed)
    pool = Rollouts(args.workers)
    started = entered
    pool.deadline = started+max(0,args.budget_seconds-elapsed)
    reserve = min(600., args.budget_seconds/6)
    training_limit = max(0., args.budget_seconds-reserve)
    (out/'episodes').mkdir(exist_ok=True)
    validation = adapter.validation_cases()
    best = out/'best.npz'
    history = []
    log = (out/'train.log').open('a', buffering=1)
    def used(): return elapsed+time.monotonic()-started
    def save_resume(next_iteration):
        temp = out/'resume.tmp'
        torch.save(dict(net=net.state_dict(), optimiser=optimiser.state_dict(), rng=rng.bit_generator.state,
                        torch_rng=torch.get_rng_state(), iteration=next_iteration, elapsed=used(),
                        team_size=team_size, best_score=best_score, policy=current), temp)
        temp.replace(resume_path)
    try:
        if not saved:
            teacher_jobs = make_jobs(args,out/current,adapter.training_cases(0,args.bootstrap_episodes,team_size,bootstrap=True),'teacher')
            demonstrated = pool(teacher_jobs)
            clone_behaviour(net, [e for result in demonstrated for e in result[0]], dict(adapter.SPEC.heads), selected_heads=adapter.IMITATION_HEADS, epochs=4)
            policy = export(net, policy); current = 'bootstrap.npz'; policy.save(out/current)
            policy.save(best)
            best_score = adapter.selection_score(evaluate(pool,args,best,validation)['summary'])
            save_resume(0)
        for iteration in range(first, args.iterations):
            if used() >= training_limit:
                break
            weights = out/current
            cases = adapter.training_cases(iteration,args.episodes,team_size)
            jobs = make_jobs(args,weights,cases)
            rollout_at = time.monotonic()
            flown = pool(jobs)
            rollout_seconds = time.monotonic()-rollout_at
            update_at = time.monotonic()
            stats = update_team(net, optimiser, [e for result in flown for e in result[0]], rng,
                                gamma=args.gamma, lam=args.gae_lambda)
            policy = export(net, policy)
            previous, current = current, f'iter{iteration:04d}.npz'
            policy.save(out/current)
            rows = [dict(result[1], **case) for result,case in zip(flown,cases)]
            summary = adapter.metrics(rows)
            record = dict(iteration=iteration, policy=previous, task=args.task,
                          jobs=cases,
                          episodes=rows, actions=[result[2] for result in flown])
            (out/'episodes'/f'iter{iteration:04d}.json').write_text(json.dumps(record))
            if iteration % 5 == 0:
                score = adapter.selection_score(evaluate(pool, args, out/current, validation)['summary'])
                if score > best_score:
                    best_score = score; policy.save(best)
            team_size = adapter.promote(team_size,summary)
            line = dict(iteration=iteration, update_s=round(time.monotonic()-update_at,3),
                        mean_return=sum(sum(r[0][0]['rewards']) for r in flown)/len(flown),
                        rollout_s=round(rollout_seconds,3), team_size=team_size, elapsed_s=round(used(),1), **summary, **stats)
            text = ' '.join(f'{k}={v}' for k,v in line.items())
            print(text, flush=True); log.write(text+'\n'); history.append(line)
            save_resume(iteration+1)
            if (out/PAUSE_FILE).exists():
                (out/PAUSE_FILE).unlink(); write_state(out, 'paused', iteration)
                return dict(paused=True, history=history, last=str(out/current))
        # Fixed held-out arenas and seeds: no best-checkpoint selection on these results.
        cases = adapter.evaluation_cases()
        policy.save(out/current)
        if not best.exists(): policy.save(best)
        reports = {mode: evaluate(pool, args, best, cases, mode='scripted' if mode=='scripted' else 'greedy',
                                  muted=mode=='muted') for mode in ('trained','scripted','muted')}
        reports['communication_effect'] = adapter.compare(reports['trained'],reports['muted'])
        reports['versus_scripted'] = adapter.compare(reports['trained'],reports['scripted'])
        reports['wall_seconds'] = used()
        reports['opponent_sha256'] = expected['opponent_sha256']
        (out/'evaluation.json').write_text(json.dumps(reports, indent=2))
        write_state(out,'finished',history[-1]['iteration'] if history else first)
        return dict(paused=False,history=history,last=str(best))
    except (TimeoutError, __import__('multiprocessing').TimeoutError):
        (out/'evaluation.json').write_text(json.dumps(dict(budget_exhausted=True, wall_seconds=used(),
            message='Stopped at the wall-clock limit; completed checkpoints remain available.')))
        write_state(out,'finished',history[-1]['iteration'] if history else first)
        return dict(paused=False,history=history,last=str(best if best.exists() else out/current))
    finally:
        log.close(); pool.close()
