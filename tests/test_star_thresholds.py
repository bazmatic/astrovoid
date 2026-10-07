"""Stars require reaching a score threshold rather than rounding upward."""
import pytest
from rendering.ui_elements import AnimatedStarRating, StarIndicator


@pytest.mark.parametrize('percentage,expected', [
    (-0.1, 0), (0.0, 0), (0.1999, 0), (0.20, 1),
    (0.3999, 1), (0.40, 2), (0.5999, 2), (0.60, 3),
    (0.7999, 3), (0.80, 4), (0.9499, 4), (0.95, 5),
    (1.0, 5), (1.5, 5),
])
def test_awards_require_reaching_each_threshold(percentage, expected):
    assert StarIndicator.calculate_star_count(percentage) == expected
    assert AnimatedStarRating(percentage, 0, 0).num_stars == expected


def test_live_star_feedback_uses_the_same_stricter_cutoffs():
    changes = []
    indicator = StarIndicator(on_star_lost=lambda: changes.append('lost'),
                              on_star_gained=lambda: changes.append('gained'))
    indicator.update(0.96)
    indicator.update(0.94)
    assert indicator.star_count == 4 and changes == ['lost']
    indicator.update(0.95)
    assert indicator.star_count == 5 and changes == ['lost', 'gained']
