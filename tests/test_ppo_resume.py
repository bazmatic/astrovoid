import json

import numpy as np
import pytest

pytest.importorskip('torch')

from hunter.neural.policy import NeuralPolicy, random_policy
from tests.test_ppo_loop import fake_rollout_factory
from tools import ppo_neural as ppo


def quiet(*_):
    pass


@pytest.fixture
def start(tmp_path):
    path = tmp_path / 'start.npz'
    random_policy(0, hidden=16, embed=8).save(path)
    return path


def train(start, out, iterations, log=quiet, resume=False):
    return ppo.train_rl(start, out, iterations=iterations, episodes=6, workers=1,
                        rollout=fake_rollout_factory(), log=log, resume=resume)


def state(out):
    return json.loads((out / 'state.json').read_text())


def test_a_paused_and_resumed_run_matches_an_uninterrupted_one(tmp_path, start):
    whole = train(start, tmp_path / 'whole', 4)
    split = tmp_path / 'split'
    split.mkdir()

    def pause_after_iteration_one(line):
        if 'iteration=1 ' in line + ' ':
            (split / 'PAUSE').touch()

    first = train(start, split, 4, log=pause_after_iteration_one)
    assert first['paused'] and len(first['history']) == 2
    assert state(split) == {'state': 'paused', 'iteration': 1}
    assert not (split / 'PAUSE').exists()

    second = train(start, split, 4, resume=True)
    assert not second['paused']
    assert [h['iteration'] for h in second['history']] == [2, 3]
    assert state(split) == {'state': 'finished', 'iteration': 3}
    for name, a in NeuralPolicy.load(whole['last']).params.items():
        np.testing.assert_allclose(a, NeuralPolicy.load(second['last']).params[name], rtol=1e-5, atol=1e-6)
    assert len((split / 'train.log').read_text().splitlines()) == 4


def test_a_finished_run_says_so_and_keeps_its_resume_state(tmp_path, start):
    result = train(start, tmp_path / 'out', 2)
    assert not result['paused']
    assert state(tmp_path / 'out') == {'state': 'finished', 'iteration': 1}
    assert (tmp_path / 'out' / 'resume.pt').exists()


def test_the_run_config_records_every_argument(tmp_path):
    ppo.write_run_config(ppo.build_parser().parse_args(
        ['--out', str(tmp_path), '--iterations', '7', '--levels', '1-3', '--speed-penalty', '2']))
    config = json.loads((tmp_path / 'config.json').read_text())
    args = config['args']
    assert args['iterations'] == 7 and args['levels'] == [1, 2, 3] and args['speed_penalty'] == 2.0
    assert args['panic_score'] is None and 'workers' in args and 'rewards' in config


def test_resume_without_resume_state_refuses(tmp_path, start):
    with pytest.raises(FileNotFoundError):
        train(start, tmp_path / 'empty', 2, resume=True)


def test_a_pause_on_the_last_iteration_finishes_the_run(tmp_path, start):
    out = tmp_path / 'out'
    out.mkdir()

    def pause_on_the_last(line):                # iteration 1 is the last of 2
        if 'iteration=1 ' in line + ' ':
            (out / 'PAUSE').touch()

    result = train(start, out, 2, log=pause_on_the_last)
    assert not result['paused'] and state(out) == {'state': 'finished', 'iteration': 1}
    assert not (out / 'PAUSE').exists()


def test_resuming_a_run_with_nothing_left_marks_it_finished(tmp_path, start):
    out = tmp_path / 'out'
    train(start, out, 2)
    (out / 'state.json').unlink()
    result = train(start, out, 2, resume=True)
    assert result['history'] == [] and state(out) == {'state': 'finished', 'iteration': 1}


def test_a_resumed_run_starts_its_log_on_a_new_line_after_a_crash_mid_write(tmp_path, start):
    out = tmp_path / 'out'
    out.mkdir()

    def pause_at_once(line):
        (out / 'PAUSE').touch()

    train(start, out, 3, log=pause_at_once)
    with open(out / 'train.log', 'a') as log:
        log.write('policy_loss=0.1 iteration=1 kl=0.2 upd')            # killed while writing
    train(start, out, 3, resume=True)
    lines = (out / 'train.log').read_text().splitlines()
    assert lines[1] == 'policy_loss=0.1 iteration=1 kl=0.2 upd' and 'iteration=1 ' in lines[2] + ' '
