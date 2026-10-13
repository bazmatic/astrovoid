"""Records the rules pilot as teaching data: senses at each decision step, and the controls it executed."""
import argparse
import os
import numpy as np
from experiments import run
from experiments.harness import run_episode
from hunter.neural.controls import step_labels
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE, Senses

TEACH_DIR = run.RESULTS_DIR.parent / 'neural' / 'teach'


class StepRecorder:
    def __init__(self, decision_frames, rate=5.0):
        self.decision_frames, self.rate = decision_frames, rate
        self.senses, self.labels = [], []
        self._frames = []
        self._count = 0
        self._last = (1, 0, 0)
        self._senses_obj = None
        self._game = self._hunter = None

    # --- called by the harness ---
    def begin(self, game, hunter, settings):
        self._game, self._hunter = game, hunter
        self._senses_obj = Senses(settings)
        self.rate = hunter.current_rotation_speed

    def before_frame(self, game, hunter):
        if self._count % self.decision_frames == 0:
            enemies = game._hunter_entities()
            sense = self._senses_obj.observe(
                hunter, game.maze, enemies, game.projectiles,
                [c for c in game.powerup_crystals if type(c).__name__ != 'JevBeacon'],
                game.ship if game._hunter_sees_player() else None, self._last, self._count / 60.0)
            self.senses.append(sense)

    def add_frame(self, rotation, engine, trigger):
        self._frames.append((rotation, engine, trigger))

    def after_frame(self):
        self._count += 1
        if self._count % self.decision_frames == 0:
            self._close_step()

    # --- helpers ---
    def pending_label(self):
        return step_labels(self._frames, self.rate)

    def _close_step(self):
        label = self.pending_label()
        self.labels.append(label)
        self._last = (label[0], 1 if label[1] else 0, 1 if label[2] else 0)
        self._frames = []

    def arrays(self):
        n = min(len(self.senses), len(self.labels))
        senses = np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE)
        labels = np.asarray(self.labels[:n], dtype=np.int8).reshape(n, 3)
        return senses, labels


def record_episode(level, seed, params=RULES, decision_frames=6, turn_rate=1.0, horizon=90.0):
    from dataclasses import replace
    flown = replace(params, turn_rate_multiplier=turn_rate)
    recorder = StepRecorder(decision_frames)
    run_episode(level, seed, flown, horizon, recorder=recorder)
    return recorder.arrays()


def _record_job(job):
    level, seed, decision_frames, turn_rate, horizon, path = job
    senses, labels = record_episode(level, seed, RULES, decision_frames, turn_rate, horizon)
    np.savez(path + '.tmp.npz', senses=senses, labels=labels)
    os.replace(path + '.tmp.npz', path)
    return path


def _parse_seeds(text):
    low, _, high = text.partition('-')
    return range(int(low), int(high or low) + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(TEACH_DIR))
    parser.add_argument('--seeds', default='100-139')
    parser.add_argument('--levels', default='tune', help="'tune', 'heldout' or a comma list of level numbers")
    parser.add_argument('--turn-rate', type=float, default=1.0)
    parser.add_argument('--decision-frames', type=int, default=6)
    parser.add_argument('--horizon', type=float, default=90.0)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    levels = (run.LEVEL_SETS[args.levels] if args.levels in run.LEVEL_SETS
              else tuple(int(x) for x in args.levels.split(',')))
    os.makedirs(args.out, exist_ok=True)
    jobs = []
    for level in levels:
        for seed in _parse_seeds(args.seeds):
            path = os.path.join(args.out, f'level{level}-seed{seed}.npz')
            if not os.path.exists(path):
                jobs.append((level, seed, args.decision_frames, args.turn_rate, args.horizon, path))
    if args.workers <= 1:
        for job in jobs:
            _record_job(job)
    else:
        import multiprocessing
        with multiprocessing.get_context('spawn').Pool(args.workers, initializer=run._use_dummy_drivers) as pool:
            pool.map(_record_job, jobs, chunksize=1)
    print(f'{len(jobs)} episodes recorded to {args.out}')


if __name__ == '__main__':
    main()
