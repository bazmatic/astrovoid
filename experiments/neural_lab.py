"""Flies a neural student against the rules pilot and applies the gate: python -m experiments.neural_lab."""
import argparse
import os
from experiments import run
from experiments.score import components, mean_components, paired_bootstrap, score
from experiments.student import StudentSpec
from hunter.rule_params import RULES

SCORE_RATIO_MIN = 0.8
COLLISION_RATIO_MAX = 1.25


def _ratio(student, rules):
    if rules <= 1e-9:
        return 0.0 if student <= 1e-9 else float('inf')
    return student / rules


def gate_report(rules_results, student_results, weights=None):
    rules = mean_components(rules_results, *([weights] if weights else []))
    student = mean_components(student_results, *([weights] if weights else []))
    report = {'rules': rules, 'student': student}
    report['score_ratio'] = student['score'] / rules['score'] if rules['score'] > 0 else float('nan')
    report['wall_ratio'] = _ratio(student['wall_hits_per_min'], rules['wall_hits_per_min'])
    report['hit_ratio'] = _ratio(student['hits_taken_per_min'], rules['hits_taken_per_min'])
    report['rules_score_positive'] = rules['score'] > 0
    report['score_ok'] = report['rules_score_positive'] and report['score_ratio'] >= SCORE_RATIO_MIN
    report['wall_ok'] = report['wall_ratio'] <= COLLISION_RATIO_MAX
    report['hit_ok'] = report['hit_ratio'] <= COLLISION_RATIO_MAX
    report['passed'] = report['score_ok'] and report['wall_ok'] and report['hit_ok']
    return report


def format_gate(report):
    lines = ['term                 rules   student']
    for key in ('kill_pct_per_min', 'kills_per_min', 'wall_hits_per_min', 'hits_taken_per_min',
                'idle_fraction', 'score'):
        lines.append(f'  {key:20s} {report["rules"][key]:8.3f} {report["student"][key]:8.3f}')
    if report['rules_score_positive']:
        lines.append(f'score ratio {report["score_ratio"]:.2f} (needs >= {SCORE_RATIO_MIN}): '
                     f'{"ok" if report["score_ok"] else "short"}')
    else:
        lines.append('score ratio unavailable: the rules pilot score is not positive')
    lines.append(f'wall hits ratio {report["wall_ratio"]:.2f} (needs <= {COLLISION_RATIO_MAX}): '
                 f'{"ok" if report["wall_ok"] else "too many"}')
    lines.append(f'enemy hits ratio {report["hit_ratio"]:.2f} (needs <= {COLLISION_RATIO_MAX}): '
                 f'{"ok" if report["hit_ok"] else "too many"}')
    lines.append('GATE ' + ('PASSED' if report['passed'] else 'FAILED'))
    return '\n'.join(lines)


def _spec(args, weights):
    return StudentSpec(weights=str(weights), decision_frames=args.decision_frames, turn_rate=args.turn_rate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('gate', 'compare'))
    parser.add_argument('--weights')
    parser.add_argument('--weights-a')
    parser.add_argument('--weights-b')
    parser.add_argument('--turn-rate', type=float, default=1.0)
    parser.add_argument('--decision-frames', type=int, default=6)
    parser.add_argument('--seeds', type=int, default=18)
    parser.add_argument('--set', default='heldout', choices=('heldout', 'tune'))
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    seeds = tuple(range(args.seeds))
    if args.command == 'gate':
        rules = run.evaluate(RULES, args.set, seeds, 90.0, args.workers)
        student = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights))
        print(format_gate(gate_report(rules, student)))
        return
    a = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights_a))
    b = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights_b))
    for key in list(components(a[0])) + ['score']:
        va = [score(r) if key == 'score' else components(r)[key] for r in a]
        vb = [score(r) if key == 'score' else components(r)[key] for r in b]
        diff, low, high = paired_bootstrap(va, vb)
        print(f'  {key:20s} {sum(va)/len(va):8.3f} -> {sum(vb)/len(vb):8.3f}  {diff:+8.3f} ({low:+.3f} .. {high:+.3f})')


if __name__ == '__main__':
    main()
