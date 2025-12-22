"""Spatial partitioning grid for efficient collision detection.

This module provides a grid-based spatial partitioning system to reduce
the number of collision checks from O(n*m) to O(k) where k is the number
of entities in nearby grid cells.
"""

from typing import List, Tuple, Set
import config


class SpatialGrid:
    """Grid-based spatial partition for collision detection optimization.
    
    Divides the game space into a grid of cells. Each wall is assigned to
    the cells it overlaps with, allowing entities to only check walls
    in nearby cells instead of all walls.
    """
    
    def __init__(self, width: float, height: float, cell_size: float = 100.0):
        """Initialize spatial grid.
        
        Args:
            width: Total width of the game space.
            height: Total height of the game space.
            cell_size: Size of each grid cell (default: 100 pixels).
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        
        # Calculate grid dimensions
        self.grid_cols = int(width / cell_size) + 1
        self.grid_rows = int(height / cell_size) + 1
        
        # Grid: list of sets, each set contains wall indices
        # Using indices instead of wall objects for efficiency
        self.grid: List[List[Set[int]]] = [
            [set() for _ in range(self.grid_cols)]
            for _ in range(self.grid_rows)
        ]
        
        # Store all walls with their indices
        self.walls: List = []
        self.wall_to_index: dict = {}
    
    def clear(self) -> None:
        """Clear all walls from the grid."""
        for row in self.grid:
            for cell in row:
                cell.clear()
        self.walls.clear()
        self.wall_to_index.clear()
    
    def add_walls(self, walls: List) -> None:
        """Add walls to the spatial grid.
        
        Args:
            walls: List of wall segments (WallSegment instances or tuples).
        """
        self.clear()
        
        for wall in walls:
            # Handle both WallSegment and tuple formats
            if hasattr(wall, 'get_segment'):
                if not wall.active:
                    continue
                segment = wall.get_segment()
            else:
                segment = wall
            
            # Add wall to storage
            wall_index = len(self.walls)
            self.walls.append(wall)
            self.wall_to_index[wall] = wall_index
            
            # Find all grid cells this wall overlaps with
            cells = self._get_cells_for_line(segment[0], segment[1])
            for row, col in cells:
                if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
                    self.grid[row][col].add(wall_index)
    
    def get_nearby_walls(
        self,
        pos: Tuple[float, float],
        radius: float
    ) -> List:
        """Get walls that are potentially colliding with an entity.
        
        Args:
            pos: Entity position (x, y).
            radius: Entity collision radius.
            
        Returns:
            List of walls that might be colliding (need further collision check).
        """
        # Calculate bounding box around entity
        min_x = pos[0] - radius
        max_x = pos[0] + radius
        min_y = pos[1] - radius
        max_y = pos[1] + radius
        
        # Get grid cells that overlap with bounding box
        min_col = max(0, int(min_x / self.cell_size))
        max_col = min(self.grid_cols - 1, int(max_x / self.cell_size))
        min_row = max(0, int(min_y / self.cell_size))
        max_row = min(self.grid_rows - 1, int(max_y / self.cell_size))
        
        # Collect unique wall indices from overlapping cells
        wall_indices: Set[int] = set()
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                wall_indices.update(self.grid[row][col])
        
        # Return actual wall objects
        return [self.walls[i] for i in wall_indices]
    
    def get_walls_along_path(
        self,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float],
        radius: float
    ) -> List:
        """Get walls that might intersect with a swept path.
        
        This method queries walls along the entire movement path, not just
        at the end position. This prevents tunneling through walls during
        large movements or high-speed scenarios.
        
        Args:
            start_pos: Starting position (x, y).
            end_pos: Ending position (x, y).
            radius: Entity collision radius.
            
        Returns:
            List of walls that might intersect the swept path.
        """
        # Calculate bounding box that covers entire movement path
        # Include radius on all sides to account for entity size
        min_x = min(start_pos[0], end_pos[0]) - radius
        max_x = max(start_pos[0], end_pos[0]) + radius
        min_y = min(start_pos[1], end_pos[1]) - radius
        max_y = max(start_pos[1], end_pos[1]) + radius
        
        # Get grid cells that overlap with the expanded bounding box
        min_col = max(0, int(min_x / self.cell_size))
        max_col = min(self.grid_cols - 1, int(max_x / self.cell_size))
        min_row = max(0, int(min_y / self.cell_size))
        max_row = min(self.grid_rows - 1, int(max_y / self.cell_size))
        
        # Collect unique wall indices from overlapping cells
        wall_indices: Set[int] = set()
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                wall_indices.update(self.grid[row][col])
        
        # Return actual wall objects
        return [self.walls[i] for i in wall_indices]
    
    def _get_cells_for_line(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float]
    ) -> List[Tuple[int, int]]:
        """Get all grid cells that a line segment passes through.
        
        Uses Bresenham-like algorithm to find all cells the line touches.
        
        Args:
            start: Line start point (x, y).
            end: Line end point (x, y).
            
        Returns:
            List of (row, col) tuples for cells the line passes through.
        """
        x1, y1 = start
        x2, y2 = end
        
        # Get cell coordinates
        col1 = int(x1 / self.cell_size)
        row1 = int(y1 / self.cell_size)
        col2 = int(x2 / self.cell_size)
        row2 = int(y2 / self.cell_size)
        
        cells = set()
        
        # Add start and end cells
        cells.add((row1, col1))
        cells.add((row2, col2))
        
        # If line is mostly horizontal or vertical, add intermediate cells
        dx = abs(col2 - col1)
        dy = abs(row2 - row1)
        
        if dx > dy:
            # Horizontal line - iterate through columns
            if col1 > col2:
                col1, col2 = col2, col1
                row1, row2 = row2, row1
            for col in range(col1, col2 + 1):
                # Calculate row at this column
                if col2 != col1:
                    t = (col - col1) / (col2 - col1)
                    row = int(row1 + (row2 - row1) * t)
                    cells.add((row, col))
        else:
            # Vertical line - iterate through rows
            if row1 > row2:
                row1, row2 = row2, row1
                col1, col2 = col2, col1
            for row in range(row1, row2 + 1):
                # Calculate column at this row
                if row2 != row1:
                    t = (row - row1) / (row2 - row1)
                    col = int(col1 + (col2 - col1) * t)
                    cells.add((row, col))
        
        return list(cells)
    
    def update_wall(self, wall) -> None:
        """Update a wall's position in the grid (e.g., when it's destroyed).
        
        Args:
            wall: The wall segment to update.
        """
        if wall not in self.wall_to_index:
            return
        
        wall_index = self.wall_to_index[wall]
        
        # Remove from all cells
        for row in self.grid:
            for cell in row:
                cell.discard(wall_index)
        
        # Re-add if still active
        if hasattr(wall, 'active') and wall.active:
            if hasattr(wall, 'get_segment'):
                segment = wall.get_segment()
            else:
                segment = wall
            
            cells = self._get_cells_for_line(segment[0], segment[1])
            for row, col in cells:
                if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
                    self.grid[row][col].add(wall_index)


