"""Resource path utility for PyInstaller compatibility.

This module provides a helper function to resolve resource paths that work
correctly both in development and when frozen by PyInstaller.
"""

import sys
import os
from pathlib import Path
from typing import Union


def resource_path(relative_path: Union[str, Path]) -> str:
    """Get absolute path to resource, works for dev and PyInstaller.
    
    When running from source, returns path relative to project root.
    When frozen by PyInstaller, uses sys._MEIPASS to find bundled resources.
    
    Args:
        relative_path: Path relative to project root (e.g., "assets/gauge.png").
        
    Returns:
        Absolute path to the resource file.
    """
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development - use project root
        # Go up from utils/ to project root
        base_path = Path(__file__).parent.parent
    
    return str(base_path / relative_path)

