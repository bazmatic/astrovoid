"""learning.run says in evaluation.json whether best.npz was chosen by the task's selection_score or is only the
end-of-run fallback (no checkpoint ever passed), and logs one line when it is the fallback."""
import json
import math

import pytest


def run_jelly(tmp_path, monkeypatch, score):
    from learning import run
    from learning.adapters import jelly_scenario as scenario
    from tools import ppo_neural
    monkeypatch.setattr(scenario, 'selection_score', lambda summary, baseline=None: score)
    monkeypatch.setattr(scenario, '_baselines', {})
    monkeypatch.setattr(scenario, 'run_horizon', scenario.run_horizon)
    out = tmp_path/'run'
    args = ppo_neural.build_parser().parse_args(
        ['--task', 'jelly_team', '--start', '', '--out', str(out), '--horizon', '.1', '--iterations', '1',
         '--episodes', '2', '--workers', '1', '--bootstrap-episodes', '0', '--budget-seconds', '0'])
    run.train(args)
    return json.loads((out/'evaluation.json').read_text()), (out/'train.log').read_text()


def test_a_run_whose_checkpoint_passes_the_gate_says_it_was_selected(tmp_path, monkeypatch, capsys):
    evaluation, log = run_jelly(tmp_path, monkeypatch, 1.)
    assert evaluation['selection_gate_passed'] is True
    assert 'selection_gate_passed=False' not in log


def test_a_run_where_no_checkpoint_passes_flags_best_as_the_fallback(tmp_path, monkeypatch, capsys):
    evaluation, log = run_jelly(tmp_path, monkeypatch, -math.inf)
    assert evaluation['selection_gate_passed'] is False
    assert (tmp_path/'run'/'best.npz').exists()   # the same file is still written
    assert log.count('selection_gate_passed=False') == 1
    assert 'selection_gate_passed=False' in capsys.readouterr().out
