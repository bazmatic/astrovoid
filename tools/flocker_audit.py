"""Small matched held-out Flocker audits while training continues.

This does not select or deploy weights. Full deployment evaluation remains separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--checkpoint',default=None)
    parser.add_argument('--stage',type=int,choices=range(1,7),default=None)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--horizon',type=float,default=60.)
    parser.add_argument('--seed',type=int,default=1600)
    parser.add_argument('--regroup',action='store_true',help='target-free reunion drills')
    parser.add_argument('--split-group',action='store_true')
    parser.add_argument('--validation-cases',action='store_true',help='use the exact curriculum promotion trials')
    parser.add_argument('--budget-seconds',type=float,default=180.)
    options=parser.parse_args()
    from learning.adapters import flocker_scenario as scenario
    from learning.run import Rollouts,evaluate
    import torch
    run=options.run.resolve()
    config=json.loads((run/'config.json').read_text())
    saved=torch.load(run/'resume.pt',map_location='cpu',weights_only=False)
    stage=options.stage or saved['curriculum']['stage']
    weights=run/(options.checkpoint or saved['policy'])
    args=SimpleNamespace(**config['args'])
    args.out=str(run)
    args.opponent=str(run/'opponent.npz')
    args.horizon=options.horizon
    cases=[dict(level=level,seed=options.seed+2*j+k,team_size=(2,4,6)[j],stage=stage,moving=bool(k),
                regroup=options.regroup,split_group=options.split_group)
           for j,level in enumerate(scenario.HOLDOUT_LEVELS) for k in range(2)]
    if options.validation_cases:
        cases=scenario.curriculum_validation_cases(dict(stage=stage))
    pool=Rollouts(options.workers)
    pool.deadline=time.monotonic()+options.budget_seconds
    started=time.monotonic()
    try:
        trained=evaluate(pool,args,weights,cases)
        scripted=scenario.scripted_report(cases,args.horizon,args.opponent,
            rewards=config['manifest']['rewards'],arenas=config['manifest']['arenas'],deadline=pool.deadline)
        report=dict(checkpoint=weights.name,checkpoint_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
            stage=stage,trained=trained,scripted=scripted,comparison=scenario.compare(trained,scripted),
            wall_seconds=time.monotonic()-started,cases=cases)
        folder=run/'audits';folder.mkdir(exist_ok=True)
        suffix=('-regroup' if options.regroup else '')+('-split' if options.split_group else '')
        if options.validation_cases:
            suffix+='-validation'
        path=folder/f'{weights.stem}-stage{stage}-seed{options.seed}{suffix}.json'
        path.write_text(json.dumps(report,indent=2))
        print(json.dumps(dict(report=str(path),stage=stage,checkpoint=weights.name,
            trained=trained['summary'],scripted=scripted['summary'])),flush=True)
    finally:
        pool.close()


if __name__=='__main__':main()
