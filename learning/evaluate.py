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
    parser.add_argument('--suite',choices=('practice','ships','dodge','pursuit'),default='practice')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--checkpoint',type=Path,default=Path('best.npz'))
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
    source=options.checkpoint if options.checkpoint.is_absolute() else options.run/options.checkpoint
    payload=source.read_bytes()
    checkpoint_hash=hashlib.sha256(payload).hexdigest()
    # Workers must all see the same weights even while training updates best.npz.
    weights=options.run/f'evaluation-{checkpoint_hash}.npz'
    if not weights.exists():weights.write_bytes(payload)
    pool=Rollouts(options.workers)
    try:
        cases=adapter.evaluation_cases()
        if options.suite=='dodge':
            cases=[dict(case,practice_stage='dodge') for case in cases if case.get('practice_stage')=='pursuit']
        if options.suite in ('dodge','pursuit'):
            cases=[case for case in cases if case.get('practice_stage')==options.suite and case['team_size']==2]
        if options.suite=='ships':
            cases=[dict(case,opponents=mode) for case in cases for mode in ('hunter','mixed')]
        reports={name:evaluate(pool,args,weights,cases,mode='scripted' if name=='scripted' else 'greedy',
                               muted=name=='muted') for name in ('trained','scripted','muted')}
        if options.suite in ('dodge','pursuit'):
            reports['jumping_disabled']=evaluate(pool,args,weights,[dict(case,jumping=False) for case in cases])
            reports['jump_effect']=adapter.compare_jumping(reports['trained'],reports['jumping_disabled'])
        reports['suite']=options.suite
        reports['communication_effect']=adapter.compare(reports['trained'],reports['muted'])
        reports['versus_scripted']=adapter.compare(reports['trained'],reports['scripted'])
        reports['checkpoint_sha256']=checkpoint_hash
        output=options.out or options.run/'reevaluation.json'
        output.write_text(json.dumps(reports,indent=2))
        print(output)
    finally:
        pool.close()


if __name__=='__main__':
    main()
