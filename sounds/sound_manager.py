"""Sound manager for game audio effects.

This module provides programmatic sound generation and playback for game sounds
including white noise for thruster and 8-bit blip sounds for shooting.
"""

import pygame
import random
import math
import numpy as np
import config
from typing import Optional


class SoundManager:
    """Manages sound generation and playback for game audio effects.
    
    Generates sounds programmatically using pygame.sndarray and manages
    continuous playback for thruster sounds and one-shot playback for
    shooting sounds.
    """
    
    def __init__(self) -> None:
        """Initialize sound manager and generate sounds."""
        if not config.SOUND_ENABLED:
            self.thruster_sound: Optional[pygame.mixer.Sound] = None
            self.shoot_sound: Optional[pygame.mixer.Sound] = None
            self.thruster_channel: Optional[pygame.mixer.Channel] = None
            return
        
        # Initialize mixer if not already done
        if not pygame.mixer.get_init():
            pygame.mixer.init(
                frequency=config.SOUND_SAMPLE_RATE,
                size=-16,  # 16-bit signed samples
                channels=2,  # Stereo
                buffer=512  # Small buffer for low latency
            )
        
        # Generate sounds
        self.thruster_sound = self._generate_white_noise()
        self.shoot_sound = self._generate_blip()
        
        # Set up dedicated channel for thruster (continuous sound)
        self.thruster_channel = pygame.mixer.Channel(0)
        self.thruster_channel.set_volume(config.THRUSTER_SOUND_VOLUME)
        
        # Set volume for shoot sound
        if self.shoot_sound:
            self.shoot_sound.set_volume(config.SHOOT_SOUND_VOLUME)
    
    def _generate_white_noise(self) -> Optional[pygame.mixer.Sound]:
        """Generate white noise sound for thruster.
        
        Creates a short loop of random samples that can be played continuously.
        
        Returns:
            pygame.mixer.Sound object with white noise, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = config.THRUSTER_NOISE_DURATION
        num_samples = int(sample_rate * duration)
        
        # Generate random samples (white noise)
        # Use int16 range: -32768 to 32767
        samples = []
        for _ in range(num_samples):
            # Generate random value in int16 range
            sample = random.randint(-32768, 32767)
            samples.append(sample)
        
        # Convert to numpy array format expected by pygame.sndarray
        # pygame.sndarray expects a 2D array: (num_samples, channels)
        # For stereo, we duplicate the samples
        samples_array = np.array(samples, dtype=np.int16)
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_array
        stereo_samples[:, 1] = samples_array
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        return sound
    
    def _generate_blip(self) -> Optional[pygame.mixer.Sound]:
        """Generate 8-bit style blip sound for shooting.
        
        Creates a short square wave tone with attack/decay envelope.
        
        Returns:
            pygame.mixer.Sound object with blip sound, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        frequency = config.SHOOT_BLIP_FREQUENCY
        duration = config.SHOOT_BLIP_DURATION
        num_samples = int(sample_rate * duration)
        
        # Generate square wave
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            # Square wave: +1 for first half of period, -1 for second half
            phase = (t * frequency) % 1.0
            square_value = 1.0 if phase < 0.5 else -1.0
            
            # Apply envelope (attack and decay)
            # Attack: first 20% of duration
            # Decay: last 30% of duration
            attack_end = 0.2
            decay_start = 0.7
            progress = i / num_samples
            
            if progress < attack_end:
                # Attack: fade in
                envelope = progress / attack_end
            elif progress > decay_start:
                # Decay: fade out
                envelope = (1.0 - progress) / (1.0 - decay_start)
            else:
                # Sustain: full volume
                envelope = 1.0
            
            # Scale to int16 range and apply envelope
            sample_value = int(square_value * 16383 * envelope)  # Use ~50% of range for 8-bit feel
            samples.append(sample_value)
        
        # Convert to numpy array format
        samples_array = np.array(samples, dtype=np.int16)
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_array
        stereo_samples[:, 1] = samples_array
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        return sound
    
    def start_thruster(self) -> None:
        """Start playing thruster sound in a loop.
        
        If sound is already playing, this does nothing.
        """
        if not config.SOUND_ENABLED or not self.thruster_sound or not self.thruster_channel:
            return
        
        # Only start if not already playing
        if not self.thruster_channel.get_busy():
            self.thruster_channel.play(self.thruster_sound, loops=-1)  # -1 = infinite loop
    
    def stop_thruster(self) -> None:
        """Stop playing thruster sound."""
        if not config.SOUND_ENABLED or not self.thruster_channel:
            return
        
        self.thruster_channel.stop()
    
    def play_shoot(self) -> None:
        """Play shoot blip sound once.
        
        Uses a separate channel so it doesn't interfere with thruster sound.
        """
        if not config.SOUND_ENABLED or not self.shoot_sound:
            return
        
        # Use channel 1 for shoot sound (channel 0 is reserved for thruster)
        shoot_channel = pygame.mixer.Channel(1)
        shoot_channel.play(self.shoot_sound)
