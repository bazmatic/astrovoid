import json
import pytest
from experiments import run
from experiments.harness import EpisodeResult
from hunter.rule_params import DEFAULT, RuleParams


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def test_level_sets_are_disjoint_and_complete():
    assert set(run.TUNE_LEVELS).isdisjoint(run.HELDOUT_LEVELS)
    assert len(run.TUNE_LEVELS) == 12 and len(run.HELDOUT_LEVELS) == 6
    for boss in (18, 30):
        assert boss in run.TUNE_LEVELS
    assert 24 in run.HELDOUT_LEVELS
    assert run.SEEDS == (0, 1, 2, 3, 4, 5)


def test_episode_list_is_levels_times_seeds_in_a_fixed_order():
    episodes = run.episode_list('heldout')
    assert len(episodes) == 36
    assert episodes[:6] == [(16, seed) for seed in range(6)] and episodes[6] == (21, 0)
    assert run.episode_list('tune', seeds=(0,))[:2] == [(13, 0), (14, 0)]
    with pytest.raises(KeyError):
        run.episode_list('everything')


def test_evaluate_runs_each_episode_in_order(monkeypatch):
    calls = []

    def fake_episode(level, seed, params, horizon, hide_player=True, student=None):
        calls.append((level, seed, horizon))
        return EpisodeResult(level, seed, 5, 10.0, 1, 0, 0, 0.0, 'horizon')
    monkeypatch.setattr(run, '_episode', fake_episode)
    results = run.evaluate(DEFAULT, 'heldout', seeds=(0,), horizon=7.0, workers=1)
    assert [(r.level, r.seed) for r in results] == [(16, 0), (21, 0), (23, 0), (28, 0), (29, 0), (24, 0)]
    assert all(h == 7.0 for _, _, h in calls)


def test_a_failing_episode_names_itself(monkeypatch):
    def boom(level, seed, params, horizon, hide_player=True, student=None):
        if level == 21:
            raise RuntimeError('kaboom')
        return EpisodeResult(level, seed, 5, 10.0, 1, 0, 0, 0.0, 'horizon')
    monkeypatch.setattr(run, '_episode', boom)
    with pytest.raises(run.EpisodeError) as info:
        run.evaluate(RuleParams(pulse_frames=9.0), 'heldout', seeds=(0,), workers=1)
    message = str(info.value)
    assert 'level 21' in message and 'seed 0' in message and 'pulse_frames' in message
    assert 'kaboom' in message


def test_results_round_trip_and_are_written_atomically(tmp_path):
    results = [EpisodeResult(13, 0, 5, 10.0, 1, 2, 3, 0.5, 'horizon'),
               EpisodeResult(14, 1, 6, 4.0, 6, 0, 1, 0.0, 'horizon')]
    path = tmp_path / 'r.jsonl'
    run.save_results(results, path)
    assert run.load_results(path) == results
    assert not list(tmp_path.glob('*.tmp'))


def test_an_interrupted_save_leaves_no_half_written_file(tmp_path, monkeypatch):
    path = tmp_path / 'r.jsonl'
    results = [EpisodeResult(13, 0, 5, 10.0, 1, 2, 3, 0.5, 'horizon')]
    monkeypatch.setattr(run.os, 'replace', lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run.save_results(results, path)
    assert not path.exists()


def test_a_partial_params_file_is_applied_on_top_of_the_rules_defaults(tmp_path):
    from hunter.rule_params import RULES
    partial = tmp_path / 'partial.json'
    partial.write_text(json.dumps({'pulse_frames': 5}))
    params = run.load_params(partial)
    assert params.pulse_frames == 5.0
    assert params.investigate_memory is RULES.investigate_memory is True


def test_load_params_reads_a_json_file_and_rejects_bad_ones(tmp_path):
    good = tmp_path / 'p.json'
    good.write_text(json.dumps({'steer_band_degrees': 25}))
    assert run.load_params(good).steer_band_degrees == 25.0
    from hunter.rule_params import RULES
    assert run.load_params(None) == RULES
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'nope': 1}))
    with pytest.raises(ValueError):
        run.load_params(bad)
    notobject = tmp_path / 'list.json'
    notobject.write_text('[1, 2]')
    with pytest.raises(ValueError, match='object'):
        run.load_params(notobject)


def test_main_prints_a_summary_and_writes_results(monkeypatch, tmp_path, capsys):
    def fake_episode(level, seed, params, horizon, hide_player=True, student=None):
        return EpisodeResult(level, seed, 5, 10.0, 2, 1, 0, 0.0, 'horizon')
    monkeypatch.setattr(run, '_episode', fake_episode)
    out = tmp_path / 'out.jsonl'
    run.main(['--set', 'heldout', '--seeds', '1', '--workers', '1', '--out', str(out)])
    text = capsys.readouterr().out
    assert 'kill_pct_per_min' in text and 'score' in text and str(out) in text
    assert len(run.load_results(out)) == 6


def test_a_real_parallel_evaluation_matches_a_serial_one():
    serial = run.evaluate(DEFAULT, 'heldout', seeds=(0,), horizon=2.0, workers=1)
    parallel = run.evaluate(DEFAULT, 'heldout', seeds=(0,), horizon=2.0, workers=2)
    assert serial == parallel


def test_evaluate_passes_the_player_scenario_to_each_episode(monkeypatch):
    seen = []

    def fake_episode(level, seed, params, horizon, hide_player=True, student=None):
        seen.append(hide_player)
        return EpisodeResult(level, seed, 5, 10.0, 1, 0, 0, 0.0, 'horizon', 0)
    monkeypatch.setattr(run, '_episode', fake_episode)
    run.evaluate(DEFAULT, 'heldout', seeds=(0,), workers=1)
    assert seen and all(seen)
    seen.clear()
    run.evaluate(DEFAULT, 'heldout', seeds=(0,), workers=1, hide_player=False)
    assert seen and not any(seen)
