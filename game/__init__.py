"""Game management modules for handling entities, collisions, and state."""

import sys
import os

# Import Game from the parent game.py module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import Game from game.py (the file, not this package)
import importlib.util
game_module_path = os.path.join(parent_dir, 'game.py')
spec = importlib.util.spec_from_file_location("game_module", game_module_path)
game_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game_module)

# Export Game class
Game = game_module.Game

