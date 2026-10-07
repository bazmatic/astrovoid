"""Completion comparisons use stored precision and signed gaps."""
from profiles import LevelBest, LevelResult
from rendering.level_complete_menu import comparison_lines


def test_first_clear_only_marks_time():
    result = LevelResult(True, True, True, 5, None)
    assert comparison_lines(result, 86, 41.2) == ('FIRST CLEAR', '')


def test_records_and_gaps():
    previous = LevelBest(86, 41.2, 4)
    assert comparison_lines(LevelResult(False, True, True, 1, previous), 90, 40.8) == ('NEW BEST', 'NEW BEST')
    assert comparison_lines(LevelResult(False, False, False, 0, previous), 74, 41.6) == ('BEST 00:41.2  +0.4s', 'BEST 86  -12')
    assert comparison_lines(LevelResult(False, False, False, 0, previous), 86, 41.2) == ('BEST 00:41.2  +0.0s', 'BEST 86  +0')
    assert comparison_lines(None, 0, 0) == ('', '')
