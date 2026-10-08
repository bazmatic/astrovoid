"""Grid to walls conversion.

This module provides utilities for converting maze grids to wall segments.
A wall cell is a solid block: it gets a segment only on each face that looks
onto open space, so blocks packed together share no inner edges.
"""

from typing import List, Tuple
import config
from maze.wall_segment import WallSegment
from maze.positioning import MazePositionCalculator

# Offsets to the cells above, right of, below and left of a cell
SIDES = ((0, -1), (1, 0), (0, 1), (-1, 0))


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
            List of WallSegment instances, one for each exposed face of each block.
        """
        walls = []
        for y, row in enumerate(grid):
            for x, value in enumerate(row):
                if value != 1:
                    continue
                for side in SIDES:
                    if not self.is_wall(grid, x + side[0], y + side[1]):
                        walls.append(self.face(grid, (x, y), side, config.WALL_HIT_POINTS))
        return walls
    
    @staticmethod
    def is_wall(grid: List[List[int]], grid_x: int, grid_y: int) -> bool:
        """Whether a cell is a wall block. Cells outside the grid are not."""
        return 0 <= grid_y < len(grid) and 0 <= grid_x < len(grid[grid_y]) and grid[grid_y][grid_x] == 1
    
    @staticmethod
    def on_perimeter(grid: List[List[int]], grid_x: int, grid_y: int) -> bool:
        """Whether a cell is in the outer ring, which bounds the playing area and can never be destroyed."""
        return grid_x in (0, len(grid[0]) - 1) or grid_y in (0, len(grid) - 1)
    
    def cell_rect(self, grid_x: int, grid_y: int) -> Tuple[int, int, int, int]:
        """Screen area of a cell as (left, top, width, height), in whole pixels."""
        screen_x, screen_y = self.position_calculator.grid_to_screen(grid_x, grid_y)
        left, top = int(round(screen_x)), int(round(screen_y))
        right = int(round(screen_x + self.position_calculator.cell_size_x))
        bottom = int(round(screen_y + self.position_calculator.cell_size_y))
        return (left, top, right - left, bottom - top)
    
    def face(self, grid: List[List[int]], cell: Tuple[int, int], side: Tuple[int, int],
             hit_points: int) -> WallSegment:
        """Create the wall segment for one face of a block.
        
        Args:
            grid: The maze grid, used to tell perimeter blocks apart.
            cell: Grid cell (x, y) of the block.
            side: Which face, as the offset to the cell it looks onto (one of SIDES).
            hit_points: Hit points the block has left.
            
        Returns:
            The WallSegment along that face, belonging to the block.
        """
        cell_size_x = self.position_calculator.cell_size_x
        cell_size_y = self.position_calculator.cell_size_y
        screen_x, screen_y = self.position_calculator.grid_to_screen(cell[0], cell[1])
        corners = {
            (0, -1): ((screen_x, screen_y), (screen_x + cell_size_x, screen_y)),
            (1, 0): ((screen_x + cell_size_x, screen_y), (screen_x + cell_size_x, screen_y + cell_size_y)),
            (0, 1): ((screen_x + cell_size_x, screen_y + cell_size_y), (screen_x, screen_y + cell_size_y)),
            (-1, 0): ((screen_x, screen_y + cell_size_y), (screen_x, screen_y)),
        }
        start, end = corners[side]
        return WallSegment(start, end, hit_points, not self.on_perimeter(grid, cell[0], cell[1]), cell)
