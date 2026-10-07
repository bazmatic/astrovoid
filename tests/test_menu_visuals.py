"""The profile, level complete and quit screens share the main menu's look and never overlap themselves."""
import pygame
import pytest

import config
from profiles import ProfileManager
from rendering import menu_components
from rendering.level_complete_menu import LevelCompleteMenu
from rendering.menu_components import ConfirmationDialog
from rendering.profile_selection_menu import ProfileSelectionMenu
from rendering.ui_elements import AnimatedStarRating

SIZE = (1352, 878)


@pytest.fixture
def screen(monkeypatch):
    pygame.init()
    pygame.display.set_mode((320, 240))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', SIZE[0])
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', SIZE[1])
    surface = pygame.Surface(SIZE, pygame.SRCALPHA)
    surface.fill((*config.COLOR_BACKGROUND, 255))
    return surface


def is_opaque(surface):
    return pygame.mask.from_surface(surface, 254).count() == surface.get_width() * surface.get_height()


def profile_menu(screen, tmp_path, names):
    manager = ProfileManager(tmp_path / "profiles.json")
    for name in names:
        if manager.get_profile(name) is None:
            manager.create_profile(name)
    return ProfileSelectionMenu(screen, manager)


class TestSharedPieces:
    def test_backdrop_is_opaque_and_tinted(self, screen):
        backdrop = menu_components.build_menu_backdrop(*SIZE)
        assert backdrop.get_size() == SIZE
        screen.blit(backdrop, (0, 0))
        assert is_opaque(screen)
        # The nebula lifts the middle of the screen above the flat background colour
        assert sum(backdrop.get_at((SIZE[0] // 2, int(SIZE[1] * 0.42)))[:3]) > sum(config.COLOR_BACKGROUND) + 20

    def test_hint_row_pairs_each_key_with_its_action(self, screen):
        font = pygame.font.Font(None, 24)
        one = menu_components.render_hint_row(font, [("ENTER", "Select")])
        two = menu_components.render_hint_row(font, [("ENTER", "Select"), ("ESC / B", "Back")])
        assert two.get_width() > one.get_width()
        assert two.get_height() == one.get_height()

    def test_panel_has_rounded_corners(self, screen):
        panel = menu_components.build_panel((400, 200))
        assert panel.get_size() == (400, 200)
        assert panel.get_at((0, 0))[3] == 0
        assert panel.get_at((399, 199))[3] == 0
        assert panel.get_at((200, 0))[3] > 200
        assert panel.get_at((200, 100))[3] > 200


class TestProfileSelection:
    def test_every_option_has_a_row_on_screen(self, screen, tmp_path):
        menu = profile_menu(screen, tmp_path, ["Ada", "Grace"])
        rows = [menu.row_rect(i) for i in range(len(menu.options))]
        assert all(row is not None for row in rows)
        assert all(screen.get_rect().contains(row) for row in rows)
        assert all(a.bottom <= b.top for a, b in zip(rows, rows[1:]))

    def test_long_lists_scroll_to_keep_the_selection_visible(self, screen, tmp_path):
        menu = profile_menu(screen, tmp_path, [f"Pilot {i}" for i in range(30)])
        hints_top = menu.hints_rect().top
        for index in range(len(menu.options)):
            menu.selected_index = index
            row = menu.row_rect(index)
            assert row is not None
            assert row.top >= menu.title_rect().bottom
            assert row.bottom <= hints_top
        menu.selected_index = 0
        assert menu.row_rect(len(menu.options) - 1) is None

    def test_selected_row_stands_out(self, screen, tmp_path):
        menu = profile_menu(screen, tmp_path, ["Ada", "Grace"])
        menu.selected_index = 1
        menu.draw()
        selected, idle = menu.row_rect(1), menu.row_rect(0)

        def border_brightness(rect):
            # The selected skin is drawn slightly larger, so look either side of the edge
            return max(sum(screen.get_at((rect.centerx, rect.top + dy))[:3]) for dy in range(-5, 5))

        assert border_brightness(selected) > border_brightness(idle) + 100

    def test_draws_in_every_state_and_leaves_the_screen_opaque(self, screen, tmp_path):
        menu = profile_menu(screen, tmp_path, ["Ada"])
        menu.draw()
        menu.start_creating_profile()
        for char in "Katherine":
            menu.append_character(char)
        menu.update(1.0)
        menu.draw()
        menu.cancel_creating_profile()
        menu.draw()
        assert is_opaque(screen)

    def test_name_being_typed_is_shown_in_the_create_row(self, screen, tmp_path):
        menu = profile_menu(screen, tmp_path, ["Ada"])
        menu.selected_index = len(menu.options) - 1
        menu.start_creating_profile()
        menu.draw()
        empty = screen.copy()
        for char in "WWWWWWWW":
            menu.append_character(char)
        menu.draw()
        row = menu.row_rect(menu.selected_index)
        changed = [
            (x, y) for x in range(row.left, row.right) for y in range(row.top, row.bottom)
            if screen.get_at((x, y)) != empty.get_at((x, y))
        ]
        assert len(changed) > 200


class TestLevelComplete:
    @pytest.mark.parametrize('succeeded', [True, False])
    def test_nothing_overlaps(self, screen, succeeded):
        menu = LevelCompleteMenu(screen)
        layout = menu.layout(succeeded)
        order = ['title', 'level_number', 'stars', 'stats', 'buttons', 'hints']
        rects = [layout[name] for name in order if name in layout]
        assert len(rects) >= 5
        for above, below in zip(rects, rects[1:]):
            assert above.bottom <= below.top
        assert all(screen.get_rect().contains(rect) for rect in rects)

    def test_time_is_no_longer_printed_over_the_banner(self, screen):
        menu = LevelCompleteMenu(screen)
        layout = menu.layout(True)
        assert not layout['stats'].colliderect(layout['title'])

    def test_stars_are_moved_into_their_slot(self, screen):
        menu = LevelCompleteMenu(screen)
        stars = AnimatedStarRating(0.5, 0, 0)
        menu.draw(3, True, 42.3, {'final_score': 55, 'total_score': 1234}, stars, False, lambda: None)
        slot = menu.layout(True)['stars']
        assert stars.y == slot.centery
        assert stars.x + 2 * stars.star_spacing == slot.centerx

    @pytest.mark.parametrize('succeeded', [True, False])
    def test_draws_and_leaves_the_screen_opaque(self, screen, succeeded):
        menu = LevelCompleteMenu(screen)
        stars = AnimatedStarRating(0.5, 0, 0) if succeeded else None
        menu.update(1.0)
        menu.draw(3, succeeded, 42.3, {'final_score': 55, 'total_score': 1234}, stars, False, lambda: None)
        assert is_opaque(screen)


class TestStarRating:
    def test_unearned_stars_show_as_empty_outlines(self, screen):
        stars = AnimatedStarRating(0.3, 200, 200, star_size=40)
        assert stars.num_stars == 1
        stars.draw(screen)
        last = pygame.Rect(0, 0, 40, 40)
        last.center = (200 + 4 * stars.star_spacing, 200)
        outline = pygame.mask.from_threshold(
            screen.subsurface(last), (*config.COLOR_BACKGROUND, 255), (12, 12, 12, 255)
        )
        outline.invert()
        assert 20 < outline.count() < 40 * 40 * 0.5


class TestConfirmationDialog:
    SIZES = {'side_by_side': (560, 290), 'stacked': (620, 370)}

    def make(self, screen, layout):
        width, height = self.SIZES[layout]
        return ConfirmationDialog(
            screen, "QUIT LEVEL?", "Progress will be lost.",
            dialog_width=width, dialog_height=height, button_layout=layout
        )

    @pytest.mark.parametrize('layout', ['side_by_side', 'stacked'])
    def test_dialog_is_a_rounded_panel(self, screen, layout):
        dialog = self.make(screen, layout)
        dialog.draw(0.0, 0)
        rect = dialog.dialog_rect()
        border = sum(screen.get_at((rect.centerx, rect.top + 1))[:3])
        # The corner is cut away, so only the soft glow behind the panel shows there
        assert sum(screen.get_at(rect.topleft)[:3]) < border * 0.5
        assert sum(screen.get_at((rect.right - 1, rect.bottom - 1))[:3]) < border * 0.5
        assert is_opaque(screen)

    @pytest.mark.parametrize('layout', ['side_by_side', 'stacked'])
    def test_buttons_and_hints_fit_inside_without_overlapping(self, screen, layout):
        dialog = self.make(screen, layout)
        dialog.draw(0.0, 1)
        rect = dialog.dialog_rect()
        confirm, cancel = dialog.button_rects()
        hints = dialog.hints_rect()
        assert rect.contains(confirm) and rect.contains(cancel) and rect.contains(hints)
        assert not confirm.colliderect(cancel)
        assert max(confirm.bottom, cancel.bottom) <= hints.top


class TestControlsScreen:
    def make_game(self):
        from unittest.mock import Mock
        from game_handlers.state_handlers import StateHandlerRegistry
        from rendering.main_menu import MainMenu
        game = Mock()
        game.state = config.STATE_MENU
        game.main_menu = MainMenu(pygame.Surface(SIZE))
        return game, StateHandlerRegistry()

    def key(self, key):
        return pygame.event.Event(pygame.KEYDOWN, key=key, unicode="")

    def test_main_menu_no_longer_carries_the_key_mappings(self, screen):
        game, _ = self.make_game()
        assert game.main_menu.menu_options == ["START GAME", "LEVELS", "SELECT PROFILE", "CONTROLS", "QUIT"]
        assert not hasattr(game.main_menu, 'controls_surface')

    def test_controls_option_opens_the_screen_and_escape_returns(self, screen):
        game, registry = self.make_game()
        game.main_menu.menu_selected_index = game.main_menu.menu_options.index("CONTROLS")
        registry.get_handler(game.state).handle_keyboard(self.key(pygame.K_RETURN), game)
        assert game.state == config.STATE_CONTROLS
        registry.get_handler(game.state).handle_keyboard(self.key(pygame.K_ESCAPE), game)
        assert game.state == config.STATE_MENU

    def test_one_panel_per_device_side_by_side(self, screen):
        from rendering.controls_menu import CONTROL_GROUPS, ControlsMenu
        menu = ControlsMenu(screen)
        layout = menu.layout()
        panels = layout['panels']
        assert len(panels) == len(CONTROL_GROUPS) == 2
        assert panels[0].right < panels[1].left
        assert layout['title'].bottom <= panels[0].top
        assert max(panel.bottom for panel in panels) <= layout['hints'].top
        assert all(screen.get_rect().contains(panel) for panel in panels)

    def test_every_mapping_fits_inside_its_panel(self, screen):
        from rendering.controls_menu import CONTROL_GROUPS, ControlsMenu
        menu = ControlsMenu(screen)
        pad = menu._scaled(36)
        for rect, (_, mappings) in zip(menu.layout()['panels'], CONTROL_GROUPS):
            for key_text, action_text in mappings:
                needed = menu.row_font.size(key_text)[0] + menu.row_font.size(action_text)[0] + menu._scaled(28) + 40
                assert needed <= rect.width - pad * 2

    def test_draws_and_leaves_the_screen_opaque(self, screen):
        from rendering.controls_menu import ControlsMenu
        menu = ControlsMenu(screen)
        menu.update(1.0)
        menu.draw()
        assert is_opaque(screen)
