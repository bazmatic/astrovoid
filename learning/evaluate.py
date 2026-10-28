"""Reproduce a run's fixed held-out neural/scripted/muted comparisons."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from learning.tasks import task
from learning.run import Rollouts, evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--out',type=Path)
    options=parser.parse_args()
    config=json.loads((options.run/'config.json').read_text())
    args=SimpleNamespace(**config['args'])
    args.opponent=str((options.run/'opponent.npz').resolve())
    adapter=task(args.task).adapter()
    expected=dict(config['manifest']);expected.pop('training',None)
    current=json.loads(json.dumps(adapter.metadata(args)))
    current['arenas']=expected['arenas']
    if current!=expected:
        raise ValueError('current rules differ from the frozen evaluation manifest')
    weights=options.run/'best.npz'
    pool=Rollouts(options.workers)
    try:
        cases=adapter.evaluation_cases()
        reports={name:evaluate(pool,args,weights,cases,mode='scripted' if name=='scripted' else 'greedy',
                               muted=name=='muted') for name in ('trained','scripted','muted')}
        reports['communication_effect']=adapter.compare(reports['trained'],reports['muted'])
        reports['versus_scripted']=adapter.compare(reports['trained'],reports['scripted'])
        reports['checkpoint_sha256']=hashlib.sha256(weights.read_bytes()).hexdigest()
        output=options.out or options.run/'reevaluation.json'
        output.write_text(json.dumps(reports,indent=2))
        print(output)
    finally:
        pool.close()


if __name__=='__main__':
    main()
