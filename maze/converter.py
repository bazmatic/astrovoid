"""Grid to walls conversion.

This module provides utilities for converting maze grids to wall segments.
"""

from typing import List
import config
from maze.wall_segment import WallSegment
from maze.positioning import MazePositionCalculator


class GridToWallsConverter:
    """Converts maze grid to wall segments."""
    
    def __init__(self, position_calculator: MazePositionCalculator):
        """Initialize converter.
        
        Args:
            position_calculator: Calculator for position conversions.
        """
        self.position_calculator = position_calculator
    
    def convert(self, grid: List[List[int]]) -> List[WallSegment]:
        """Convert grid to list of wall line segments.
        
        Args:
            grid: 2D grid where 1 = wall, 0 = path.
            
        Returns:
            List of WallSegment instances.
        """
        walls = []
        grid_height = len(grid)
        grid_width = len(grid[0]) if grid_height > 0 else 0
        
        for y in range(grid_height):
            for x in range(grid_width):
                if grid[y][x] == 1:  # Wall cell
                    # The outer ring of cells bounds the playing area and can never be destroyed
                    on_perimeter = x in (0, grid_width - 1) or y in (0, grid_height - 1)
                    wall_segments = self._create_wall_segments_for_cell(x, y, destructible=not on_perimeter)
                    walls.extend(wall_segments)
        
        return walls
    
    def _create_wall_segments_for_cell(self, grid_x: int, grid_y: int,
                                       destructible: bool = True) -> List[WallSegment]:
        """Create wall segments for a single grid cell.
        
        Args:
            grid_x: Grid X coordinate.
            grid_y: Grid Y coordinate.
            destructible: Whether the cell's walls can be shot away.
            
        Returns:
            List of WallSegment instances for the cell's four edges.
        """
        cell_size_x = self.position_calculator.cell_size_x
        cell_size_y = self.position_calculator.cell_size_y
        screen_x, screen_y = self.position_calculator.grid_to_screen(grid_x, grid_y)
        
        # Create wall rectangle as line segments with hit points
        # Top edge
        top = WallSegment(
            (screen_x, screen_y),
            (screen_x + cell_size_x, screen_y),
            config.WALL_HIT_POINTS,
            destructible
        )
        # Right edge
        right = WallSegment(
            (screen_x + cell_size_x, screen_y),
            (screen_x + cell_size_x, screen_y + cell_size_y),
            config.WALL_HIT_POINTS,
            destructible
        )
        # Bottom edge
        bottom = WallSegment(
            (screen_x + cell_size_x, screen_y + cell_size_y),
            (screen_x, screen_y + cell_size_y),
            config.WALL_HIT_POINTS,
            destructible
        )
        # Left edge
        left = WallSegment(
            (screen_x, screen_y + cell_size_y),
            (screen_x, screen_y),
            config.WALL_HIT_POINTS,
            destructible
        )
        
        return [top, right, bottom, left]


