# tests/test_rules_hunter_training.py
import numpy as np
import pytest

import level_config
from experiments import rollout
from experiments.harness import run_episode
from hunter.senses import SENSE_SIZE


@pytest.fixture(autouse=True)
def one_rules_hunter(monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 1 if level == 13 else 0)


def test_in_training_the_rules_hunter_hunts_the_hunter_not_the_parked_player():
    seen = []

    def trace(t, game, hunter):
        seen.append((game.protagonist() is hunter, [e for e in game.rules_hunters[0].surroundings.enemies()]))
    result = run_episode(13, 0, horizon=2.0, pursue_hunter=True, trace=trace)
    assert result.rules_hunters == 1
    assert seen and all(is_hunter for is_hunter, _ in seen)
    assert all(len(foes) == 1 for _, foes in seen)


def test_an_episode_on_another_level_has_no_rules_hunter():
    assert run_episode(14, 0, horizon=2.0, pursue_hunter=True).rules_hunters == 0


def test_destroying_it_marks_the_episode_rules_beaten():
    def kill_it(t, game, hunter):
        if t > 0.5:
            for rules_hunter in game.rules_hunters:
                rules_hunter.die()
    result = run_episode(13, 0, horizon=3.0, pursue_hunter=True, trace=kill_it)
    assert result.rules_beaten and result.rules_hunters == 1


def test_an_episode_it_survives_is_not_rules_beaten():
    result = run_episode(13, 0, horizon=2.0, pursue_hunter=True)
    assert result.rules_hunters == 1 and not result.rules_beaten


def test_the_lab_overrides_do_not_outlive_the_episode():
    run_episode(13, 0, horizon=1.0, pursue_hunter=True)
    from experiments import harness
    game = harness._game
    assert '_rules_worker_factory' not in game.__dict__ and 'protagonist' not in game.__dict__


class _Counter:
    kills = wall_impulse = hits_taken = spawned = powerups = 0
    idle_seconds = 0.0
    died = False
    rules_beaten = False


def _bounty_rewards(beaten_at, bounty, steps=4):
    recorder = rollout.RolloutRecorder(6, rules_bounty=bounty)
    recorder._start_enemies = 1
    for step in range(steps):
        recorder.senses.append(np.zeros(SENSE_SIZE, np.float32))
        recorder.controls.append((1, 0, 0))
        recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
        counter = _Counter()
        counter.rules_beaten = beaten_at is not None and step >= beaten_at
        recorder.counted(counter, step / 10.0)
    return recorder.arrays()[2]


def test_destroying_it_pays_the_bounty_once_in_the_step_it_happens():
    assert _bounty_rewards(2, 50.0).tolist() == pytest.approx([0.0, 0.0, 50.0, 0.0])


def test_no_bounty_without_a_win_and_none_by_default():
    assert not _bounty_rewards(None, 50.0).any()
    assert not _bounty_rewards(2, 0.0).any()


def test_a_rollout_reports_the_arena_and_the_win(monkeypatch, tmp_path):
    from experiments.student import StudentSpec
    from hunter.neural.policy import random_policy
    path = tmp_path / 'w.npz'
    random_policy(0).save(path)
    spec = StudentSpec(weights=str(path), sample_seed=1)
    flown = rollout.fly_rollout(13, 300, spec, horizon=3.0, rules_bounty=50.0)
    assert flown['rules_arena'] is True and flown['rules_beaten'] is False
    other = rollout.fly_rollout(14, 300, spec, horizon=3.0)
    assert other['rules_arena'] is False
