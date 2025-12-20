#!/bin/bash

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment and run the game
source venv/bin/activate && python main.py


