import pytest
from experiments import run
from experiments.harness import run_episode
from experiments.student import StudentSpec, load_policy
from hunter.neural.policy import random_policy


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / 'p.npz'
    random_policy(0).save(path)
    return StudentSpec(weights=str(path), decision_frames=6, turn_rate=1.0)


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def test_a_student_episode_runs_and_is_scored_like_any_other(spec):
    result = run_episode(13, 0, horizon=5.0, student=spec)
    assert result.end in ('cleared', 'horizon') and result.elapsed > 0
    assert min(result.kills, result.wall_hits, result.hits_taken) >= 0


def test_the_same_student_episode_twice_is_identical(spec):
    assert run_episode(14, 0, horizon=8.0, student=spec) == run_episode(14, 0, horizon=8.0, student=spec)


def test_the_student_flies_with_the_specs_turn_rate_and_plain_controls(spec, monkeypatch):
    from entities.hunter_ship import HunterShip
    seen = []
    original = HunterShip.step

    def spy(self, dt, action, solution=None):
        seen.append((self.current_rotation_speed, action))
        return original(self, dt, action, solution)
    monkeypatch.setattr(HunterShip, 'step', spy)
    run_episode(13, 0, horizon=2.0, student=spec)
    assert seen
    assert all(rate == pytest.approx(HunterShipRate.base * 1.0) for rate, _ in seen)
    assert all(not (a.track or a.course or a.worked_burn) for _, a in seen)


class HunterShipRate:
    base = 5.0


def test_a_different_turn_rate_changes_the_episode(spec, tmp_path):
    fast = StudentSpec(weights=spec.weights, decision_frames=6, turn_rate=3.0)
    a = run_episode(14, 0, horizon=15.0, student=spec)
    b = run_episode(14, 0, horizon=15.0, student=fast)
    assert (a.kills, a.wall_hits, a.hits_taken, round(a.idle_seconds, 2)) != \
           (b.kills, b.wall_hits, b.hits_taken, round(b.idle_seconds, 2))


def test_evaluate_passes_the_student_to_each_episode(monkeypatch, spec):
    seen = []

    def fake_episode(level, seed, params, horizon, hide_player=True, student=None):
        seen.append(student)
        from experiments.harness import EpisodeResult
        return EpisodeResult(level, seed, 5, 10.0, 1, 0, 0, 0.0, 'horizon', 0)
    monkeypatch.setattr(run, '_episode', fake_episode)
    run.evaluate(run.DEFAULT, 'heldout', seeds=(0,), workers=1, student=spec)
    assert seen and all(s == spec for s in seen)
    seen.clear()
    run.evaluate(run.DEFAULT, 'heldout', seeds=(0,), workers=1)
    assert all(s is None for s in seen)


def test_the_policy_is_loaded_once_per_process(spec):
    assert load_policy(spec) is load_policy(spec)


def test_the_rules_episode_stays_the_rules_pilot_whatever_the_game_setting(monkeypatch):
    from config import SETTINGS
    from hunter.controller import HunterController
    seen = []
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    run_episode(13, 0, horizon=1.0, trace=lambda t, game, hunter: seen.append(game.hunter_controller))
    assert seen and all(isinstance(c, HunterController) for c in seen)


def test_a_missing_weights_file_is_an_error_in_the_lab(tmp_path):
    with pytest.raises(ValueError, match='weights'):
        run_episode(13, 0, horizon=1.0, student=StudentSpec(weights=str(tmp_path / 'absent.npz')))
