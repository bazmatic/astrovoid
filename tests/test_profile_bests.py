"""Per-level records are independent, durable, and isolated by profile."""
import json

import pytest

from profiles import ProfileManager


def test_first_clear_and_independent_records(tmp_path):
    manager = ProfileManager(tmp_path / 'profiles.json')
    result = manager.record_level_result(4, 86.9, 41.24, 5)
    assert result.first_clear and result.previous_best is None
    assert result.new_best_score and result.new_best_time and result.stars_gained == 5
    best = manager.get_active_profile().bests[4]
    assert (best.score, best.time, best.stars) == (86, 41.2, 5)
    result = manager.record_level_result(4, 90, 44.0, 4)
    assert result.new_best_score and not result.new_best_time
    assert result.previous_best.score == 86 and result.stars_gained == 0
    result = manager.record_level_result(4, 75, 40.0, 3)
    assert result.new_best_time and not result.new_best_score
    result = manager.record_level_result(4, 50, 45.0, 1)
    assert not result.first_clear and not result.new_best_score and not result.new_best_time
    best = manager.get_active_profile().bests[4]
    assert (best.score, best.time, best.stars) == (90, 40.0, 5)


def test_bests_round_trip_and_belong_to_each_profile(tmp_path):
    path = tmp_path / 'profiles.json'
    manager = ProfileManager(path)
    manager.record_level_result(4, 86, 41.2, 5)
    manager.create_profile('Ada')
    assert manager.get_active_profile().bests == {}
    manager.record_level_result(4, 60, 55.3, 3)
    loaded = ProfileManager(path)
    assert loaded.get_active_profile().bests[4].score == 60
    loaded.set_active_profile('Player1')
    assert loaded.get_active_profile().bests[4].score == 86
    assert json.loads(path.read_text())['profiles'][0]['bests']['4']['time'] == 41.2


def test_old_profiles_and_malformed_bests_load(tmp_path):
    path = tmp_path / 'profiles.json'
    entries = [
        {'name': 'Old', 'level': 17, 'total_score': 8141},
        {'name': 'Broken', 'bests': []},
        {'name': 'Mixed', 'bests': {
            '4': {'score': 86, 'time': 41.2, 'stars': 5},
            '5': None, 'six': {'score': 1, 'time': 1, 'stars': 1},
            '7': {'score': 1, 'time': -1, 'stars': 1},
            '8': {'score': 1, 'time': float('nan'), 'stars': 1},
            '9': {'score': 1, 'time': 1, 'stars': 6},
            '10': {'score': 'bad', 'time': 1, 'stars': 1},
        }},
    ]
    path.write_text(json.dumps({'profiles': entries, 'active_profile': 'Old', 'levels_version': 2}))
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 17 and manager.get_active_total_score() == 8141
    assert manager.get_profile('Broken').bests == {}
    assert list(manager.get_profile('Mixed').bests) == [4]


OLD_BEST = {'4': {'score': 83, 'time': 9.0, 'stars': 5}}


def write_profiles(path, **top_level):
    path.write_text(json.dumps({
        'profiles': [{'name': 'Old', 'level': 21, 'total_score': 9039, 'bests': OLD_BEST}],
        'active_profile': 'Old', **top_level}))


def test_bests_from_before_the_levels_changed_are_cleared_but_progress_is_kept(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path)
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 21 and manager.get_active_total_score() == 9039


def test_the_file_is_rewritten_at_once_so_bests_are_cleared_only_once(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path)
    manager = ProfileManager(path)
    saved = json.loads(path.read_text())
    assert saved['levels_version'] == 2
    assert saved['profiles'][0]['bests'] == {}
    manager.record_level_result(4, 50, 12.0, 3)
    assert list(ProfileManager(path).get_active_profile().bests) == [4]


def test_a_current_file_keeps_its_bests(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path, levels_version=2)
    assert list(ProfileManager(path).get_active_profile().bests) == [4]


@pytest.mark.parametrize('version', [None, '2', 1, 2.0, True, [], {}])
def test_a_missing_or_malformed_version_counts_as_old(tmp_path, version):
    path = tmp_path / 'profiles.json'
    write_profiles(path, levels_version=version)
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 21


def test_a_new_profiles_file_is_written_with_the_version(tmp_path):
    path = tmp_path / 'profiles.json'
    ProfileManager(path)
    assert json.loads(path.read_text())['levels_version'] == 2
