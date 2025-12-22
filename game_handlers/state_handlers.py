"""State-specific event handlers to eliminate duplication.

This module provides state handlers that unify keyboard and controller
input handling, eliminating code duplication in the main game loop.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import pygame
import time
import config
if TYPE_CHECKING:
    from game import Game


class StateHandler(ABC):
    """Base class for state-specific event handlers."""
    
    @abstractmethod
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard event for this state.
        
        Args:
            event: The pygame keyboard event.
            game: The game instance.
            
        Returns:
            True if event was handled, False otherwise.
        """
        pass
    
    @abstractmethod
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller button event for this state.
        
        Args:
            event: The pygame controller button event.
            game: The game instance.
            
        Returns:
            True if event was handled, False otherwise.
        """
        pass


class MenuStateHandler(StateHandler):
    """Handler for menu state events."""
    
    def __init__(self):
        """Initialize menu state handler with navigation debounce."""
        self.last_navigation_time = 0.0
        self.navigation_debounce_interval = 0.15  # 150ms between navigations
    
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events in menu state."""
        if event.key == pygame.K_UP:
            game.main_menu.navigate_up()
            return True
        elif event.key == pygame.K_DOWN:
            game.main_menu.navigate_down()
            return True
        elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
            selected_option = game.main_menu.get_selected_option()
            if selected_option == "START GAME":
                game.state = config.STATE_PLAYING
                game.level = game.initial_start_level if game.initial_start_level else 1
                game.start_level()
            elif selected_option == "OPTIONS":
                # Placeholder - do nothing yet
                pass
            elif selected_option == "QUIT":
                game.running = False
            return True
        elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            game.running = False
            return True
        return False
    
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events in menu state."""
        if event.type == pygame.JOYBUTTONDOWN:
            if game.input_handler.is_controller_menu_confirm_pressed(event.button):
                selected_option = game.main_menu.get_selected_option()
                if selected_option == "START GAME":
                    game.state = config.STATE_PLAYING
                    game.level = game.initial_start_level if game.initial_start_level else 1
                    game.start_level()
                elif selected_option == "OPTIONS":
                    # Placeholder - do nothing yet
                    pass
                elif selected_option == "QUIT":
                    game.running = False
                return True
            elif game.input_handler.is_controller_menu_cancel_pressed(event.button):
                game.running = False
                return True
        elif event.type == pygame.JOYHATMOTION:
            # Handle d-pad navigation
            hat_value = event.value
            # hat_value is a tuple (x, y) where -1 = left/up, 0 = center, 1 = right/down
            current_time = time.time()
            if current_time - self.last_navigation_time >= self.navigation_debounce_interval:
                if hat_value[1] == -1:  # D-pad up
                    game.main_menu.navigate_up()
                    self.last_navigation_time = current_time
                    return True
                elif hat_value[1] == 1:  # D-pad down
                    game.main_menu.navigate_down()
                    self.last_navigation_time = current_time
                    return True
        elif event.type == pygame.JOYAXISMOTION:
            # Handle analog stick navigation (with debounce to prevent rapid navigation)
            current_time = time.time()
            if current_time - self.last_navigation_time >= self.navigation_debounce_interval:
                if event.axis == 1:  # Left stick Y-axis
                    if event.value < -config.CONTROLLER_DEADZONE:
                        game.main_menu.navigate_up()
                        self.last_navigation_time = current_time
                        return True
                    elif event.value > config.CONTROLLER_DEADZONE:
                        game.main_menu.navigate_down()
                        self.last_navigation_time = current_time
                        return True
                elif event.axis == 3:  # Right stick Y-axis
                    if event.value < -config.CONTROLLER_DEADZONE:
                        game.main_menu.navigate_up()
                        self.last_navigation_time = current_time
                        return True
                    elif event.value > config.CONTROLLER_DEADZONE:
                        game.main_menu.navigate_down()
                        self.last_navigation_time = current_time
                        return True
        return False


class PlayingStateHandler(StateHandler):
    """Handler for playing state events."""
    
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events in playing state."""
        if event.key == pygame.K_ESCAPE:
            game.state = config.STATE_QUIT_CONFIRM
            return True
        return False
    
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events in playing state."""
        if game.input_handler.is_controller_quit_pressed(event.button):
            game.state = config.STATE_QUIT_CONFIRM
            return True
        return False


class QuitConfirmStateHandler(StateHandler):
    """Handler for quit confirmation state events."""
    
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events in quit confirm state."""
        if event.key == pygame.K_y or event.key == pygame.K_RETURN:
            game.state = config.STATE_MENU
            game.level = 1
            from scoring.system import ScoringSystem
            game.scoring = ScoringSystem()
            return True
        elif event.key == pygame.K_q:
            game.running = False
            return True
        elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
            game.state = config.STATE_PLAYING
            return True
        return False
    
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events in quit confirm state."""
        if game.input_handler.is_controller_menu_confirm_pressed(event.button):
            # A button: Confirm quit, go to menu
            game.state = config.STATE_MENU
            game.level = 1
            from scoring.system import ScoringSystem
            game.scoring = ScoringSystem()
            return True
        elif game.input_handler.is_controller_menu_cancel_pressed(event.button):
            # B button: Cancel quit, back to playing
            game.state = config.STATE_PLAYING
            return True
        return False


class LevelCompleteStateHandler(StateHandler):
    """Handler for level complete state events."""
    
    def __init__(self):
        """Initialize level complete state handler with navigation debounce."""
        self.last_navigation_time = 0.0
        self.navigation_debounce_interval = 0.15  # 150ms between navigations
    
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events in level complete state."""
        if game.level_complete_quit_confirm:
            return self._handle_quit_confirm_keyboard(event, game)
        else:
            return self._handle_normal_keyboard(event, game)
    
    def _handle_quit_confirm_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events when quit confirmation is active."""
        if event.key == pygame.K_y or event.key == pygame.K_RETURN:
            game.state = config.STATE_MENU
            game.level_complete_quit_confirm = False
            return True
        elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
            game.level_complete_quit_confirm = False
            return True
        return False
    
    def _handle_normal_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle keyboard events in normal level complete state."""
        if event.key == pygame.K_UP:
            game.level_complete_menu.navigate_up()
            return True
        elif event.key == pygame.K_DOWN:
            game.level_complete_menu.navigate_down()
            return True
        elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
            selected_option = game.level_complete_menu.get_selected_option()
            if selected_option == "CONTINUE":
                game.level += 1
                game.state = config.STATE_PLAYING
                game.start_level()
            elif selected_option == "RETRY LEVEL":
                game.scoring.total_score = game.total_score_before_level
                game.state = config.STATE_PLAYING
                game.start_level()
            elif selected_option == "MAIN MENU":
                game.state = config.STATE_MENU
                game.level = 1
                from scoring.system import ScoringSystem
                game.scoring = ScoringSystem()
            return True
        elif event.key == pygame.K_r:
            # R key still works for quick retry
            game.scoring.total_score = game.total_score_before_level
            game.state = config.STATE_PLAYING
            game.start_level()
            return True
        elif event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            # ESC/Q still shows quit confirmation (for backwards compatibility)
            game.level_complete_quit_confirm = True
            return True
        return False
    
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events in level complete state."""
        if game.level_complete_quit_confirm:
            return self._handle_quit_confirm_controller(event, game)
        else:
            return self._handle_normal_controller(event, game)
    
    def _handle_quit_confirm_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events when quit confirmation is active."""
        if game.input_handler.is_controller_menu_confirm_pressed(event.button):
            game.state = config.STATE_MENU
            game.level_complete_quit_confirm = False
            return True
        elif game.input_handler.is_controller_menu_cancel_pressed(event.button):
            game.level_complete_quit_confirm = False
            return True
        return False
    
    def _handle_normal_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        """Handle controller events in normal level complete state."""
        if event.type == pygame.JOYBUTTONDOWN:
            if game.input_handler.is_controller_menu_confirm_pressed(event.button):
                selected_option = game.level_complete_menu.get_selected_option()
                if selected_option == "CONTINUE":
                    game.level += 1
                    game.state = config.STATE_PLAYING
                    game.start_level()
                elif selected_option == "RETRY LEVEL":
                    game.scoring.total_score = game.total_score_before_level
                    game.state = config.STATE_PLAYING
                    game.start_level()
                elif selected_option == "MAIN MENU":
                    game.state = config.STATE_MENU
                    game.level = 1
                    from scoring.system import ScoringSystem
                    game.scoring = ScoringSystem()
                return True
            elif game.input_handler.is_controller_menu_cancel_pressed(event.button):
                # B button: Show quit confirm (for backwards compatibility)
                game.level_complete_quit_confirm = True
                return True
        elif event.type == pygame.JOYHATMOTION:
            # Handle d-pad navigation
            hat_value = event.value
            current_time = time.time()
            if current_time - self.last_navigation_time >= self.navigation_debounce_interval:
                if hat_value[1] == -1:  # D-pad up
                    game.level_complete_menu.navigate_up()
                    self.last_navigation_time = current_time
                    return True
                elif hat_value[1] == 1:  # D-pad down
                    game.level_complete_menu.navigate_down()
                    self.last_navigation_time = current_time
                    return True
        elif event.type == pygame.JOYAXISMOTION:
            # Handle analog stick navigation (with debounce to prevent rapid navigation)
            current_time = time.time()
            if current_time - self.last_navigation_time >= self.navigation_debounce_interval:
                if event.axis == 1:  # Left stick Y-axis
                    if event.value < -config.CONTROLLER_DEADZONE:
                        game.level_complete_menu.navigate_up()
                        self.last_navigation_time = current_time
                        return True
                    elif event.value > config.CONTROLLER_DEADZONE:
                        game.level_complete_menu.navigate_down()
                        self.last_navigation_time = current_time
                        return True
                elif event.axis == 3:  # Right stick Y-axis
                    if event.value < -config.CONTROLLER_DEADZONE:
                        game.level_complete_menu.navigate_up()
                        self.last_navigation_time = current_time
                        return True
                    elif event.value > config.CONTROLLER_DEADZONE:
                        game.level_complete_menu.navigate_down()
                        self.last_navigation_time = current_time
                        return True
        return False


class StateHandlerRegistry:
    """Registry for state handlers."""
    
    def __init__(self):
        """Initialize registry with all state handlers."""
        self.handlers = {
            config.STATE_MENU: MenuStateHandler(),
            config.STATE_PLAYING: PlayingStateHandler(),
            config.STATE_QUIT_CONFIRM: QuitConfirmStateHandler(),
            config.STATE_LEVEL_COMPLETE: LevelCompleteStateHandler(),
        }
    
    def get_handler(self, state: str) -> StateHandler:
        """Get handler for a state.
        
        Args:
            state: The game state.
            
        Returns:
            The state handler, or a no-op handler if state not found.
        """
        return self.handlers.get(state, _NoOpStateHandler())


class _NoOpStateHandler(StateHandler):
    """No-op handler for unknown states."""
    
    def handle_keyboard(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        return False
    
    def handle_controller(self, event: 'pygame.event.Event', game: 'Game') -> bool:
        return False

