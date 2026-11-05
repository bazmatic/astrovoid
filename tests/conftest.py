"""Keep tests silent (no audio device output) and deterministic (inchworms use the scripted stride, not the sampled brain)."""
import os

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("INCHWORM_POLICY", "")      # tests that want the bundled brain unset it
