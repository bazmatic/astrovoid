"""Splash screen state implementation.

This module provides the splash screen state that displays the game logo
with fade-in/out animations and auto-advances to the menu.
"""

import pygame
import os
from typing import TYPE_CHECKING
import config

if TYPE_CHECKING:
    from states.state_machine import StateMachine


class SplashScreenState:
    """Splash screen state with fade animations."""
    
    def __init__(self, state_machine: 'StateMachine', screen: pygame.Surface):
        """Initialize splash screen state.
        
        Args:
            state_machine: The state machine managing state transitions.
            screen: The pygame Surface to render to.
        """
        self.state_machine = state_machine
        self.screen = screen
        
        # Load splash image
        splash_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'splash.png')
        try:
            self.splash_image = pygame.image.load(splash_path).convert_alpha()
            # Scale to fit screen while maintaining aspect ratio
            screen_width, screen_height = screen.get_size()
            img_width, img_height = self.splash_image.get_size()
            scale = min(screen_width / img_width, screen_height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            self.splash_image = pygame.transform.scale(self.splash_image, (new_width, new_height))
        except (pygame.error, FileNotFoundError):
            # Fallback if image not found
            self.splash_image = None
        
        # Animation state
        self.time_elapsed = 0.0
        self.alpha = 0.0
        self.fade_in_complete = False
        self.fade_out_started = False
        self.should_transition = False
    
    def enter(self) -> None:
        """Called when entering this state."""
        self.time_elapsed = 0.0
        self.alpha = 0.0
        self.fade_in_complete = False
        self.fade_out_started = False
        self.should_transition = False
    
    def exit(self) -> None:
        """Called when exiting this state."""
        pass
    
    def update(self, dt: float) -> None:
        """Update splash screen animation.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        dt_seconds = dt / 60.0
        self.time_elapsed += dt_seconds
        
        # Fade in
        if not self.fade_in_complete:
            fade_progress = self.time_elapsed / config.SPLASH_FADE_IN_DURATION
            if fade_progress >= 1.0:
                self.alpha = 1.0
                self.fade_in_complete = True
            else:
                self.alpha = fade_progress
        else:
            # Wait, then fade out
            wait_time = config.SPLASH_DISPLAY_DURATION - config.SPLASH_FADE_IN_DURATION
            if self.time_elapsed >= wait_time and not self.fade_out_started:
                self.fade_out_started = True
            
            if self.fade_out_started:
                fade_out_start_time = wait_time
                fade_out_progress = (self.time_elapsed - fade_out_start_time) / config.SPLASH_FADE_OUT_DURATION
                if fade_out_progress >= 1.0:
                    # Mark for transition
                    self.alpha = 0.0
                    self.should_transition = True
                else:
                    self.alpha = 1.0 - fade_out_progress
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw splash screen.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        # Clear screen
        screen.fill((0, 0, 0))
        
        # Draw splash image with alpha
        if self.splash_image:
            # Create surface with alpha
            alpha_surf = self.splash_image.copy()
            alpha_surf.set_alpha(int(255 * self.alpha))
            
            # Center on screen
            screen_width, screen_height = screen.get_size()
            img_width, img_height = alpha_surf.get_size()
            x = (screen_width - img_width) // 2
            y = (screen_height - img_height) // 2
            screen.blit(alpha_surf, (x, y))
    
    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle pygame events.
        
        Args:
            event: The pygame event to handle.
        """
        # Skip on any input (keyboard or controller)
        if event.type == pygame.KEYDOWN or event.type == pygame.JOYBUTTONDOWN:
            if self.fade_in_complete:
                # Start fade out immediately
                self.fade_out_started = True
                # Adjust time so fade out starts now
                wait_time = config.SPLASH_DISPLAY_DURATION - config.SPLASH_FADE_IN_DURATION
                self.time_elapsed = wait_time
    

