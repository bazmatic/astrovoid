"""Level grid shows progress and scrolls without selecting locked levels."""
import pygame
import pytest
import config
from profiles import ProfileManager
from rendering.level_select_menu import LevelSelectMenu


@pytest.fixture
def menu(tmp_path, monkeypatch):
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    manager = ProfileManager(tmp_path / 'profiles.json')
    manager.update_active_profile_progress(16, 800)
    manager.record_level_result(1, 86, 41.2, 5)
    manager.record_level_result(4, 45, 67.0, 3)
    return LevelSelectMenu(screen, manager)


def test_grid_shows_unlocked_and_one_locked_with_best_stars(menu):
    assert menu.selected_level == 17 and menu.can_play_selected
    assert menu.star_total == (8, 85)
    tiles = menu.layout()['tiles']
    assert [tile['level'] for tile in tiles] == list(range(1, 19))
    assert tiles[0]['stars'] == 5 and tiles[3]['stars'] == 3
    assert tiles[-2]['stars'] == 0 and tiles[-1]['locked']
    menu.selected_level = 18
    assert not menu.can_play_selected
    menu.refresh()
    assert menu.selected_level == 17


def test_navigation_clamps_and_scrolls(menu):
    menu.profile_manager.update_active_profile_progress(199, 800)
    menu.refresh()
    assert menu.selected_level == 200
    last = menu.layout()
    assert last['first_row'] > 0
    assert any(t['level'] == 200 for t in last['tiles'])
    for _ in range(50):
        menu.navigate(0, -1)
    for _ in range(20):
        menu.navigate(-1, 0)
    assert menu.selected_level == 1
    assert menu.layout()['first_row'] == 0
    menu.navigate(0, -1)
    menu.navigate(-1, 0)
    assert menu.selected_level == 1
    for _ in range(50):
        menu.navigate(0, 1)
    for _ in range(20):
        menu.navigate(1, 0)
    assert menu.selected_level == 200 and menu.can_play_selected
    layout = menu.layout()
    assert all(menu.screen.get_rect().contains(t['rect']) for t in layout['tiles'])
    assert max(t['rect'].bottom for t in layout['tiles']) < layout['details'].top
    menu.update(1)
    menu.draw()
    assert pygame.mask.from_surface(menu.screen, 254).count() == 1352 * 878
