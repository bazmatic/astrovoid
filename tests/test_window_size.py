import pytest
from utils.window_size import parse_window_size


@pytest.mark.parametrize('text,expected', [
    ('1352x878', (1352, 878)), ('1352X878', (1352, 878)), (' 800 x 600 ', (800, 600))])
def test_parses_width_and_height(text, expected):
    assert parse_window_size(text) == expected


@pytest.mark.parametrize('text', [None, '', 'big', '1352', '1352x', 'x878', '0x600', '-5x600',
                                  '1352x878x2', 'axb'])
def test_anything_else_means_no_override(text):
    assert parse_window_size(text) is None
