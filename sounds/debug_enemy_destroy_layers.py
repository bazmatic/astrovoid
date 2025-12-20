"""
Utility to export the enemy-destroy explosion layers as WAV files for listening.

Run:
    python sounds/debug_enemy_destroy_layers.py

Outputs WAV files in the sounds/ directory:
    - enemy_destroy_combined.wav
    - enemy_destroy_crack.wav
    - enemy_destroy_mid.wav
    - enemy_destroy_bass.wav
    - enemy_destroy_sparkle.wav
"""

import os
import sys

# Ensure repository root is on sys.path when run from the sounds/ folder
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from sound_manager import SoundManager


def main() -> None:
    sm = SoundManager()
    output_dir = os.path.dirname(os.path.abspath(__file__))
    # Fixed pitch multiplier for consistent audition
    sm.export_enemy_destroy_layers(output_dir=output_dir, pitch_multiplier=1.0)
    print("Exported enemy destroy layers to:", output_dir)


if __name__ == "__main__":
    main()

