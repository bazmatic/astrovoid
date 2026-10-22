import json
import sys

import pytest

from tools import ppo_neural as ppo
from tools.trainer import control
from tools.trainer.control import TrainerError, pause, resume, start, stop
from tools.trainer.processes import Process

ARGV = ['--iterations', '50', '--levels', '1-30', '--speed-penalty', '3', '--compass-reward', '100']


def args_for(argv):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in vars(ppo.build_parser().parse_args(argv)).items()}


def make_run(root, name, iterations, files=(), config='args'):
    path = root / name
    path.mkdir(parents=True)
    for i in range(iterations):
        (path / f'iter{i:04d}.npz').write_bytes(b'')
    args = args_for(ARGV + ['--start', str(root / 'run0' / 'iter0000.npz'), '--out', str(path)])
    cfg = {'args': args, 'start': args['start'], 'rewards': []} if config == 'args' else \
        {'start': 'x.npz', 'rewards': [], 'shaping': {'speed_penalty': 3.0}}
    (path / 'config.json').write_text(json.dumps(cfg))
    for name_, text in dict(files).items():
        (path / name_).write_text(text)
    return path


class FakeLaunch:
    def __init__(self, inside=None):
        self.commands, self.inside = [], inside

    def __call__(self, command, log_path):
        self.commands.append(command)
        if self.inside:
            self.inside()
        return 4242


def trainer(pid, out):
    return Process(pid, 1, f'python -m tools.ppo_neural --start x --out {out}')


@pytest.fixture
def root(tmp_path):
    make_run(tmp_path, 'run51', 2)
    make_run(tmp_path, 'run52', 3)
    return tmp_path


def test_start_carries_on_from_the_newest_runs_last_checkpoint(root):
    fake = FakeLaunch()
    started = start(root=root, processes=[], launch=fake)
    assert started.run == 'run53' and started.started_from == 'run52/iter0002' and started.changes == []
    command = fake.commands[0]
    assert command[:3] == [sys.executable, '-m', 'tools.ppo_neural']
    assert command[3:7] == ['--start', str(root / 'run52' / 'iter0002.npz'), '--out', str(root / 'run53')]
    assert command[command.index('--iterations') + 1] == '50'


def test_start_from_an_older_run_and_checkpoint_with_changes(root):
    fake = FakeLaunch()
    started = start('run51/iter0000', {'speed_penalty': '2'}, root=root, processes=[], launch=fake)
    assert started.started_from == 'run51/iter0000' and started.changes == [('speed_penalty', 3.0, 2.0)]
    command = fake.commands[0]
    assert command[4] == str(root / 'run51' / 'iter0000.npz')
    assert command[command.index('--speed-penalty') + 1] == '2.0'
    assert start('run51', root=root, processes=[], launch=fake).started_from == 'run51/iter0001'


@pytest.mark.parametrize('files,processes', [
    ({}, 'training'), ({'state.json': '{"state": "paused", "iteration": 2}', 'resume.pt': ''}, None),
    ({'resume.pt': ''}, None)])
def test_start_refuses_while_a_run_is_training_or_paused(root, files, processes):
    for name, text in files.items():
        (root / 'run52' / name).write_text(text)
    procs = [trainer(9, root / 'run52')] if processes else []
    fake = FakeLaunch()
    with pytest.raises(TrainerError, match='run52'):
        start(root=root, processes=procs, launch=fake)
    assert fake.commands == []


def test_start_refuses_a_run_without_checkpoints_and_unknown_runs(root):
    (root / 'run53').mkdir()
    fake = FakeLaunch()
    with pytest.raises(TrainerError, match='run53 has no checkpoints'):
        start('run53', root=root, processes=[], launch=fake)
    with pytest.raises(TrainerError, match='run99'):
        start('run99', root=root, processes=[], launch=fake)
    with pytest.raises(TrainerError, match='iter0009'):
        start('run51/iter0009', root=root, processes=[], launch=fake)
    assert fake.commands == []
    assert start(root=root, processes=[], launch=fake).run == 'run54'      # carries on from run52, skips run53


def test_bad_settings_launch_nothing(root):
    fake = FakeLaunch()
    with pytest.raises(TrainerError, match='speed_penalty'):
        start(changes={'speed_penalty': 'fast'}, root=root, processes=[], launch=fake)
    with pytest.raises(TrainerError, match='unknown setting'):
        start(changes={'warp': '9'}, root=root, processes=[], launch=fake)
    assert fake.commands == [] and not (root / 'run53').exists()


