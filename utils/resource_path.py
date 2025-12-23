"""Resource path resolution for PyInstaller compatibility.

This module provides a function to resolve resource paths that works both
in development mode and when bundled with PyInstaller.
"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller.
    
    When running from source, returns path relative to project root.
    When running from PyInstaller bundle, uses sys._MEIPASS to find resources.
    
    Args:
        relative_path: Path relative to project root (e.g., 'assets/splash.png')
        
    Returns:
        Absolute path to the resource file
    """
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development mode
        base_path = Path(__file__).parent.parent
    
    return str(base_path / relative_path)
