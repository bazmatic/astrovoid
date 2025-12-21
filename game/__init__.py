"""Game management modules for handling entities, collisions, and state."""

import sys
import os
import importlib.util

# Import Game from the parent game.py module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
game_module_path = os.path.join(parent_dir, 'game.py')
spec = importlib.util.spec_from_file_location("_game_module", game_module_path)
game_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game_module)

# Export Game class
Game = game_module.Game

