"""Render a profile selection UI for choosing or creating profiles."""

from __future__ import annotations

import pygame
from typing import List, Optional

import config
from profiles import Profile, ProfileManager
from rendering.menu_components import AnimatedBackground


class ProfileSelectionMenu:
    """Menu that lists existing profiles and lets players add new ones."""

    CREATE_OPTION = "CREATE NEW PROFILE"
    MAX_NAME_LENGTH = 18

    def __init__(self, screen: pygame.Surface, profile_manager: ProfileManager):
        self.screen = screen
        self.profile_manager = profile_manager
        self.menu_background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.title_font = pygame.font.Font(None, config.FONT_SIZE_TITLE)
        self.entry_font = pygame.font.Font(None, config.FONT_SIZE_BUTTON)
        self.prompt_font = pygame.font.Font(None, config.FONT_SIZE_HINT)
        self.menu_pulse_phase = 0.0
        self.profile_entries: List[Profile] = []
        self.options: List[str] = []
        self.selected_index = 0
        self.creating_profile = False
        self.new_profile_name = ""
        self.feedback_message: Optional[str] = None
        self.refresh_profiles()

    def refresh_profiles(self) -> None:
        """Reload the profile list from the manager."""
        self.profile_entries = self.profile_manager.get_profiles()
        names = [profile.name for profile in self.profile_entries]
        self.options = names + [self.CREATE_OPTION]
        active_profile = self.profile_manager.get_active_profile()
        if active_profile and active_profile.name in names:
            self.selected_index = names.index(active_profile.name)
        elif self.selected_index >= len(self.options):
            self.selected_index = max(0, len(self.options) - 1)

    def navigate_up(self) -> None:
        """Move selection cursor up."""
        if self.selected_index > 0:
            self.selected_index -= 1

    def navigate_down(self) -> None:
        """Move selection cursor down."""
        if self.selected_index < len(self.options) - 1:
            self.selected_index += 1

    def get_selected_option(self) -> Optional[str]:
        """Return the text of the currently selected option."""
        if not self.options:
            return None
        return self.options[self.selected_index]

    def start_creating_profile(self) -> None:
        """Begin the create-profile flow."""
        self.creating_profile = True
        self.new_profile_name = ""
        self.feedback_message = "Type a name for your new profile (Enter to save)"

    def cancel_creating_profile(self) -> None:
        """Abort creating a profile."""
        self.creating_profile = False
        self.new_profile_name = ""
        self.feedback_message = "Profile creation cancelled."

    def append_character(self, char: str) -> None:
        """Add a character to the active profile name."""
        if len(self.new_profile_name) >= self.MAX_NAME_LENGTH:
            return
        if not char.isprintable() or char in {"\r", "\n"}:
            return
        self.new_profile_name += char

    def backspace_character(self) -> None:
        """Remove the last character from the input."""
        self.new_profile_name = self.new_profile_name[:-1]

    def submit_new_profile(self) -> Optional[Profile]:
        """Attempt to create a new profile using the current input."""
        cleaned = self.new_profile_name.strip()
        if not cleaned:
            self.feedback_message = "Profile name cannot be empty."
            return None
        try:
            profile = self.profile_manager.create_profile(cleaned)
        except ValueError as exc:
            self.feedback_message = str(exc)
            return None

        self.creating_profile = False
        self.new_profile_name = ""
        self.feedback_message = f"Created profile '{profile.name}'."
        self.refresh_profiles()
        self.selected_index = self.options.index(profile.name)
        return profile

    def draw(self) -> None:
        """Draw the profile selection UI."""
        self.menu_background.draw(self.screen)

        title = self.title_font.render("PROFILE SELECTION", True, config.COLOR_TEXT)
        title_rect = title.get_rect(center=(config.SCREEN_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)

        list_start_y = 200
        list_spacing = 70

        active_name = self.profile_manager.get_active_profile().name if self.profile_manager.get_active_profile() else None

        for index, option in enumerate(self.options):
            y = list_start_y + index * list_spacing
            is_selected = index == self.selected_index
            bg_rect = pygame.Rect(
                config.SCREEN_WIDTH // 2 - 320,
                y - 25,
                640,
                60
            )
            if is_selected:
                pygame.draw.rect(self.screen, (40, 60, 90), bg_rect)
                pygame.draw.rect(self.screen, config.COLOR_BUTTON_GLOW, bg_rect, 2)
            else:
                pygame.draw.rect(self.screen, (25, 25, 35), bg_rect)
                pygame.draw.rect(self.screen, (60, 60, 70), bg_rect, 2)

            display_text = option
            if option != self.CREATE_OPTION:
                profile = self.profile_entries[index]
                suffix = " (Active)" if profile.name == active_name else ""
                display_text = (
                    f"{profile.name} | Level {profile.level} | Score {profile.total_score}{suffix}"
                )
            text_surface = self.entry_font.render(display_text, True, config.COLOR_TEXT)
            text_rect = text_surface.get_rect(center=(config.SCREEN_WIDTH // 2, y))
            self.screen.blit(text_surface, text_rect)

        prompt_y = config.SCREEN_HEIGHT - 120
        if self.creating_profile:
            prompt_text = self.prompt_font.render(
                f"New Name: {self.new_profile_name or '_'}",
                True,
                config.COLOR_TEXT
            )
        else:
            prompt_text = self.prompt_font.render(
                "Use Arrow Keys / Controller to move | Enter to select | ESC/B to go back",
                True,
                (180, 180, 180)
            )
        prompt_rect = prompt_text.get_rect(center=(config.SCREEN_WIDTH // 2, prompt_y))
        self.screen.blit(prompt_text, prompt_rect)

        if self.feedback_message:
            feedback_surface = self.prompt_font.render(
                self.feedback_message,
                True,
                (150, 255, 200)
            )
            feedback_rect = feedback_surface.get_rect(
                center=(config.SCREEN_WIDTH // 2, prompt_y + 30)
            )
            self.screen.blit(feedback_surface, feedback_rect)

    def update(self, dt: float) -> None:
        """Update menu animations."""
        self.menu_background.update(dt)
        self.menu_pulse_phase += config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0
        if self.menu_pulse_phase >= 2 * 3.14159:
            self.menu_pulse_phase -= 2 * 3.14159

