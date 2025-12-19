"""Game state machine implementation.

This module provides the base state class and state machine for managing
game state transitions and delegating state-specific logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


class GameState(ABC):
    """Abstract base class for game states.
    
    Each game state (menu, playing, level complete, etc.) implements
    this interface to handle its own logic, rendering, and event handling.
    This follows the Single Responsibility Principle by separating
    state-specific logic from the main Game class.
    """
    
    def __init__(self, state_machine: 'StateMachine'):
        """Initialize state with reference to state machine.
        
        Args:
            state_machine: The state machine managing state transitions.
        """
        self.state_machine = state_machine
    
    @abstractmethod
    def enter(self) -> None:
        """Called when entering this state."""
        pass
    
    @abstractmethod
    def exit(self) -> None:
        """Called when exiting this state."""
        pass
    
    @abstractmethod
    def update(self, dt: float) -> None:
        """Update state logic.
        
        Args:
            dt: Delta time since last update.
        """
        pass
    
    @abstractmethod
    def draw(self, screen: 'pygame.Surface') -> None:
        """Draw state visuals.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        pass
    
    @abstractmethod
    def handle_event(self, event: 'pygame.event.Event') -> None:
        """Handle pygame events.
        
        Args:
            event: The pygame event to handle.
        """
        pass


class StateMachine:
    """Manages game state transitions and delegation.
    
    The state machine holds the current state and delegates operations
    to it, allowing for clean separation of concerns.
    """
    
    def __init__(self, initial_state: GameState):
        """Initialize state machine with initial state.
        
        Args:
            initial_state: The initial game state.
        """
        self.current_state: Optional[GameState] = None
        self.change_state(initial_state)
    
    def change_state(self, new_state: GameState) -> None:
        """Change to a new state.
        
        Args:
            new_state: The state to transition to.
        """
        if self.current_state:
            self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()
    
    def update(self, dt: float) -> None:
        """Update current state.
        
        Args:
            dt: Delta time since last update.
        """
        if self.current_state:
            self.current_state.update(dt)
    
    def draw(self, screen: 'pygame.Surface') -> None:
        """Draw current state.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        if self.current_state:
            self.current_state.draw(screen)
    
    def handle_event(self, event: 'pygame.event.Event') -> None:
        """Handle event in current state.
        
        Args:
            event: The pygame event to handle.
        """
        if self.current_state:
            self.current_state.handle_event(event)

