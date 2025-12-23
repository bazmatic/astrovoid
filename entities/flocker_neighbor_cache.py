"""Shared neighbor cache for efficient flocker flocking calculations.

This module provides a shared data structure that pre-computes neighbor relationships
for all flockers once per frame, reducing computational complexity from O(n²) to O(n).
"""

from typing import List, Dict, Tuple, TYPE_CHECKING
import math
import config

if TYPE_CHECKING:
    from entities.flocker_enemy_ship import FlockerEnemyShip


class FlockerNeighborCache:
    """Shared cache for flocker neighbor calculations.
    
    Pre-computes neighbor lists for all flockers to avoid O(n²) complexity.
    Uses spatial hashing for efficient neighbor queries.
    """
    
    def __init__(self):
        """Initialize the neighbor cache."""
        self.cache: Dict[int, List[Tuple['FlockerEnemyShip', float]]] = {}
        self.max_radius: float = max(
            config.FLOCKER_ENEMY_SEPARATION_RADIUS,
            config.FLOCKER_ENEMY_ALIGNMENT_RADIUS,
            config.FLOCKER_ENEMY_COHESION_RADIUS
        )
        # Use cell size based on max radius for spatial hashing
        self.cell_size: float = self.max_radius * 2.0
    
    def update(self, flockers: List['FlockerEnemyShip']) -> None:
        """Update the neighbor cache for all active flockers.
        
        Args:
            flockers: List of all flocker ships.
        """
        # Clear previous cache
        self.cache.clear()
        
        # Build spatial hash grid
        # Calculate grid dimensions based on screen size
        grid_cols = int(config.SCREEN_WIDTH / self.cell_size) + 1
        grid_rows = int(config.SCREEN_HEIGHT / self.cell_size) + 1
        
        # Create grid: each cell contains list of (flocker, index) tuples
        grid: List[List[List[Tuple['FlockerEnemyShip', int]]]] = [
            [[] for _ in range(grid_cols)]
            for _ in range(grid_rows)
        ]
        
        # Place flockers in grid cells
        active_flockers: List[Tuple['FlockerEnemyShip', int]] = []
        for idx, flocker in enumerate(flockers):
            if not flocker.active:
                continue
            
            active_flockers.append((flocker, idx))
            
            # Calculate grid cell
            col = max(0, min(grid_cols - 1, int(flocker.x / self.cell_size)))
            row = max(0, min(grid_rows - 1, int(flocker.y / self.cell_size)))
            
            # Add to grid cell
            grid[row][col].append((flocker, idx))
        
        # For each flocker, find neighbors by checking nearby grid cells
        for flocker, idx in active_flockers:
            neighbors: List[Tuple['FlockerEnemyShip', float]] = []
            
            # Calculate which grid cells to check (3x3 area around flocker's cell)
            col = max(0, min(grid_cols - 1, int(flocker.x / self.cell_size)))
            row = max(0, min(grid_rows - 1, int(flocker.y / self.cell_size)))
            
            # Check 3x3 grid of cells around the flocker
            for check_row in range(max(0, row - 1), min(grid_rows, row + 2)):
                for check_col in range(max(0, col - 1), min(grid_cols, col + 2)):
                    for other_flocker, other_idx in grid[check_row][check_col]:
                        # Skip self
                        if other_idx == idx:
                            continue
                        
                        # Calculate distance squared (avoid sqrt until needed)
                        dx = flocker.x - other_flocker.x
                        dy = flocker.y - other_flocker.y
                        dist_sq = dx * dx + dy * dy
                        
                        # Only add if within max radius
                        max_radius_sq = self.max_radius * self.max_radius
                        if dist_sq > 0.0 and dist_sq < max_radius_sq:
                            dist = math.sqrt(dist_sq)
                            neighbors.append((other_flocker, dist))
            
            # Store neighbors for this flocker
            self.cache[idx] = neighbors
    
    def get_neighbors(
        self,
        flocker_idx: int,
        radius: float
    ) -> List[Tuple['FlockerEnemyShip', float]]:
        """Get neighbors within specified radius for a flocker.
        
        Args:
            flocker_idx: Index of the flocker in the original list.
            radius: Maximum distance to consider as neighbor.
            
        Returns:
            List of (neighbor_flocker, distance) tuples within radius.
        """
        if flocker_idx not in self.cache:
            return []
        
        radius_sq = radius * radius
        neighbors = []
        
        for neighbor, dist in self.cache[flocker_idx]:
            if dist * dist < radius_sq:
                neighbors.append((neighbor, dist))
        
        return neighbors

