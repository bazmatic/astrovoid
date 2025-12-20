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
import wave
import os
from typing import Optional, Dict, Tuple, Any


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
        self.enemy_destroy_sound = None  # Generated on-demand with pitch variation
        self.upgraded_shoot_sound: Optional[pygame.mixer.Sound] = None  # Generated on first use
        self.tinkling_sound_cache: Dict[float, Optional[pygame.mixer.Sound]] = {}  # Cache tinkling sounds by pitch
        
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
    
    def stop_all_sounds(self) -> None:
        """Stop all currently playing sounds."""
        if not config.SOUND_ENABLED:
            return
        
        # Stop all mixer channels
        for i in range(pygame.mixer.get_num_channels()):
            channel = pygame.mixer.Channel(i)
            if channel.get_busy():
                channel.stop()
    
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
    
    def _generate_enemy_destroy(
        self,
        pitch_multiplier: float = 1.0,
        return_layers: bool = False
    ) -> Optional[pygame.mixer.Sound]:
        """Generate layered arcade explosion sound for enemy destruction.
        
        Creates a satisfying, punchy explosion with multiple layers:
        - High-frequency crack (breaking glass/metallic snap)
        - Mid-range explosion (descending tone)
        - Bass rumble (low frequency weight)
        - Sparkle tail (high-pitched finishing flourish)
        
        Args:
            pitch_multiplier: Pitch variation multiplier (0.85 to 1.15 for ±15% variation).
        
        Returns:
            pygame.mixer.Sound object with explosion sound, or None if sounds disabled.
            When return_layers is True, returns (sound, layers_dict).
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = 0.5  # 500ms for a satisfying explosion (middle of 0.3-0.7s range)
        num_samples = int(sample_rate * duration)
        
        # Create time array for vectorized operations
        t_array = np.arange(num_samples, dtype=np.float32) / sample_rate
        progress_array = np.arange(num_samples, dtype=np.float32) / num_samples
        
        # Pre-generate reusable noise sources
        noise_white = np.random.normal(0.0, 1.0, num_samples).astype(np.float32)
        # Slightly smoothed noise for body; short kernel to avoid dulling transients
        body_kernel = np.ones(9, dtype=np.float32) / 9.0
        filtered_body_noise = np.convolve(noise_white, body_kernel, mode='same')
        # High-passed noise for crack/sparkle by subtracting a wider blur
        blur_kernel = np.ones(25, dtype=np.float32) / 25.0
        blurred_noise = np.convolve(noise_white, blur_kernel, mode='same')
        noise_high = noise_white - blurred_noise
        
        # Initialize all layers
        crack_layer = np.zeros(num_samples, dtype=np.float32)
        explosion_layer = np.zeros(num_samples, dtype=np.float32)
        bass_layer = np.zeros(num_samples, dtype=np.float32)
        sparkle_layer = np.zeros(num_samples, dtype=np.float32)
        
        # Layer 1: High-frequency crack (breaking glass/metallic snap)
        # Very early, short, and noisy to avoid tonal chirp
        crack_mask = progress_array < 0.2
        crack_indices = np.where(crack_mask)[0]
        if len(crack_indices) > 0:
            crack_progress = progress_array[crack_mask] / 0.2
            crack_t = t_array[crack_mask]
            # Band-limited noisy crack with a slight FM wobble to avoid pure tone
            base_freq = 800 * pitch_multiplier
            fm = 400 * pitch_multiplier
            fm_mod = np.sin(2 * math.pi * fm * crack_t) * 0.1
            crack_carrier = np.sin(2 * math.pi * base_freq * crack_t * (1.0 + fm_mod))
            # Band-limit noise toward lower highs (~0.8–3 kHz) to remove squeak
            crack_noise_raw = noise_high[crack_mask]
            bp_mid = crack_noise_raw - np.convolve(crack_noise_raw, np.ones(19)/19.0, mode='same')
            bp_wide = crack_noise_raw - np.convolve(crack_noise_raw, np.ones(37)/37.0, mode='same')
            crack_noise = (bp_mid * 0.55 + bp_wide * 0.45) * 1.1
            # Add a micro click (single-cycle impulse) to emphasize the initial snap
            click_env = np.exp(-crack_progress * 220.0)
            click = click_env * 1.2
            # Reduce tonal part to avoid bell-like ring; noise dominates
            crack_signal = crack_carrier * 0.35 + crack_noise + click
            # Envelope: instantaneous attack, very fast decay to avoid tail
            crack_envelope = np.where(
                crack_progress < 0.02,
                crack_progress / 0.02,
                np.exp(-(crack_progress - 0.02) / 0.98 * 14.0)
            )
            crack_layer[crack_mask] = crack_signal * crack_envelope * 0.9  # strong but very brief
        
        # Layer 2: Mid-range explosion (main body)
        # Texture-dominant noise with slight downward bend to avoid tonal sweep
        explosion_mask = progress_array < 0.8
        explosion_indices = np.where(explosion_mask)[0]
        if len(explosion_indices) > 0:
            explosion_progress = progress_array[explosion_mask] / 0.8
            explosion_t = t_array[explosion_mask]
            # Lowpass cutoff sweeps downward for a satisfying drop
            start_cutoff = 180.0 * pitch_multiplier
            end_cutoff = 40.0 * pitch_multiplier
            cutoff = start_cutoff - (start_cutoff - end_cutoff) * explosion_progress
            # Envelope: fast attack, smooth but present decay across most of the duration
            explosion_envelope = np.where(
                explosion_progress < 0.03,
                explosion_progress / 0.03,
                np.exp(-(explosion_progress - 0.03) / 0.97 * 2.6)
            )
            # Crunchy click train that decelerates: start dense, then widen spacing
            # Create an impulse train whose period increases over time
            start_rate = 750.0   # clicks per second initially (lowered)
            end_rate = 90.0      # slow clicks near tail
            inst_rate = start_rate - (start_rate - end_rate) * explosion_progress
            phase = np.cumsum(inst_rate / sample_rate)
            # Create impulses at each wrap: diff of the floored phase
            impulse = np.diff(np.floor(phase), prepend=0).astype(np.float32)
            # Shape impulses with a short decay kernel
            click_kernel = np.exp(-np.arange(20) / 6.0).astype(np.float32)
            impulse = np.convolve(impulse, click_kernel, mode='same') * 1.25
            # Texture the impulses with filtered noise
            wide_kernel = np.ones(55, dtype=np.float32) / 55.0
            tight_kernel = np.ones(23, dtype=np.float32) / 23.0
            wide = np.convolve(noise_white, wide_kernel, mode='same')[explosion_mask]
            tight = np.convolve(noise_white, tight_kernel, mode='same')[explosion_mask]
            # Blend tighter filtering early, wider later
            blend = (explosion_progress).clip(0.0, 1.0)
            textured = tight * (1.0 - blend) + wide * blend
            explosion_signal = (textured * 0.4 + impulse * 1.35) * explosion_envelope
            # Add a downward sine/triangle hybrid for body without whistle, lower freq
            sweep_freq = (110.0 - 70.0 * explosion_progress) * pitch_multiplier
            tri_body = 2.0 * np.abs((sweep_freq * explosion_t) % 1.0) - 1.0
            tri_body = np.tanh(tri_body * 1.3) * 0.24
            sine_body = np.sin(2 * math.pi * sweep_freq * explosion_t) * 0.14
            explosion_signal += (sine_body + tri_body) * explosion_envelope
            # Post low-pass to tame residual highs
            lp_kernel = np.ones(9, dtype=np.float32) / 9.0
            explosion_signal = np.convolve(explosion_signal, lp_kernel, mode='same')
            explosion_layer[explosion_mask] = explosion_signal * 1.0  # Base amplitude
        
        # Layer 3: Bass rumble (low frequency weight)
        # Extends longer and overlaps to avoid gaps
        bass_mask = progress_array < 0.9
        bass_indices = np.where(bass_mask)[0]
        if len(bass_indices) > 0:
            bass_progress = progress_array[bass_mask] / 0.9
            bass_t = t_array[bass_mask]
            bass_freq = 52 * pitch_multiplier
            bass_signal = np.sin(2 * math.pi * bass_freq * bass_t)
            # Add weight via gentle distortion of a low sine + smoothed noise
            low_noise_kernel = np.ones(65, dtype=np.float32) / 65.0
            low_noise = np.convolve(noise_white * 0.4, low_noise_kernel, mode='same')[bass_mask]
            bass_signal = np.tanh(bass_signal * 1.8 + low_noise * 1.35)
            # Envelope: slower attack, long decay to keep weight under the tail
            bass_envelope = np.where(
                bass_progress < 0.12,
                bass_progress / 0.12,
                np.exp(-(bass_progress - 0.12) / 0.88 * 1.6)
            )
            bass_layer[bass_mask] = bass_signal * bass_envelope * 0.6  # 0.4-0.6+ range
        
        # Layer 4: Sparkle tail (high-pitched finishing flourish)
        # Start earlier with quicker onset to avoid gap
        sparkle_mask = progress_array >= 0.2
        sparkle_indices = np.where(sparkle_mask)[0]
        if len(sparkle_indices) > 0:
            sparkle_progress = (progress_array[sparkle_mask] - 0.2) / 0.8
            sparkle_t = t_array[sparkle_mask]
            sparkle_freq = 2600 * pitch_multiplier
            shimmer_noise = noise_high[sparkle_mask] * 0.16
            sparkle_signal = (np.sin(2 * math.pi * sparkle_freq * sparkle_t) * 0.45 +
                            0.28 * np.sin(2 * math.pi * sparkle_freq * 2.1 * sparkle_t) +
                            shimmer_noise)
            # Envelope: brisk attack, smooth but not-too-long fade
            sparkle_envelope = np.where(
                sparkle_progress < 0.08,
                sparkle_progress / 0.08,
                np.exp(-(sparkle_progress - 0.08) / 0.92 * 2.8)
            )
            sparkle_layer[sparkle_mask] = sparkle_signal * sparkle_envelope * 0.4  # 0.3-0.5 range
        
        # Mix all layers together
        samples = crack_layer + explosion_layer + bass_layer + sparkle_layer
        
        # Normalize to prevent clipping while preserving relative layer amplitudes
        max_amplitude = np.max(np.abs(samples))
        target_max = 0.9
        if max_amplitude > target_max:
            samples = samples * (target_max / max_amplitude)
        
        # Scale to int16 range
        samples_int16 = (samples * 16383).astype(np.int16)
        
        # Convert to stereo
        stereo_samples = np.zeros((num_samples, 2), dtype=np.int16)
        stereo_samples[:, 0] = samples_int16
        stereo_samples[:, 1] = samples_int16
        
        # Create sound from array
        sound = pygame.sndarray.make_sound(stereo_samples)
        
        if not return_layers:
            return sound
        
        def _to_stereo_layer(layer: np.ndarray) -> np.ndarray:
            layer_copy = np.copy(layer)
            peak = np.max(np.abs(layer_copy))
            if peak > 0.0:
                layer_copy = layer_copy * (target_max / peak)
            layer_int16 = (layer_copy * 16383).astype(np.int16)
            stereo_layer = np.zeros((num_samples, 2), dtype=np.int16)
            stereo_layer[:, 0] = layer_int16
            stereo_layer[:, 1] = layer_int16
            return stereo_layer
        
        layers = {
            "combined": stereo_samples,
            "crack": _to_stereo_layer(crack_layer),
            "mid": _to_stereo_layer(explosion_layer),
            "bass": _to_stereo_layer(bass_layer),
            "sparkle": _to_stereo_layer(sparkle_layer),
        }
        return sound, layers
    
    def play_enemy_destroy(self) -> None:
        """Play enemy destruction explosion sound once with pitch variation.
        
        Generates the sound on-demand with random pitch variation (±15%) to prevent
        ear fatigue when destroying multiple enemies rapidly. Each destruction gets
        a fresh, slightly different sound.
        
        Uses a separate channel so it doesn't interfere with other sounds.
        """
        if not config.SOUND_ENABLED:
            return
        
        # Generate sound with random pitch variation (±15%)
        # Pitch multiplier range: 0.85 to 1.15
        pitch_multiplier = random.uniform(0.85, 1.15)
        sound = self._generate_enemy_destroy(pitch_multiplier)
        
        if not sound:
            return
        
        # Set volume
        sound.set_volume(config.ENEMY_DESTROY_SOUND_VOLUME)
        
        # Use channel 2 for enemy destroy sound
        destroy_channel = pygame.mixer.Channel(2)
        destroy_channel.play(sound)
    
    def export_enemy_destroy_layers(
        self,
        output_dir: str = ".",
        pitch_multiplier: float = 1.0
    ) -> None:
        """Export combined and individual explosion layers to WAV for debugging."""
        if not config.SOUND_ENABLED:
            return
        
        result = self._generate_enemy_destroy(
            pitch_multiplier=pitch_multiplier,
            return_layers=True
        )
        
        if not result:
            return
        
        sound, layers = result  # type: ignore
        os.makedirs(output_dir, exist_ok=True)
        for name, stereo in layers.items():
            path = os.path.join(output_dir, f"enemy_destroy_{name}.wav")
            with wave.open(path, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(config.SOUND_SAMPLE_RATE)
                wf.writeframes(stereo.tobytes())
    
    def _generate_tinkling_sound(self, pitch: float) -> Optional[pygame.mixer.Sound]:
        """Generate bell-like tinkling sound with specified pitch.
        
        Creates a pleasant bell/chime sound with harmonics for richness.
        
        Args:
            pitch: Frequency in Hz for the base tone.
            
        Returns:
            pygame.mixer.Sound object with tinkling sound, or None if sounds disabled.
        """
        if not config.SOUND_ENABLED:
            return None
        
        sample_rate = config.SOUND_SAMPLE_RATE
        duration = 0.15  # Short duration for tinkling effect (150ms)
        num_samples = int(sample_rate * duration)
        
        # Generate tinkling: bell-like tone with harmonics
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            
            # Base frequency
            base_freq = pitch
            
            # Create bell-like tone with harmonics
            tone = math.sin(2 * math.pi * base_freq * t)
            # Add second harmonic (octave) for bell character
            tone += 0.5 * math.sin(2 * math.pi * base_freq * 2 * t)
            # Add third harmonic for more richness
            tone += 0.25 * math.sin(2 * math.pi * base_freq * 3 * t)
            
            # Apply envelope: quick attack, then exponential decay
            if progress < 0.1:
                # Quick attack for bell-like character
                envelope = progress / 0.1
            else:
                # Exponential decay
                decay_progress = (progress - 0.1) / 0.9
                envelope = math.exp(-decay_progress * 5)  # Moderate decay
            
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
        if sound:
            sound.set_volume(config.SHOOT_SOUND_VOLUME * 0.8)  # Slightly quieter than shoot
        return sound
    
    def play_tinkling(self, pitch: float) -> None:
        """Play tinkling sound at specified pitch.
        
        Uses cached sounds to avoid regeneration. Pitch increases with each star.
        
        Args:
            pitch: Frequency in Hz for the tinkling sound.
        """
        if not config.SOUND_ENABLED:
            return
        
        # Check cache first
        if pitch not in self.tinkling_sound_cache:
            self.tinkling_sound_cache[pitch] = self._generate_tinkling_sound(pitch)
        
        sound = self.tinkling_sound_cache[pitch]
        if sound:
            # Use channel 3 for tinkling sound
            tinkling_channel = pygame.mixer.Channel(3)
            tinkling_channel.play(sound)


