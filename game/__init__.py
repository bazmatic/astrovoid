"""Game management modules for handling entities, collisions, and state."""

import sys
import os
import importlib.util
import importlib.machinery
import types
import importlib

# Import Game from the parent game.py module
# Handle both development and PyInstaller environments
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle
    # In PyInstaller, all modules are in the archive and importable
    # The issue is the naming conflict: we have both game.py (module) and game/ (package)
    # Solution: Import the root-level game module by temporarily manipulating sys.modules
    base_path = sys._MEIPASS
    
    # CRITICAL: Ensure base_path is in sys.path so imports work
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    # The problem: when we load game.py as a file, its imports don't work
    # because the other modules are in the archive, not as files
    # Solution: Import it as a module by temporarily removing this package from sys.modules
    # Then import the root-level game module, then restore this package
    
    # Save current state
    original_game_module = sys.modules.get('game')
    original_root_game = sys.modules.get('_root_game')
    
    # Remove this package from sys.modules temporarily
    if 'game' in sys.modules:
        del sys.modules['game']
    
    try:
        # Now import the root-level game.py module
        # We need to import it with a different name to avoid conflict
        import importlib.util
        game_module_path = os.path.join(base_path, 'game.py')
        
        if os.path.exists(game_module_path):
            # Load as a module - this should allow imports to work
            spec = importlib.util.spec_from_file_location('_root_game', game_module_path)
            if spec and spec.loader:
                # Create the module
                root_game_module = importlib.util.module_from_spec(spec)
                # Set up the module's __path__ and __package__ so imports work
                root_game_module.__package__ = None
                # Add to sys.modules with a temporary name
                sys.modules['_root_game'] = root_game_module
                # Execute - imports should now work because modules are in the archive
                spec.loader.exec_module(root_game_module)
                Game = root_game_module.Game
            else:
                raise ImportError("Could not create spec for game module")
        else:
            raise ImportError(f"game.py not found at {game_module_path}")
    finally:
        # Restore this package in sys.modules
        if original_game_module:
            sys.modules['game'] = original_game_module
        elif 'game' not in sys.modules:
            sys.modules['game'] = sys.modules[__name__]
else:
    # Development mode - use file-based import
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    game_module_path = os.path.join(parent_dir, 'game.py')
    spec = importlib.util.spec_from_file_location("_game_module", game_module_path)
    game_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(game_module)
    Game = game_module.Game

