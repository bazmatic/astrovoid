"""Live star feedback during play."""
import pytest
from rendering.ui_elements import StarIndicator


def test_live_star_feedback_uses_the_same_stricter_cutoffs():
    changes = []
    indicator = StarIndicator(on_star_lost=lambda: changes.append('lost'),
                              on_star_gained=lambda: changes.append('gained'))
    indicator.update(0.96)
    indicator.update(0.94)
    assert indicator.star_count == 4 and changes == ['lost']
    indicator.update(0.95)
    assert indicator.star_count == 5 and changes == ['lost', 'gained']
