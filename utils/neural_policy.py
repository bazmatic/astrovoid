"""Where a creature's trained brain lives. Neural is the default wherever a bundled brain exists."""
import os
from pathlib import Path

from utils.resource_path import resource_path


def neural_policy_path(variable, bundled):
    """The file the environment variable names (empty: none, so the scripted controller), else the brain bundled in
    assets/neural/`bundled` when it exists, else None."""
    if variable in os.environ:
        return os.environ[variable] or None
    path = Path(resource_path(f'assets/neural/{bundled}'))
    return str(path) if path.is_file() else None