def test_two_starts_at_once_launch_one_run(root):
    errors = []

    def second_start():
        try:
            start(root=root, processes=[], launch=FakeLaunch())
        except TrainerError as e:
            errors.append(str(e))

    fake = FakeLaunch(inside=second_start)
    start(root=root, processes=[], launch=fake)
    assert len(fake.commands) == 1 and errors and 'starting' in errors[0]
    assert not (root / '.trainer.lock').exists()


def test_pause_asks_the_training_run_to_pause(root):
    assert pause(root=root, processes=[trainer(9, root / 'run52')]) == 'run52'
    assert (root / 'run52' / 'PAUSE').exists()
    with pytest.raises(TrainerError, match='nothing is training'):
        pause(root=root, processes=[])


def test_pause_refuses_a_run_started_before_pausing_existed(root):
    make_run(root, 'run53', 1, config='old')
    with pytest.raises(TrainerError, match='before pausing existed'):
        pause(root=root, processes=[trainer(9, root / 'run53')])
    assert not (root / 'run53' / 'PAUSE').exists()


def test_stop_ends_the_training_run_and_marks_it_stopped(root):
    (root / 'run52' / 'train.log').write_text('iteration=0 update_s=1\niteration=1 update_s=1\n')
    (root / 'run52' / 'PAUSE').write_text('')
    ended = []
    procs = [trainer(9, root / 'run52')]
    assert stop(root=root, processes=procs, terminate=lambda pid, processes: ended.append(pid)) == 'run52'
    assert ended == [9]
    assert json.loads((root / 'run52' / 'state.json').read_text()) == {'state': 'stopped', 'iteration': 1}
    assert not (root / 'run52' / 'PAUSE').exists()


def test_stop_marks_a_paused_run_stopped_without_signalling(root):
    (root / 'run52' / 'resume.pt').write_text('')
    (root / 'run52' / 'state.json').write_text('{"state": "paused", "iteration": 2}')
    assert stop(root=root, processes=[], terminate=lambda *a: pytest.fail('signalled')) == 'run52'
    assert json.loads((root / 'run52' / 'state.json').read_text())['state'] == 'stopped'
    with pytest.raises(TrainerError, match='nothing is training'):
        stop(root=root, processes=[], terminate=lambda *a: None)


def test_resume_relaunches_the_paused_run_with_resume(root):
    (root / 'run52' / 'resume.pt').write_text('')
    (root / 'run52' / 'state.json').write_text('{"state": "paused", "iteration": 2}')
    fake = FakeLaunch()
    assert resume(root=root, processes=[], launch=fake) == 'run52'
    command = fake.commands[0]
    assert command[3:7] == ['--start', str(root / 'run0' / 'iter0000.npz'), '--out', str(root / 'run52')]
    assert command[-1] == '--resume' and '--speed-penalty' in command


def test_resume_clears_a_stale_pause_on_an_interrupted_run(root):
    (root / 'run51' / 'resume.pt').write_text('')
    (root / 'run51' / 'PAUSE').write_text('')
    fake = FakeLaunch()
    assert resume('run51', root=root, processes=[], launch=fake) == 'run51'
    assert not (root / 'run51' / 'PAUSE').exists()


def test_resume_refuses_runs_that_cannot_resume(root):
    fake = FakeLaunch()
    with pytest.raises(TrainerError, match='nothing to resume'):
        resume(root=root, processes=[], launch=fake)
    with pytest.raises(TrainerError, match='run51 is stopped'):
        resume('run51', root=root, processes=[], launch=fake)
    (root / 'run52' / 'resume.pt').write_text('')
    with pytest.raises(TrainerError, match='training'):
        resume('run52', root=root, processes=[trainer(9, root / 'run52')], launch=fake)
    assert fake.commands == []


def test_the_default_launcher_writes_to_the_run_log(tmp_path, monkeypatch):
    seen = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            seen.update(kwargs, command=command)
            self.pid = 77

    monkeypatch.setattr(control.subprocess, 'Popen', FakePopen)
    assert control.launch_process(['x'], tmp_path / 'run9.log') == 77
    assert seen['start_new_session'] and seen['stdout'].name == str(tmp_path / 'run9.log')
