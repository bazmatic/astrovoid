"""Package a Flocker checkpoint only after its paired deployment evaluation passes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def promote(run, output, accept_without_gate=False):
    from learning.adapters.flocker import load_policy
    from learning.adapters.flocker_replay import open_environment
    run,output = Path(run),Path(output)
    report = json.loads((run/'evaluation.json').read_text())
    if report.get('deployment',{}).get('passed') is not True and not accept_without_gate:
        raise ValueError('Flocker checkpoint has not passed the deployment gate')
    source = run/'best.npz'
    if hashlib.sha256(source.read_bytes()).hexdigest() != report.get('checkpoint_sha256'):
        raise ValueError('best.npz differs from the evaluated checkpoint')
    manifest = json.loads((run/'config.json').read_text())['manifest']
    import enemy_kinds
    if manifest['creature']['tuning']['size'] != enemy_kinds.kind('flocker').tuning['size']:
        raise ValueError('checkpoint was evaluated at a different Flocker body size; reevaluate before packaging')
    env = open_environment(run,manifest)
    env.close()
    load_policy(source)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp = output.with_name(output.name+'.tmp')
    try:
        shutil.copyfile(source,temp)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'assets/neural/flocker.npz')
    parser.add_argument('--accept-without-gate',action='store_true',
                        help='ship a checkpoint whose deployment gate failed; the evaluated checkpoint hash is still enforced')
    args = parser.parse_args()
    print(promote(args.run,args.out,args.accept_without_gate))


if __name__=='__main__':
    main()
