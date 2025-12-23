"""Splash screen state implementation.

This module provides the splash screen state that displays the game logo
with fade-in/out animations and auto-advances to the menu.
"""

import pygame
import os
from typing import TYPE_CHECKING, Optional
import config
from utils.resource_path import resource_path

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

if TYPE_CHECKING:
    from states.state_machine import StateMachine


class SplashScreenState:
    """Splash screen state with fade animations and video playback."""
    
    def __init__(self, state_machine: 'StateMachine', screen: pygame.Surface):
        """Initialize splash screen state.
        
        Args:
            state_machine: The state machine managing state transitions.
            screen: The pygame Surface to render to.
        """
        self.state_machine = state_machine
        self.screen = screen
        
        # Load splash image
        splash_path = resource_path('assets/splash.png')
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
        
        # Video state
        self.video_cap: Optional[object] = None  # cv2.VideoCapture when available
        self.video_fps: float = 30.0
        self.video_frame: Optional[pygame.Surface] = None
        self.video_started = False
        self.video_complete = False
        self.video_path = resource_path('assets/video.mp4')
        self.screen_width, self.screen_height = screen.get_size()
        self.video_time_accumulator: float = 0.0
        
        # Animation state
        self.time_elapsed = 0.0
        self.alpha = 0.0
        self.fade_in_complete = False
        self.fade_out_started = False
        self.should_transition = False
        self.showing_image = True
    
    def enter(self) -> None:
        """Called when entering this state."""
        self.time_elapsed = 0.0
        self.alpha = 0.0
        self.fade_in_complete = False
        self.fade_out_started = False
        self.should_transition = False
        self.showing_image = True
        self.video_started = False
        self.video_complete = False
        self.video_frame = None
        self.video_time_accumulator = 0.0
        
        # Close any existing video capture
        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None
    
    def exit(self) -> None:
        """Called when exiting this state."""
        # Clean up video capture
        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None
    
    def _load_video(self) -> bool:
        """Load and initialize video playback.
        
        Returns:
            True if video was loaded successfully, False otherwise.
        """
        if not CV2_AVAILABLE:
            print("Warning: opencv-python not available. Video playback disabled.")
            return False
        
        try:
            if not os.path.exists(self.video_path):
                print(f"Warning: Video file not found: {self.video_path}")
                return False
            
            self.video_cap = cv2.VideoCapture(self.video_path)
            if not self.video_cap.isOpened():
                print(f"Warning: Could not open video file: {self.video_path}")
                return False
            
            self.video_fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            if self.video_fps <= 0:
                self.video_fps = 30.0
            
            # Load first frame immediately
            ret, frame = self.video_cap.read()
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Scale to fit screen while maintaining aspect ratio
                frame_height, frame_width = frame_rgb.shape[:2]
                scale = min(self.screen_width / frame_width, self.screen_height / frame_height)
                new_width = int(frame_width * scale)
                new_height = int(frame_height * scale)
                
                # Resize frame
                frame_resized = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
                
                # Convert to pygame surface
                frame_surface = pygame.surfarray.make_surface(frame_resized.swapaxes(0, 1))
                self.video_frame = frame_surface.convert()
            
            return True
        except Exception as e:
            print(f"Warning: Error loading video: {e}")
            return False
    
    def _update_video(self, dt_seconds: float) -> None:
        """Update video playback and load next frame.
        
        Args:
            dt_seconds: Delta time in seconds.
        """
        if self.video_cap is None or not self.video_cap.isOpened():
            self.video_complete = True
            return
        
        # Accumulate time for time-based frame reading
        # Apply speed multiplier to slow down or speed up playback
        self.video_time_accumulator += dt_seconds * config.SPLASH_VIDEO_SPEED_MULTIPLIER
        
        # Calculate how many frames should have elapsed based on video FPS
        frames_to_advance = int(self.video_time_accumulator * self.video_fps)
        
        if frames_to_advance > 0:
            # Advance by the calculated number of frames
            for _ in range(frames_to_advance):
                ret, frame = self.video_cap.read()
                if not ret:
                    # Video ended
                    self.video_complete = True
                    self.video_cap.release()
                    self.video_cap = None
                    return
            
            # Update accumulator to keep fractional frame time
            self.video_time_accumulator -= frames_to_advance / self.video_fps
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Scale to fit screen while maintaining aspect ratio
            frame_height, frame_width = frame_rgb.shape[:2]
            scale = min(self.screen_width / frame_width, self.screen_height / frame_height)
            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)
            
            # Resize frame
            frame_resized = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Convert to pygame surface
            frame_surface = pygame.surfarray.make_surface(frame_resized.swapaxes(0, 1))
            self.video_frame = frame_surface.convert()
    
    def update(self, dt: float) -> None:
        """Update splash screen animation.
        
        Args:
            dt: Delta time since last update (normalized to 60fps).
        """
        dt_seconds = dt / 60.0
        self.time_elapsed += dt_seconds
        
        if self.showing_image:
            # Phase 1: Show image with fade-in
            if not self.fade_in_complete:
                fade_progress = self.time_elapsed / config.SPLASH_FADE_IN_DURATION
                if fade_progress >= 1.0:
                    self.alpha = 1.0
                    self.fade_in_complete = True
                else:
                    self.alpha = fade_progress
            else:
                # Wait for image display duration, then switch to video
                wait_time = config.SPLASH_DISPLAY_DURATION - config.SPLASH_FADE_IN_DURATION
                if self.time_elapsed >= wait_time and not self.video_started:
                    # Switch to video
                    self.showing_image = False
                    self.video_started = True
                    self.time_elapsed = 0.0  # Reset timer for video phase
                    self.video_time_accumulator = 0.0
                    self.alpha = 1.0
                    if not self._load_video():
                        # If video fails to load, skip to fade out
                        self.video_complete = True
                        self.fade_out_started = True
                        self.time_elapsed = 0.0  # Reset timer for fade out
        else:
            # Phase 2: Play video
            if not self.video_complete:
                self._update_video(dt_seconds)
            else:
                # Phase 3: Fade out after video
                if not self.fade_out_started:
                    self.fade_out_started = True
                    # Reset timer for fade out
                    self.time_elapsed = 0.0
                
                fade_out_progress = self.time_elapsed / config.SPLASH_FADE_OUT_DURATION
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
        
        if self.showing_image:
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
        else:
            # Draw video frame with alpha
            if self.video_frame:
                # Create surface with alpha
                alpha_surf = self.video_frame.copy()
                alpha_surf.set_alpha(int(255 * self.alpha))
                
                # Center on screen
                screen_width, screen_height = screen.get_size()
                frame_width, frame_height = alpha_surf.get_size()
                x = (screen_width - frame_width) // 2
                y = (screen_height - frame_height) // 2
                screen.blit(alpha_surf, (x, y))
    
    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle pygame events.
        
        Args:
            event: The pygame event to handle.
        """
        # Skip on any input (keyboard or controller)
        if event.type == pygame.KEYDOWN or event.type == pygame.JOYBUTTONDOWN:
            if self.showing_image and self.fade_in_complete:
                # Skip image and go to video
                self.showing_image = False
                self.video_started = True
                self.time_elapsed = 0.0
                self.video_time_accumulator = 0.0
                self.alpha = 1.0
                if not self._load_video():
                    self.video_complete = True
                    self.fade_out_started = True
            elif not self.showing_image and not self.video_complete:
                # Skip video and go to fade out
                self.video_complete = True
                self.fade_out_started = True
                self.time_elapsed = 0.0
                if self.video_cap is not None:
                    self.video_cap.release()
                    self.video_cap = None
            elif self.fade_out_started:
                # Already fading out, do nothing
                pass
    

