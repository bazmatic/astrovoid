"""Procedural maze generation."""

import random
import pygame
from typing import List, Tuple, Set
import config
import utils


class Maze:
    """Procedurally generated maze."""
    
    def __init__(self, level: int):
        """Generate a maze for the given level."""
        self.level = level
        self.grid_width = config.BASE_MAZE_SIZE + (level - 1) * config.MAZE_SIZE_INCREMENT
        self.grid_height = self.grid_width
        
        # Calculate cell size to fill screen (leave some margin for UI)
        # Use 90% of screen for maze area
        available_width = config.SCREEN_WIDTH * 0.9
        available_height = config.SCREEN_HEIGHT * 0.9
        self.cell_size = min(
            available_width / self.grid_width,
            available_height / self.grid_height
        )
        
        # Center the maze on screen
        total_maze_width = self.grid_width * self.cell_size
        total_maze_height = self.grid_height * self.cell_size
        self.offset_x = (config.SCREEN_WIDTH - total_maze_width) / 2
        self.offset_y = (config.SCREEN_HEIGHT - total_maze_height) / 2
        
        # Generate maze grid
        self.grid = self._generate_maze()
        
        # Convert grid to wall segments
        self.walls = self._grid_to_walls()
        
        # Set start and exit positions
        self.start_pos = (
            self.offset_x + self.cell_size * 1.5,
            self.offset_y + self.cell_size * 1.5
        )
        exit_grid_x = self.grid_width - 2
        exit_grid_y = self.grid_height - 2
        self.exit_pos = (
            self.offset_x + exit_grid_x * self.cell_size + self.cell_size // 2,
            self.offset_y + exit_grid_y * self.cell_size + self.cell_size // 2
        )
        self.exit_radius = self.cell_size // 2
    
    def _generate_maze(self) -> List[List[int]]:
        """Generate maze using recursive backtracking algorithm with wider passages."""
        # Initialize grid: 1 = wall, 0 = path
        grid = [[1 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Start from (1, 1)
        stack = [(1, 1)]
        grid[1][1] = 0
        
        # Use much larger step size for very wide passages
        step_size = 5
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
                # Clear a MUCH wider area around the passage (3-4 cells in each direction)
                dx = next_x - current_x
                dy = next_y - current_y
                passage_width = 4  # Clear 4 cells wide on each side
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
                stack.append((next_x, next_y))
            else:
                # Backtrack
                stack.pop()
        
        # Ensure start and exit are clear with very wide area
        start_clear_size = 6
        for y in range(1, min(start_clear_size, self.grid_height - 1)):
            for x in range(1, min(start_clear_size, self.grid_width - 1)):
                grid[y][x] = 0
        
        exit_y_start = max(1, self.grid_height - start_clear_size)
        exit_x_start = max(1, self.grid_width - start_clear_size)
        for y in range(exit_y_start, self.grid_height - 1):
            for x in range(exit_x_start, self.grid_width - 1):
                grid[y][x] = 0
        
        # Add many more extra paths and clear large areas for much wider corridors
        for _ in range(self.level * 10):
            x = random.randint(2, self.grid_width - 3)
            y = random.randint(2, self.grid_height - 3)
            if grid[y][x] == 1:
                # Clear a large area around each removed wall
                clear_radius = 3
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
        
        return grid
    
    def _grid_to_walls(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """Convert grid to list of wall line segments."""
        walls = []
        wall_thickness = config.WALL_THICKNESS
        
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                if self.grid[y][x] == 1:  # Wall cell
                    # Convert grid coordinates to screen coordinates with offset
                    screen_x = self.offset_x + x * self.cell_size
                    screen_y = self.offset_y + y * self.cell_size
                    
                    # Create wall rectangle as line segments
                    # Top edge
                    walls.append((
                        (screen_x, screen_y),
                        (screen_x + self.cell_size, screen_y)
                    ))
                    # Right edge
                    walls.append((
                        (screen_x + self.cell_size, screen_y),
                        (screen_x + self.cell_size, screen_y + self.cell_size)
                    ))
                    # Bottom edge
                    walls.append((
                        (screen_x + self.cell_size, screen_y + self.cell_size),
                        (screen_x, screen_y + self.cell_size)
                    ))
                    # Left edge
                    walls.append((
                        (screen_x, screen_y + self.cell_size),
                        (screen_x, screen_y)
                    ))
        
        return walls
    
    def check_exit_reached(self, pos: Tuple[float, float], radius: float) -> bool:
        """Check if player reached the exit."""
        return utils.circle_circle_collision(pos, radius, self.exit_pos, self.exit_radius)
    
    def get_valid_spawn_positions(self, count: int, min_distance: float = 100) -> List[Tuple[float, float]]:
        """Get valid spawn positions for enemies, avoiding walls."""
        positions = []
        attempts = 0
        max_attempts = count * 50
        
        while len(positions) < count and attempts < max_attempts:
            attempts += 1
            
            # Random position in maze (with offset)
            x = random.uniform(
                self.offset_x + self.cell_size * 2,
                self.offset_x + (self.grid_width - 2) * self.cell_size
            )
            y = random.uniform(
                self.offset_y + self.cell_size * 2,
                self.offset_y + (self.grid_height - 2) * self.cell_size
            )
            pos = (x, y)
            
            # Check if too close to start or exit
            if (utils.distance(pos, self.start_pos) < min_distance or
                utils.distance(pos, self.exit_pos) < min_distance):
                continue
            
            # Check if too close to other spawns
            too_close = False
            for existing_pos in positions:
                if utils.distance(pos, existing_pos) < min_distance:
                    too_close = True
                    break
            if too_close:
                continue
            
            # Check if position is in a wall
            in_wall = False
            for wall in self.walls:
                if utils.circle_line_collision(pos, 15, wall[0], wall[1]):
                    in_wall = True
                    break
            if in_wall:
                continue
            
            positions.append(pos)
        
        return positions
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the maze."""
        # Draw filled wall boxes
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                if self.grid[y][x] == 1:  # Wall cell
                    # Convert grid coordinates to screen coordinates with offset
                    screen_x = int(self.offset_x + x * self.cell_size)
                    screen_y = int(self.offset_y + y * self.cell_size)
                    
                    # Draw filled rectangle for wall cell
                    pygame.draw.rect(
                        screen,
                        config.COLOR_WALLS,
                        (screen_x, screen_y, int(self.cell_size), int(self.cell_size))
                    )
        
        # Draw exit marker
        pygame.draw.circle(screen, config.COLOR_EXIT, 
                          (int(self.exit_pos[0]), int(self.exit_pos[1])), 
                          int(self.exit_radius))
        pygame.draw.circle(screen, config.COLOR_TEXT, 
                          (int(self.exit_pos[0]), int(self.exit_pos[1])), 
                          int(self.exit_radius), 2)

