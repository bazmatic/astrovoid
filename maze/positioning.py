"""Maze position calculations.

This module provides position calculation utilities for converting between
grid coordinates and screen coordinates.
"""

from typing import Tuple
import config


class MazePositionCalculator:
    """Handles all position calculations for maze rendering and positioning."""
    
    def __init__(self, grid_width: int, grid_height: int):
        """Initialize position calculator.
        
        Args:
            grid_width: Width of the maze grid in cells.
            grid_height: Height of the maze grid in cells.
        """
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.cell_size = self._calculate_cell_size()
        self.offset_x, self.offset_y = self._calculate_offsets()
    
    def _calculate_cell_size(self) -> float:
        """Calculate cell size to fill screen (leave some margin for UI).
        
        Uses 90% of screen for maze area.
        
        Returns:
            Cell size in pixels.
        """
        available_width = config.SCREEN_WIDTH * 0.9
        available_height = config.SCREEN_HEIGHT * 0.9
        return min(
            available_width / self.grid_width,
            available_height / self.grid_height
        )
    
    def _calculate_offsets(self) -> Tuple[float, float]:
        """Calculate offsets to center the maze on screen.
        
        Returns:
            Tuple of (offset_x, offset_y) in pixels.
        """
        total_maze_width = self.grid_width * self.cell_size
        total_maze_height = self.grid_height * self.cell_size
        offset_x = (config.SCREEN_WIDTH - total_maze_width) / 2
        offset_y = (config.SCREEN_HEIGHT - total_maze_height) / 2
        return (offset_x, offset_y)
    
    def grid_to_screen(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid coordinates to screen coordinates.
        
        Args:
            grid_x: Grid X coordinate.
            grid_y: Grid Y coordinate.
            
        Returns:
            Tuple of (screen_x, screen_y) in pixels.
        """
        screen_x = self.offset_x + grid_x * self.cell_size
        screen_y = self.offset_y + grid_y * self.cell_size
        return (screen_x, screen_y)
    
    def grid_center_to_screen(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid cell center to screen coordinates.
        
        Args:
            grid_x: Grid X coordinate.
            grid_y: Grid Y coordinate.
            
        Returns:
            Tuple of (screen_x, screen_y) for the center of the cell.
        """
        screen_x = self.offset_x + grid_x * self.cell_size + self.cell_size // 2
        screen_y = self.offset_y + grid_y * self.cell_size + self.cell_size // 2
        return (screen_x, screen_y)
    
    def screen_to_grid(self, screen_x: float, screen_y: float) -> Tuple[int, int]:
        """Convert screen coordinates to grid coordinates.
        
        Args:
            screen_x: Screen X coordinate.
            screen_y: Screen Y coordinate.
            
        Returns:
            Tuple of (grid_x, grid_y).
        """
        grid_x = int((screen_x - self.offset_x) / self.cell_size)
        grid_y = int((screen_y - self.offset_y) / self.cell_size)
        return (grid_x, grid_y)
    
    def get_start_position(self, start_grid: Tuple[int, int]) -> Tuple[float, float]:
        """Calculate start position with offset from corner edge.
        
        Args:
            start_grid: Grid coordinates (x, y) of the start corner.
            
        Returns:
            Tuple of (screen_x, screen_y) for the start position.
        """
        offset_distance = self.cell_size * config.SHIP_SPAWN_OFFSET
        start_grid_x, start_grid_y = start_grid
        
        # Calculate offset direction based on which corner we're in
        if start_grid_x == 1:  # Left side
            offset_x = offset_distance
        else:  # Right side
            offset_x = -offset_distance
        
        if start_grid_y == 1:  # Top side
            offset_y = offset_distance
        else:  # Bottom side
            offset_y = -offset_distance
        
        center_x, center_y = self.grid_center_to_screen(start_grid_x, start_grid_y)
        return (center_x + offset_x, center_y + offset_y)

