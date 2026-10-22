import json

import pytest

from tools import ppo_neural as ppo
from tools.trainer.settings import SETTINGS, Value, apply_changes, changed, read_settings, to_argv


def args_for(argv):
    args = vars(ppo.build_parser().parse_args(argv))
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in args.items()}


NEW_ARGV = ['--iterations', '1000', '--levels', '1-30', '--speed-penalty', '3', '--compass-reward', '100',
            '--health', '10', '--panic-score', '-50', '--boredom-window', '12', '--rules-share', '0.05']


def make_run(root, name, config):
    path = root / name
    path.mkdir(parents=True)
    if config is not None:
        (path / 'config.json').write_text(json.dumps(config))
    return path


def new_run(root, name='run52', argv=NEW_ARGV):
    return make_run(root, name, {'rewards': [], 'args': args_for(argv)})


SHAPING_51 = {'wall_scale': 1.0, 'hit_scale': 1.0, 'still_penalty': 0.0, 'horizon': 60.0, 'random_start': True,
              'still_speed': 0.15, 'turn_change_penalty': 0.0, 'reversal_penalty': 0.5, 'health': 10,
              'death_penalty': 200.0, 'speed_penalty': 3.0, 'powerup_reward': 15.0, 'after_clear': 60.0,
              'upgrade_bonus': 1.0, 'pursue_hunter': True, 'rules_bounty': 50.0, 'compass_reward': 100.0,
              'boredom_penalty': 20.0, 'boredom_window': 10.0, 'shot_price': 1.0, 'turning_penalty': 1.0,
              'hit_reward': 3.0, 'panic_score': -50.0, 'panic_temperature': 3.0}
EPISODE = {'horizon_seconds': 60.0, 'after_clear_seconds': 60.0, 'episodes_per_iteration': 96,
           'learning_rate': 0.0001, 'health': 10, 'wall_energy': 4.0, 'rules_share': 0.05, 'levels': [1, 2, 3]}


def test_a_run_with_args_is_read_exactly(tmp_path):
    run = new_run(tmp_path)
    s = read_settings(run, [run])
    assert all(v.source == 'recorded' for v in s.values())
    assert s['speed_penalty'] == Value(3.0, 'recorded') and s['levels'].value == list(range(1, 31))
    assert s['iterations'] == Value(1000, 'recorded') and s['panic_score'].value == -50.0


def test_run51_style_shaping_is_recorded_and_episode_fills_the_rest(tmp_path):
    run = make_run(tmp_path, 'run51', {'rewards': [], 'episode': EPISODE, 'shaping': SHAPING_51})
    s = read_settings(run, [run])
    assert s['speed_penalty'] == Value(3.0, 'recorded') and s['fixed_start'] == Value(False, 'recorded')
    assert s['decoy_player'] == Value(False, 'recorded')
    assert s['episodes'] == Value(96, 'recovered') and s['lr'] == Value(0.0001, 'recovered')
    assert s['levels'] == Value([1, 2, 3], 'recovered')


def test_an_old_run_recovers_rewards_and_guesses_the_rest_from_the_newest(tmp_path):
    rewards = [{'name': 'Kills', 'sign': '+', 'value': 100.0, 'unit': ''},
               {'name': 'Powerup collected', 'sign': '+', 'value': 15.0, 'unit': ''},
               {'name': 'Wall impact', 'sign': '-', 'value': 10.0, 'unit': ''}]
    old = make_run(tmp_path, 'run40', {'rewards': rewards, 'episode': EPISODE})
    newest = new_run(tmp_path)
    s = read_settings(old, [old, newest])
    assert s['powerup_reward'] == Value(15.0, 'recovered')
    assert s['compass_reward'] == Value(0.0, 'recovered')          # no row: it was 0
    from experiments.score import Weights
    assert s['wall_scale'].source == 'recovered' and s['wall_scale'].value == pytest.approx(10.0 / Weights().quotient)
    assert s['boredom_window'] == Value(12.0, 'guessed')
    assert s['iterations'] == Value(1000, 'guessed')


def test_a_run_with_no_config_takes_everything_from_the_newest(tmp_path):
    old = make_run(tmp_path, 'run3', None)
    newest = new_run(tmp_path)
    s = read_settings(old, [old, newest])
    assert all(v.source == 'guessed' for v in s.values())
    assert s['compass_reward'].value == 100.0


def test_a_guess_can_come_from_what_a_newer_run_recovered(tmp_path):
    old = make_run(tmp_path, 'run3', None)
    newer = make_run(tmp_path, 'run40', {'rewards': [], 'episode': EPISODE})
    assert read_settings(old, [old, newer])['levels'] == Value([1, 2, 3], 'guessed')


def test_the_iteration_total_falls_back_to_1000_when_no_run_recorded_it(tmp_path):
    old = make_run(tmp_path, 'run40', {'rewards': [], 'episode': EPISODE})
    assert read_settings(old, [old])['iterations'] == Value(1000, 'guessed')


def test_changes_accept_dest_or_flag_names_and_report_what_changed(tmp_path):
    run = new_run(tmp_path)
    base = read_settings(run, [run])
    new = apply_changes(base, {'speed-penalty': '2', '--levels': '1-5'})
    assert changed(base, new) == [('levels', list(range(1, 31)), [1, 2, 3, 4, 5]), ('speed_penalty', 3.0, 2.0)]
    assert new['speed_penalty'] == Value(2.0, 'recorded')
    assert apply_changes(base, {'health': 12, 'fixed_start': True})['fixed_start'].value is True


@pytest.mark.parametrize('bad', [{'speed_penalty': 'fast'}, {'levels': '1-x'}, {'no_such': '1'},
                                 {'health': '2.5'}, {'fixed_start': 'maybe'}, {'levels': ''}])
def test_bad_names_and_values_are_refused(tmp_path, bad):
    run = new_run(tmp_path)
    with pytest.raises(ValueError):
        apply_changes(read_settings(run, [run]), bad)


def test_guessed_values_are_not_counted_as_changes(tmp_path):
    old = make_run(tmp_path, 'run3', None)
    newest = new_run(tmp_path)
    base = read_settings(old, [old, newest])
    assert changed(base, apply_changes(base, {})) == []


def test_the_command_line_round_trips_through_the_trainer_parser(tmp_path):
    run = new_run(tmp_path)
    values = apply_changes(read_settings(run, [run]), {'fixed_start': True, 'panic_score': 'none'})
    parsed = vars(ppo.build_parser().parse_args(to_argv(values)))
    for dest, v in values.items():
        expected = tuple(v.value) if dest == 'levels' and v.value else v.value
        assert parsed[dest] == expected, dest


def test_every_parser_flag_is_a_setting():
    assert {s.dest for s in SETTINGS} == {a.dest for a in ppo.build_parser()._actions} - {'start', 'out', 'resume', 'help'}
    assert {s.group for s in SETTINGS} <= {'Rewards', 'Episodes', 'Training'}
