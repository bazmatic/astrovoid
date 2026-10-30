"""Keep tests silent: no audio device output."""
import os

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
