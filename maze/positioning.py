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
        self.cell_size_x, self.cell_size_y = self._calculate_cell_sizes()
        self.offset_x, self.offset_y = self._calculate_offsets()
    
    def _calculate_cell_sizes(self) -> Tuple[float, float]:
        """Calculate cell sizes to fill available space (left zone reserved for UI).
        
        Reserves left side for UI components (~220px), uses remaining width for maze.
        Uses 96% of screen height (UI is mostly at top). Calculates separate sizes
        for width and height to allow rectangular mazes.
        
        Returns:
            Tuple of (cell_size_x, cell_size_y) in pixels.
        """
        # Reserve left side for UI (gauges, indicators, etc.)
        UI_ZONE_WIDTH = 320
        PLAY_AREA_RIGHT_MARGIN = 30
        available_width = config.SCREEN_WIDTH - UI_ZONE_WIDTH
        available_height = config.SCREEN_HEIGHT * 0.96
        available_width -= PLAY_AREA_RIGHT_MARGIN
        cell_size_x = available_width / self.grid_width
        cell_size_y = available_height / self.grid_height
        return (cell_size_x, cell_size_y)
    
    def _calculate_offsets(self) -> Tuple[float, float]:
        """Calculate offsets to position maze on right side of screen.
        
        Maze is positioned starting from the UI zone width, creating a dedicated
        left zone for indicators.
        
        Returns:
            Tuple of (offset_x, offset_y) in pixels.
        """
        # Reserve left side for UI
        UI_ZONE_WIDTH = 320
        PLAY_AREA_RIGHT_MARGIN = 30
        total_maze_width = self.grid_width * self.cell_size_x
        total_maze_height = self.grid_height * self.cell_size_y
        # Position maze starting after UI zone, vertically centered
        offset_x = UI_ZONE_WIDTH
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
        screen_x = self.offset_x + grid_x * self.cell_size_x
        screen_y = self.offset_y + grid_y * self.cell_size_y
        return (screen_x, screen_y)
    
    def grid_center_to_screen(self, grid_x: int, grid_y: int) -> Tuple[float, float]:
        """Convert grid cell center to screen coordinates.
        
        Args:
            grid_x: Grid X coordinate.
            grid_y: Grid Y coordinate.
            
        Returns:
            Tuple of (screen_x, screen_y) for the center of the cell.
        """
        screen_x = self.offset_x + grid_x * self.cell_size_x + self.cell_size_x / 2
        screen_y = self.offset_y + grid_y * self.cell_size_y + self.cell_size_y / 2
        return (screen_x, screen_y)
    
    def screen_to_grid(self, screen_x: float, screen_y: float) -> Tuple[int, int]:
        """Convert screen coordinates to grid coordinates.
        
        Args:
            screen_x: Screen X coordinate.
            screen_y: Screen Y coordinate.
            
        Returns:
            Tuple of (grid_x, grid_y).
        """
        grid_x = int((screen_x - self.offset_x) / self.cell_size_x)
        grid_y = int((screen_y - self.offset_y) / self.cell_size_y)
        return (grid_x, grid_y)
    
    def get_start_position(self, start_grid: Tuple[int, int]) -> Tuple[float, float]:
        """Calculate start position with offset from corner edge.
        
        Args:
            start_grid: Grid coordinates (x, y) of the start corner.
            
        Returns:
            Tuple of (screen_x, screen_y) for the start position.
        """
        offset_distance_x = self.cell_size_x * config.SHIP_SPAWN_OFFSET
        offset_distance_y = self.cell_size_y * config.SHIP_SPAWN_OFFSET
        start_grid_x, start_grid_y = start_grid
        
        # Calculate offset direction based on which corner we're in
        if start_grid_x == 1:  # Left side
            offset_x = offset_distance_x
        else:  # Right side
            offset_x = -offset_distance_x
        
        if start_grid_y == 1:  # Top side
            offset_y = offset_distance_y
        else:  # Bottom side
            offset_y = -offset_distance_y
        
        center_x, center_y = self.grid_center_to_screen(start_grid_x, start_grid_y)
        return (center_x + offset_x, center_y + offset_y)


