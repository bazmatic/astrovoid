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


from utils.window_size import fit_window_size


def test_a_window_too_big_for_the_desktop_shrinks_to_fit_keeping_its_shape():
    width, height = fit_window_size((3840, 2160), (1512, 982))
    assert width <= 1512 * 0.95 and height <= 982 * 0.9                  # room for the menu bar and Dock
    assert abs(width / height - 3840 / 2160) < 0.01
    assert width >= 1300                                                  # as big as fits, not timidly small


def test_a_window_that_fits_is_left_alone():
    assert fit_window_size((1280, 720), (2560, 1440)) == (1280, 720)


def test_without_a_known_desktop_the_window_is_left_alone():
    assert fit_window_size((3840, 2160), None) == (3840, 2160)
