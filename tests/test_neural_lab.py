import pytest
from experiments import neural_lab
from experiments.harness import EpisodeResult


def results(kill_share, walls, hits, n=6, minutes=1.0):
    elapsed = 60.0 * minutes
    return [EpisodeResult(13, i, 10, elapsed, int(10 * kill_share), int(walls), int(hits), 0.0, 'horizon', 0)
            for i in range(n)]


def test_a_student_close_to_the_rules_pilot_passes():
    report = neural_lab.gate_report(results(1.0, 2, 2), results(0.9, 2, 2))
    assert report['passed'] and report['score_ok'] and report['wall_ok'] and report['hit_ok']
    assert 0.8 <= report['score_ratio'] <= 1.0


def test_a_student_that_scores_too_low_fails():
    report = neural_lab.gate_report(results(1.0, 2, 2), results(0.3, 2, 2))
    assert not report['score_ok'] and not report['passed']


def test_a_student_that_collides_too_much_fails_even_if_it_scores_well():
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 8, 4))
    assert not report['wall_ok'] and not report['passed']
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 4, 8))
    assert not report['hit_ok'] and not report['passed']


def test_exactly_at_the_limits_passes():
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 5, 5))
    assert report['wall_ok'] and report['hit_ok']


def test_a_rules_pilot_with_no_collisions_does_not_divide_by_zero():
    report = neural_lab.gate_report(results(1.0, 0, 0), results(1.0, 0, 0))
    assert report['wall_ok'] and report['hit_ok']
    assert not neural_lab.gate_report(results(1.0, 0, 0), results(1.0, 3, 0))['wall_ok']


def test_a_non_positive_rules_score_cannot_pass_the_ratio():
    report = neural_lab.gate_report(results(0.0, 0, 0), results(1.0, 0, 0))
    assert not report['score_ok'] and 'not positive' in neural_lab.format_gate(report)


def test_the_text_report_names_every_term_and_the_verdict():
    text = neural_lab.format_gate(neural_lab.gate_report(results(1.0, 2, 2), results(0.9, 2, 2)))
    for word in ('score', 'wall', 'enemy', 'kill', 'PASSED'):
        assert word in text
    assert 'FAILED' in neural_lab.format_gate(neural_lab.gate_report(results(1.0, 2, 2), results(0.1, 2, 2)))


def test_the_gate_command_flies_both_pilots_on_the_same_episodes(monkeypatch, tmp_path):
    calls = []

    def fake_evaluate(params, level_set, seeds, horizon, workers, hide_player=True, student=None):
        calls.append((level_set, tuple(seeds), student))
        return results(1.0 if student is None else 0.95, 2, 2, n=3)
    monkeypatch.setattr(neural_lab.run, 'evaluate', fake_evaluate)
    path = tmp_path / 'w.npz'
    path.write_bytes(b'x')
    neural_lab.main(['gate', '--weights', str(path), '--seeds', '3', '--workers', '1'])
    assert [c[0] for c in calls] == ['heldout', 'heldout'] and calls[0][1] == calls[1][1] == (0, 1, 2)
    assert calls[0][2] is None and calls[1][2].weights == str(path)
