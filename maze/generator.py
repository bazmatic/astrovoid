"""Procedural maze generation."""

import random
import pygame
import math
from typing import List, Tuple, Set, Dict, Optional
import config
from utils import (
    distance,
    distance_squared,
    get_angle_to_point,
    point_in_rect,
    circle_circle_collision,
    circle_line_collision
)
from maze.wall_segment import WallSegment
from maze.config import MazeComplexity, MazeGenerationConfig, MazeComplexityPresets
from maze.positioning import MazePositionCalculator
from maze.converter import GridToWallsConverter, SIDES
from utils.spatial_grid import SpatialGrid
from entities.exit import ExitPortal
from rendering.wall_renderer import WallRenderer
from rendering.wall_debris import WallDebris


class RecursiveBacktrackingGenerator:
    """Generates mazes using recursive backtracking algorithm."""
    
    def __init__(self, config: MazeGenerationConfig, grid_width: int, grid_height: int, level: int):
        """Initialize generator.
        
        Args:
            config: Generation configuration parameters.
            grid_width: Width of the maze grid in cells.
            grid_height: Height of the maze grid in cells.
            level: Current level number (used for extra paths calculation).
        """
        self.config = config
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.level = level
    
    def generate(self) -> List[List[int]]:
        """Generate maze grid.
        
        Returns:
            2D grid where 1 = wall, 0 = path.
        """
        # Special case: EMPTY complexity = perimeter only, no obstacles
        if (self.config.extra_paths_multiplier == 0 and 
            self.config.passage_width == 0 and 
            self.config.clear_radius == 0):
            return self._generate_empty_maze()
        
        # Initialize grid: 1 = wall, 0 = path
        grid = [[1 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Start from (1, 1)
        stack = [(1, 1)]
        grid[1][1] = 0
        
        # Directions based on step size
        step_size = self.config.step_size
        directions = [(0, step_size), (step_size, 0), (0, -step_size), (-step_size, 0)]
        
        while stack:
            current_x, current_y = stack[-1]
            
            # Find unvisited neighbors
            neighbors = []
            random.shuffle(directions)
            for dx, dy in directions:
                nx, ny = current_x + dx, current_y + dy
                if (0 < nx < self.grid_width - 1 and 
                    0 < ny < self.grid_height - 1 and 
                    grid[ny][nx] == 1):
                    # Clear path between cells (wider passage)
                    wall_x = current_x + dx // step_size
                    wall_y = current_y + dy // step_size
                    neighbors.append((nx, ny, wall_x, wall_y))
            
            if neighbors:
                # Choose random neighbor
                next_x, next_y, wall_x, wall_y = random.choice(neighbors)
                grid[next_y][next_x] = 0
                # Clear the wall between cells
                grid[wall_y][wall_x] = 0
                # Clear wider area around the passage
                self._clear_passage(grid, current_x, current_y, next_x, next_y, wall_x, wall_y)
                stack.append((next_x, next_y))
            else:
                # Backtrack
                stack.pop()
        
        # Add extra paths
        self._add_extra_paths(grid)
        
        # Ensure perimeter is always walls
        self._ensure_perimeter(grid)
        
        return grid
    
    def _generate_empty_maze(self) -> List[List[int]]:
        """Generate an empty maze with only perimeter walls.
        
        Returns:
            2D grid where 1 = wall (perimeter only), 0 = path (everything else).
        """
        # Initialize grid: all paths (0)
        grid = [[0 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Set perimeter to walls
        self._ensure_perimeter(grid)
        
        return grid
    
    def _clear_passage(self, grid: List[List[int]], current_x: int, current_y: int,
                       next_x: int, next_y: int, wall_x: int, wall_y: int) -> None:
        """Clear a wide area around a passage connection.
        
        Args:
            grid: The maze grid to modify.
            current_x: Current cell X coordinate.
            current_y: Current cell Y coordinate.
            next_x: Next cell X coordinate.
            next_y: Next cell Y coordinate.
            wall_x: Wall X coordinate.
            wall_y: Wall Y coordinate.
        """
        dx = next_x - current_x
        dy = next_y - current_y
        passage_width = self.config.passage_width
        
        if dx != 0:
            # Horizontal movement - clear wide vertical strip
            for offset_y in range(-passage_width, passage_width + 1):
                check_y = wall_y + offset_y
                if 0 <= check_y < self.grid_height:
                    # Clear multiple cells horizontally too
                    for offset_x in range(-1, 2):
                        check_x = wall_x + offset_x
                        if 0 <= check_x < self.grid_width:
                            grid[check_y][check_x] = 0
        if dy != 0:
            # Vertical movement - clear wide horizontal strip
            for offset_x in range(-passage_width, passage_width + 1):
                check_x = wall_x + offset_x
                if 0 <= check_x < self.grid_width:
                    # Clear multiple cells vertically too
                    for offset_y in range(-1, 2):
                        check_y = wall_y + offset_y
                        if 0 <= check_y < self.grid_height:
                            grid[check_y][check_x] = 0
    
    def _add_extra_paths(self, grid: List[List[int]]) -> None:
        """Add extra paths to make corridors wider.
        
        Args:
            grid: The maze grid to modify.
        """
        num_extra_paths = self.level * self.config.extra_paths_multiplier
        clear_radius = self.config.clear_radius
        
        for _ in range(num_extra_paths):
            x = random.randint(2, self.grid_width - 3)
            y = random.randint(2, self.grid_height - 3)
            if grid[y][x] == 1:
                # Clear a large area around each removed wall
                for dy in range(-clear_radius, clear_radius + 1):
                    for dx in range(-clear_radius, clear_radius + 1):
                        check_y = y + dy
                        check_x = x + dx
                        if (0 <= check_y < self.grid_height and 
                            0 <= check_x < self.grid_width):
                            # Higher chance to clear cells closer to center
                            distance = abs(dx) + abs(dy)
                            if distance <= clear_radius and random.random() < (1.0 - distance * 0.2):
                                grid[check_y][check_x] = 0
    
    def _ensure_perimeter(self, grid: List[List[int]]) -> None:
        """Ensure perimeter is always walls.
        
        Args:
            grid: The maze grid to modify.
        """
        # Top and bottom rows
        for x in range(self.grid_width):
            grid[0][x] = 1  # Top row
            grid[self.grid_height - 1][x] = 1  # Bottom row
        
        # Left and right columns
        for y in range(self.grid_height):
            grid[y][0] = 1  # Left column
            grid[y][self.grid_width - 1] = 1  # Right column
    
    def clear_corner_area(self, grid: List[List[int]], corner: Tuple[int, int]) -> None:
        """Clear a wide area around a corner to ensure it's accessible.
        
        Args:
            grid: The maze grid to modify.
            corner: Grid coordinates (x, y) of the corner to clear around.
        """
        clear_size = self.config.corner_clear_size
        corner_x, corner_y = corner
        
        # Clear area around the corner, ensuring we stay within bounds
        for y in range(max(1, corner_y - clear_size // 2), 
                      min(corner_y + clear_size // 2 + 1, self.grid_height - 1)):
            for x in range(max(1, corner_x - clear_size // 2),
                          min(corner_x + clear_size // 2 + 1, self.grid_width - 1)):
                grid[y][x] = 0
        
        # Validate that the corner itself is in a clear path cell
        if grid[corner_y][corner_x] != 0:
            # Force clear the corner cell if it's still a wall
            grid[corner_y][corner_x] = 0


class Maze:
    """Procedurally generated maze."""
    
    def __init__(self, level: int, complexity: Optional[MazeComplexity] = None, grid_size: int = 0):
        """Generate a maze for the given level.
        
        Args:
            level: Current level number (1-based).
            complexity: Optional maze complexity level. If None, calculated from level.
            grid_size: Grid size (width/height in cells). Always provided by level_config.get_maze_grid_size().
        """
        self.level = level
        
        # Determine complexity
        if complexity is None:
            complexity = MazeComplexityPresets.get_complexity_from_level(level)
        
        # Get generation config
        gen_config = MazeComplexityPresets.get_config(complexity)
        
        # Set grid dimensions (grid_size is already calculated in level_config if None was passed)
        self.grid_width = grid_size
        self.grid_height = grid_size
        
        # Create position calculator
        self.position_calculator = MazePositionCalculator(self.grid_width, self.grid_height)
        self.cell_size_x = self.position_calculator.cell_size_x
        self.cell_size_y = self.position_calculator.cell_size_y
        # Keep cell_size property for backward compatibility (use average)
        self.cell_size = (self.cell_size_x + self.cell_size_y) / 2
        self.offset_x = self.position_calculator.offset_x
        self.offset_y = self.position_calculator.offset_y
        
        # Generate maze grid
        generator = RecursiveBacktrackingGenerator(gen_config, self.grid_width, self.grid_height, level)
        self.grid = generator.generate()
        
        # Select random opposite corners for start and exit
        corner_combinations = [
            ((1, 1), (self.grid_width - 2, self.grid_height - 2)),  # TL -> BR
            ((self.grid_width - 2, 1), (1, self.grid_height - 2)),  # TR -> BL
            ((1, self.grid_height - 2), (self.grid_width - 2, 1)),  # BL -> TR
            ((self.grid_width - 2, self.grid_height - 2), (1, 1)),  # BR -> TL
        ]
        start_grid, exit_grid = random.choice(corner_combinations)
        
        # Clear areas around selected corners to ensure they're accessible
        generator.clear_corner_area(self.grid, start_grid)
        generator.clear_corner_area(self.grid, exit_grid)
        
        # Convert grid to blocks and their wall segments
        self.converter = GridToWallsConverter(self.position_calculator)
        self.wall_renderer = WallRenderer()
        self.wall_debris = WallDebris()
        # Spatial grid for efficient collision detection
        self.spatial_grid = SpatialGrid(
            config.SCREEN_WIDTH,
            config.SCREEN_HEIGHT,
            cell_size=150.0  # Optimal cell size for this game
        )
        self.wall_generation = 0  # Goes up each time a block is destroyed
        self.rebuild_walls()
        
        # Set start position
        self.start_pos = self.position_calculator.get_start_position(start_grid)
        
        # Create exit object
        exit_pos = self.position_calculator.grid_center_to_screen(exit_grid[0], exit_grid[1])
        # Use average cell size for exit radius
        exit_radius = (self.cell_size_x + self.cell_size_y) / 4
        self.exit = ExitPortal(exit_pos, exit_radius)
    
    def check_exit_reached(self, pos: Tuple[float, float], radius: float) -> bool:
        """Check if player reached the exit."""
        return self.exit.check_circle_collision(pos, radius)
    
    def rebuild_walls(self) -> None:
        """Build the blocks, their exposed faces and the collision index from the grid."""
        self.walls = self.converter.convert(self.grid)
        # Hit points left in each wall block, keyed by grid cell (x, y). A
        # block is solid rock: shots at any of its faces wear down the block
        self.blocks: Dict[Tuple[int, int], int] = {
            (x, y): config.WALL_HIT_POINTS
            for y, row in enumerate(self.grid) for x, value in enumerate(row) if value == 1
        }
        # Where each block has been hit, as points on its edge, oldest first
        self.wounds: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        self.spatial_grid.add_walls(self.walls)
        self._refresh_block_fills()
    
    def _refresh_block_fills(self) -> None:
        """Rebuild the screen areas of the blocks, which the renderer fills with rock."""
        self.block_fills = {self.converter.cell_rect(x, y): hit_points for (x, y), hit_points in self.blocks.items()}
        self.block_wounds = {self.converter.cell_rect(x, y): tuple(wounds) for (x, y), wounds in self.wounds.items()}
    
    @staticmethod
    def _wound(wall: WallSegment, impact: Optional[Tuple[float, float]]) -> Tuple[int, int]:
        """The point on a face nearest to where a shot landed; its middle if that is unknown."""
        (ax, ay), (bx, by) = wall.start, wall.end
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        along = 0.5
        if impact is not None and length_sq > 0:
            along = ((impact[0] - ax) * dx + (impact[1] - ay) * dy) / length_sq
        # Kept off the very corner, which belongs to the neighbouring side as much as this one
        inset = min(0.5, 3.0 / math.sqrt(length_sq)) if length_sq > 0 else 0.5
        along = max(inset, min(1.0 - inset, along))
        return (int(round(ax + dx * along)), int(round(ay + dy * along)))
    
    def damage_wall(self, wall: WallSegment, impact: Optional[Tuple[float, float]] = None) -> bool:
        """Damage the block a wall segment is a face of. Returns True if the block was destroyed.
        
        The whole block goes at once, and the faces of its neighbours that
        looked onto it become walls. Either way the shot knocks rock loose.
        
        Args:
            wall: The wall segment that was hit.
            impact: Where the shot landed, for the chips it knocks off.
            
        Returns:
            True if the block was destroyed (hit points reached 0), False otherwise.
        """
        if wall not in self.walls or not wall.destructible:
            return False
        
        cell = wall.cell
        if cell not in self.blocks:
            # A loose segment that belongs to no block
            destroyed = wall.damage()
            if destroyed:
                self.spatial_grid.update_wall(wall)
                self.walls = [w for w in self.walls if w.active]
            return destroyed
        
        faces = [w for w in self.walls if w.cell == cell]
        hit_points = self.blocks[cell] - 1
        for face in faces:
            face.hit_points = hit_points
        if hit_points > 0:
            self.blocks[cell] = hit_points
            self.wounds.setdefault(cell, []).append(self._wound(wall, impact))
            self._refresh_block_fills()
            self.wall_debris.hit(self.converter.cell_rect(*cell), impact)
            return False
        
        del self.blocks[cell]
        self.wounds.pop(cell, None)
        self.wall_debris.destroy(self.converter.cell_rect(*cell))
        self.grid[cell[1]][cell[0]] = 0
        for face in faces:
            face.active = False
            self.spatial_grid.update_wall(face)
        self.walls = [w for w in self.walls if w.active]
        # Neighbouring blocks now have a face onto the gap
        for dx, dy in SIDES:
            neighbour = (cell[0] + dx, cell[1] + dy)
            if neighbour in self.blocks:
                face = self.converter.face(self.grid, neighbour, (-dx, -dy), self.blocks[neighbour])
                self.walls.append(face)
                self.spatial_grid.add_wall(face)
        self.wall_generation += 1
        self._refresh_block_fills()
        return True
    
    def get_valid_spawn_positions(self, count: int, min_distance: float = 100,
                                  start_clearance: Optional[float] = None) -> List[Tuple[float, float]]:
        """Get valid spawn positions for enemies, avoiding walls.
        
        Args:
            count: Number of positions wanted.
            min_distance: Minimum distance between positions, and from the exit.
            start_clearance: Minimum distance from the player's start (defaults to min_distance).
        
        When the maze is too full to fit them all, positions are packed closer together;
        the distances from the start and the exit are never reduced.
        """
        if start_clearance is None:
            start_clearance = min_distance
        start_clearance_sq = start_clearance * start_clearance
        min_distance_sq = min_distance * min_distance
        spacing_sq = min_distance_sq
        positions = []
        attempts = 0
        max_attempts = count * 50
        
        while len(positions) < count:
            if attempts >= max_attempts:
                # Out of room at this spacing: pack the rest closer, down to half the spacing
                spacing_sq *= 0.64
                if spacing_sq < min_distance_sq * 0.25:
                    break
                attempts = 0
            attempts += 1
            
            # Random position in maze (with offset)
            x = random.uniform(
                self.offset_x + self.cell_size_x * 2,
                self.offset_x + (self.grid_width - 2) * self.cell_size_x
            )
            y = random.uniform(
                self.offset_y + self.cell_size_y * 2,
                self.offset_y + (self.grid_height - 2) * self.cell_size_y
            )
            pos = (x, y)
            
            # Check if too close to start or exit (use squared distance for comparison)
            exit_pos = self.exit.get_pos()
            if (distance_squared(pos, self.start_pos) < start_clearance_sq or
                distance_squared(pos, exit_pos) < min_distance_sq):
                continue
            
            # Check if too close to other spawns
            too_close = False
            for existing_pos in positions:
                if distance_squared(pos, existing_pos) < spacing_sq:
                    too_close = True
                    break
            if too_close:
                continue
            
            # Check if position is inside a block
            cell = (int((x - self.offset_x) // self.cell_size_x), int((y - self.offset_y) // self.cell_size_y))
            if cell in self.blocks:
                continue
            
            # Check if position is in a wall
            in_wall = False
            for wall in self.walls:
                if wall.active:
                    segment = wall.get_segment()
                    if circle_line_collision(pos, 15, segment[0], segment[1]):
                        in_wall = True
                        break
            if in_wall:
                continue
            
            positions.append(pos)
        
        return positions
    
    def update(self, dt: float) -> None:
        """Advance the rock knocked loose by shots."""
        self.wall_debris.update(dt)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the maze."""
        self.wall_renderer.draw(screen, self.walls, blocks=self.block_fills, wounds=self.block_wounds)
        self.wall_debris.draw(screen)
        
        # Draw exit marker
        if self.exit.active:
            self.exit.draw(screen)

