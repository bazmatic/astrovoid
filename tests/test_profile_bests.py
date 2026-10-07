"""Per-level records are independent, durable, and isolated by profile."""
import json

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
    path.write_text(json.dumps({'profiles': entries, 'active_profile': 'Old'}))
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 17 and manager.get_active_total_score() == 8141
    assert manager.get_profile('Broken').bests == {}
    assert list(manager.get_profile('Mixed').bests) == [4]
