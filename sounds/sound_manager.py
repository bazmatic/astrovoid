"""Sound manager for game audio effects.

This module provides programmatic sound generation and playback for game sounds
including white noise for thruster, click sounds for shooting, and explosion
sounds for enemy destruction.
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
            self.enemy_destroy_sound: Optional[pygame.mixer.Sound] = None
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
        self.shoot_sound = self._generate_click()
        self.enemy_destroy_sound = self._generate_enemy_destroy()
        self.upgraded_shoot_sound: Optional[pygame.mixer.Sound] = None  # Generated on first use
        
        # Set up dedicated channel for thruster (continuous sound)
        self.thruster_channel = pygame.mixer.Channel(0)
        self.thruster_channel.set_volume(config.THRUSTER_SOUND_VOLUME)
        
        # Set volume for shoot sound
        if self.shoot_sound:
            self.shoot_sound.set_volume(config.SHOOT_SOUND_VOLUME)
        
        # Set volume for enemy destroy sound
        if self.enemy_destroy_sound:
            self.enemy_destroy_sound.set_volume(config.ENEMY_DESTROY_SOUND_VOLUME)
    
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
    
    def _generate_click(self) -> Optional[pygame.mixer.Sound]:
        """Generate simple click sound for shooting.
        
        Creates a very short, sharp click sound - a brief impulse with quick decay.
        
        Returns:
            pygame.mixer.Sound object with click sound, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = 0.01  # Very short duration for a click (10ms)
        num_samples = int(sample_rate * duration)
        
        # Generate click: sharp impulse with exponential decay
        samples = []
        for i in range(num_samples):
            progress = i / num_samples
            
            # Create a sharp click: immediate peak followed by exponential decay
            # Use a very short attack (first 5% of samples) and quick decay
            if progress < 0.05:
                # Quick attack to peak
                envelope = progress / 0.05
            else:
                # Exponential decay
                decay_progress = (progress - 0.05) / 0.95
                envelope = math.exp(-decay_progress * 15)  # Fast decay
            
            # Generate a brief tone at higher frequency for the "click" character
            t = i / sample_rate
            frequency = 2000  # Higher frequency for sharper click
            tone = math.sin(2 * math.pi * frequency * t)
            
            # Scale to int16 range and apply envelope
            sample_value = int(tone * 16383 * envelope)
            samples.append(sample_value)
        
        # Convert to numpy array format
        samples_array = np.array(samples, dtype=np.int16)
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_array
        stereo_samples[:, 1] = samples_array
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        return sound
    
    def _generate_upgraded_shoot(self) -> Optional[pygame.mixer.Sound]:
        """Generate machine gun sound for upgraded guns.
        
        Creates a rapid-fire machine gun effect with multiple rapid clicks.
        
        Returns:
            pygame.mixer.Sound object with machine gun sound, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = 0.06  # Short duration for rapid-fire effect (60ms)
        num_samples = int(sample_rate * duration)
        
        # Machine gun: multiple rapid clicks
        num_clicks = 4  # Number of clicks in the burst
        click_duration = 0.008  # Each click is 8ms
        click_samples = int(sample_rate * click_duration)
        click_interval = num_samples // num_clicks  # Space between clicks
        
        samples = []
        for i in range(num_samples):
            sample_value = 0
            
            # Check if we're within any click
            for click_idx in range(num_clicks):
                click_start = click_idx * click_interval
                click_end = click_start + click_samples
                
                if click_start <= i < click_end:
                    # We're in a click - generate the click sound
                    click_local_sample = i - click_start
                    click_progress = click_local_sample / click_samples
                    click_time = click_local_sample / sample_rate
                    
                    # Slight pitch variation between clicks for realism
                    pitch_variation = 1.0 + (click_idx * 0.05)  # Slight upward pitch
                    frequency = 2000 * pitch_variation
                    
                    # Generate click tone
                    tone = math.sin(2 * math.pi * frequency * click_time)
                    
                    # Apply envelope: very quick attack and decay
                    if click_progress < 0.2:
                        # Quick attack
                        envelope = click_progress / 0.2
                    else:
                        # Fast exponential decay
                        decay_progress = (click_progress - 0.2) / 0.8
                        envelope = math.exp(-decay_progress * 20)  # Very fast decay
                    
                    # Add some high-frequency content for sharpness
                    tone += 0.3 * math.sin(2 * math.pi * frequency * 3 * click_time)
                    
                    sample_value += int(tone * 16383 * envelope * 0.8)  # Scale down slightly
                    break  # Only one click active at a time
            
            samples.append(sample_value)
        
        # Convert to numpy array format
        samples_array = np.array(samples, dtype=np.int16)
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_array
        stereo_samples[:, 1] = samples_array
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        if sound:
            sound.set_volume(config.SHOOT_SOUND_VOLUME * 1.1)  # Slightly louder
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
    
    def play_shoot(self, is_upgraded: bool = False) -> None:
        """Play shoot sound once.
        
        Uses a separate channel so it doesn't interfere with thruster sound.
        
        Args:
            is_upgraded: If True, plays an enhanced shooting sound for upgraded guns.
        """
        if not config.SOUND_ENABLED:
            return
        
        # Use channel 1 for shoot sound (channel 0 is reserved for thruster)
        shoot_channel = pygame.mixer.Channel(1)
        
        if is_upgraded:
            # Play enhanced upgraded shoot sound
            if not hasattr(self, 'upgraded_shoot_sound') or self.upgraded_shoot_sound is None:
                self.upgraded_shoot_sound = self._generate_upgraded_shoot()
            if self.upgraded_shoot_sound:
                shoot_channel.play(self.upgraded_shoot_sound)
        else:
            # Play normal shoot sound
            if self.shoot_sound:
                shoot_channel.play(self.shoot_sound)
    
    def _generate_enemy_destroy(self) -> Optional[pygame.mixer.Sound]:
        """Generate cool explosion sound for enemy destruction.
        
        Creates a satisfying explosion sound with descending tone and harmonics.
        
        Returns:
            pygame.mixer.Sound object with explosion sound, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = 0.15  # 150ms for a satisfying explosion
        num_samples = int(sample_rate * duration)
        
        # Generate explosion: descending tone with harmonics and noise
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            
            # Base frequency starts high and descends (explosion effect)
            start_freq = 400
            end_freq = 100
            frequency = start_freq - (start_freq - end_freq) * progress
            
            # Create main tone with harmonics for richness
            tone = math.sin(2 * math.pi * frequency * t)
            # Add second harmonic (octave)
            tone += 0.5 * math.sin(2 * math.pi * frequency * 2 * t)
            # Add third harmonic for more character
            tone += 0.25 * math.sin(2 * math.pi * frequency * 3 * t)
            
            # Add some noise for explosion character
            noise = random.uniform(-0.2, 0.2)
            tone += noise
            
            # Apply envelope: quick attack, then exponential decay
            if progress < 0.1:
                # Quick attack
                envelope = progress / 0.1
            else:
                # Exponential decay
                decay_progress = (progress - 0.1) / 0.9
                envelope = math.exp(-decay_progress * 4)  # Moderate decay
            
            # Normalize and scale to int16 range
            tone = max(-1.0, min(1.0, tone))  # Clamp to prevent clipping
            sample_value = int(tone * 16383 * envelope)
            samples.append(sample_value)
        
        # Convert to numpy array format
        samples_array = np.array(samples, dtype=np.int16)
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_array
        stereo_samples[:, 1] = samples_array
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        return sound
    
    def play_enemy_destroy(self) -> None:
        """Play enemy destruction explosion sound once.
        
        Uses a separate channel so it doesn't interfere with other sounds.
        """
        if not config.SOUND_ENABLED or not self.enemy_destroy_sound:
            return
        
        # Use channel 2 for enemy destroy sound
        destroy_channel = pygame.mixer.Channel(2)
        destroy_channel.play(self.enemy_destroy_sound)


