"""Screens that once needed the keyboard can be used with only a controller."""
from types import SimpleNamespace

import pygame

import config
from game_handlers.state_handlers import ProfileSelectionStateHandler
from tests.test_menu_visuals import profile_menu, screen  # noqa: F401 - pytest fixture

BUTTONS = {0: 'a', 1: 'b', 2: 'x', 7: 'start'}


class Pad:
    """Stands in for the game's InputHandler with one standard controller plugged in."""

    def controller_button_name(self, button):
        return BUTTONS.get(button)

    def is_controller_menu_confirm_pressed(self, button):
        return BUTTONS.get(button) in ('a', 'start')

    def is_controller_menu_cancel_pressed(self, button):
        return BUTTONS.get(button) in ('b', 'back')


def press(name):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, button={v: k for k, v in BUTTONS.items()}[name])


def dpad(x, y):
    return pygame.event.Event(pygame.JOYHATMOTION, value=(x, y))


def test_a_profile_can_be_created_and_named_with_only_a_controller(screen, tmp_path):  # noqa: F811
    menu = profile_menu(screen, tmp_path, [])
    game = SimpleNamespace(profile_selection_menu=menu, input_handler=Pad(), state=config.STATE_PROFILE_SELECTION,
                           reset_scoring_to_profile_state=lambda: None)
    handler = ProfileSelectionStateHandler()

    def send(event):
        handler.last_navigation_time = 0.0  # each press is a separate press, not a held one
        handler.handle_controller(event, game)

    for _ in menu.options:
        send(dpad(0, -1))                  # down to the last row
    send(press('a'))                       # create a new profile
    send(dpad(0, 1))                       # A -> B
    send(press('a'))                       # add B
    send(dpad(0, -1))                      # B -> A
    send(dpad(1, 0))                       # add A
    send(press('x'))                       # delete it again
    send(dpad(0, 1))                       # A -> B
    send(dpad(0, 1))                       # B -> C; Start keeps the letter still being chosen
    send(press('start'))

    assert game.state == config.STATE_MENU
    assert menu.profile_manager.get_profile('BC') is not None
