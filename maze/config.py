"""Maze generation configuration.

This module provides configuration classes for maze generation, including
complexity levels and generation parameters.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import config


class MazeComplexity(Enum):
    """Maze complexity levels."""
    SIMPLE = "simple"
    NORMAL = "normal"
    COMPLEX = "complex"
    EXTREME = "extreme"


@dataclass
class MazeGenerationConfig:
    """Configuration for maze generation algorithm.
    
    Attributes:
        step_size: Step size for recursive backtracking (larger = wider passages)
        passage_width: Width of passages to clear around connections
        clear_radius: Radius for clearing extra paths
        corner_clear_size: Size of cleared area around corners
        extra_paths_multiplier: Multiplier for number of extra paths (applied to level)
        grid_size_base: Base grid size
        grid_size_increment: Grid size increment per level
    """
    step_size: int
    passage_width: int
    clear_radius: int
    corner_clear_size: int
    extra_paths_multiplier: int
    grid_size_base: int
    grid_size_increment: int


class MazeComplexityPresets:
    """Factory for creating maze generation configs based on complexity level."""
    
    @staticmethod
    def get_config(complexity: MazeComplexity) -> MazeGenerationConfig:
        """Get generation config for a complexity level.
        
        Args:
            complexity: The complexity level.
            
        Returns:
            MazeGenerationConfig with parameters for the complexity level.
        """
        if complexity == MazeComplexity.SIMPLE:
            return MazeGenerationConfig(
                step_size=3,
                passage_width=2,
                clear_radius=2,
                corner_clear_size=4,
                extra_paths_multiplier=5,
                grid_size_base=config.BASE_MAZE_SIZE,
                grid_size_increment=config.MAZE_SIZE_INCREMENT
            )
        elif complexity == MazeComplexity.NORMAL:
            return MazeGenerationConfig(
                step_size=5,
                passage_width=4,
                clear_radius=3,
                corner_clear_size=6,
                extra_paths_multiplier=10,
                grid_size_base=config.BASE_MAZE_SIZE,
                grid_size_increment=config.MAZE_SIZE_INCREMENT
            )
        elif complexity == MazeComplexity.COMPLEX:
            return MazeGenerationConfig(
                step_size=7,
                passage_width=6,
                clear_radius=4,
                corner_clear_size=8,
                extra_paths_multiplier=15,
                grid_size_base=config.BASE_MAZE_SIZE,
                grid_size_increment=config.MAZE_SIZE_INCREMENT
            )
        elif complexity == MazeComplexity.EXTREME:
            return MazeGenerationConfig(
                step_size=9,
                passage_width=8,
                clear_radius=5,
                corner_clear_size=10,
                extra_paths_multiplier=20,
                grid_size_base=config.BASE_MAZE_SIZE,
                grid_size_increment=config.MAZE_SIZE_INCREMENT
            )
        else:
            raise ValueError(f"Unknown complexity level: {complexity}")
    
    @staticmethod
    def get_complexity_from_level(level: int) -> MazeComplexity:
        """Get complexity level based on level number.
        
        Args:
            level: Current level number (1-based).
            
        Returns:
            MazeComplexity based on level ranges:
            - Levels 1-3: SIMPLE
            - Levels 4-7: NORMAL
            - Levels 8-11: COMPLEX
            - Levels 12+: EXTREME
        """
        if level <= 3:
            return MazeComplexity.SIMPLE
        elif level <= 7:
            return MazeComplexity.NORMAL
        elif level <= 11:
            return MazeComplexity.COMPLEX
        else:
            return MazeComplexity.EXTREME

