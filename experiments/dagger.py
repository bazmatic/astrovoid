"""Teacher-corrected rounds: the student flies, the rules pilot labels the states it reaches."""
import argparse
import os
import numpy as np
from experiments import run
from experiments.harness import run_episode
from experiments.shadow import ShadowTeacher
from hunter.neural.controls import to_action
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE

DAGGER_DIR = run.RESULTS_DIR.parent / 'neural'


class DaggerLabeller:
    def __init__(self, params, decision_frames, beta=0.0, seed=0):
        self.params, self.decision_frames, self.beta = params, decision_frames, beta
        self.rng = np.random.default_rng(seed)
        self.teacher = None
        self.senses, self.labels = [], []
        self._pending = None

    def before_frame(self, game, hunter, frame):
        controller = game.hunter_controller
        if self.teacher is None:
            self.teacher = ShadowTeacher(self.params, hunter.settings)
            self._spy_on_the_senses(game)
        self.teacher.decide(game, hunter, frame / 60.0, frame)
        self._pending = None
        if controller.frames % self.decision_frames == 0:
            self._pending = self.teacher.label(game, hunter, self.decision_frames)
            if self.beta > 0 and self.rng.random() < self.beta:
                controller.override = to_action(self._pending)

    def _spy_on_the_senses(self, game):
        """Record the senses the controller builds for this step, paired with the teacher's label."""
        original = game._neural_senses

        def spy(last_controls, now):
            sense = original(last_controls, now)
            if self._pending is not None:
                self.senses.append(sense)
                self.labels.append(self._pending)
                self._pending = None
            return sense
        game._neural_senses = spy

    def arrays(self):
        n = len(self.labels)
        return (np.asarray(self.senses, dtype=np.float32).reshape(n, SENSE_SIZE),
                np.asarray(self.labels, dtype=np.int8).reshape(n, 3))


def fly_and_label(level, seed, student, params=RULES, horizon=90.0, beta=0.0, on_result=None):
    labeller = DaggerLabeller(params, student.decision_frames, beta, seed)
    run_episode(level, seed, params, horizon, student=student, labeller=labeller, on_result=on_result)
    return labeller.arrays()


def _label_job(job):
    level, seed, spec, horizon, beta, path = job
    senses, labels = fly_and_label(level, seed, spec, RULES, horizon, beta)
    np.savez(path + '.tmp.npz', senses=senses, labels=labels)
    os.replace(path + '.tmp.npz', path)
    return path


def main(argv=None):
    from experiments.student import StudentSpec
    from experiments.teach import _parse_seeds
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', required=True)
    parser.add_argument('--out')
    parser.add_argument('--round', type=int, default=1)
    parser.add_argument('--beta', type=float, default=0.0)
    parser.add_argument('--seeds', default='200-239')
    parser.add_argument('--levels', default='tune', help="'tune', 'heldout' or a comma list of level numbers")
    parser.add_argument('--turn-rate', type=float, default=1.0)
    parser.add_argument('--decision-frames', type=int, default=6)
    parser.add_argument('--horizon', type=float, default=90.0)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    out = args.out or str(DAGGER_DIR / f'round{args.round}')
    levels = (run.LEVEL_SETS[args.levels] if args.levels in run.LEVEL_SETS
              else tuple(int(x) for x in args.levels.split(',')))
    spec = StudentSpec(weights=args.weights, decision_frames=args.decision_frames, turn_rate=args.turn_rate)
    os.makedirs(out, exist_ok=True)
    jobs = []
    for level in levels:
        for seed in _parse_seeds(args.seeds):
            path = os.path.join(out, f'level{level}-seed{seed}.npz')
            if not os.path.exists(path):
                jobs.append((level, seed, spec, args.horizon, args.beta, path))
    if args.workers <= 1:
        for job in jobs:
            _label_job(job)
    else:
        import multiprocessing
        with multiprocessing.get_context('spawn').Pool(args.workers, initializer=run._use_dummy_drivers) as pool:
            pool.map(_label_job, jobs, chunksize=1)
    print(f'{len(jobs)} episodes labelled to {out}')


if __name__ == '__main__':
    main()
