"""Procedural maze generation."""

import random
import pygame
import math
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
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
    """Carve a connected room graph, then expand it into broad, aligned corridors.

    Visiting logical rooms separately from the rendered grid prevents wide passages
    from accidentally marking neighbouring rooms as visited. Extra routes join rooms
    through whole doorways instead of eroding random patches of masonry.
    """

    def __init__(self, config: MazeGenerationConfig, grid_width: int, grid_height: int, level: int):
        self.config = config
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.level = level

    def generate(self) -> List[List[int]]:
        grid = [[1 for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        empty = (self.config.extra_paths_multiplier == 0 and
                 self.config.passage_width == 0 and self.config.clear_radius == 0)
        if empty:
            self._clear(grid, 1, 1, self.grid_width-1, self.grid_height-1)
            return grid

        # Later complexity presets create more junctions, never narrower than a
        # comfortable flight corridor. Distribute spare cells evenly at the edges.
        position = MazePositionCalculator(self.grid_width, self.grid_height)
        room_width = max(3, 7-self.config.step_size//2)
        xs = self._bands(self.grid_width, max(room_width, math.ceil(70/position.cell_size_x)))
        ys = self._bands(self.grid_height, max(room_width, math.ceil(70/position.cell_size_y)))
        rooms = [(x,y) for y in range(len(ys)) for x in range(len(xs))]
        for x,y in rooms:
            self._clear(grid, xs[x][0], ys[y][0], xs[x][1], ys[y][1])

        def neighbours(room):
            x,y = room
            return [(nx,ny) for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
                    if 0 <= nx < len(xs) and 0 <= ny < len(ys)]

        def connect(a,b):
            x,y = a
            nx,ny = b
            if x != nx:
                wall = xs[min(x,nx)][1]
                self._clear(grid, wall, ys[y][0], wall+1, ys[y][1])
            else:
                wall = ys[min(y,ny)][1]
                self._clear(grid, xs[x][0], wall, xs[x][1], wall+1)

        start = random.choice(rooms)
        visited = {start}
        stack = [start]
        passages = set()
        while stack:
            current = stack[-1]
            choices = [room for room in neighbours(current) if room not in visited]
            if not choices:
                stack.pop()
                continue
            following = random.choice(choices)
            connect(current,following)
            passages.add(frozenset((current,following)))
            visited.add(following)
            stack.append(following)

        # A few deliberate shortcuts support combat and flanking. Never remove
        # all four sides around a junction: that would leave a lonely square block.
        closed = [(a,b) for a in rooms for b in neighbours(a)
                  if a < b and frozenset((a,b)) not in passages]
        random.shuffle(closed)
        budget = round(len(rooms)/(self.config.clear_radius+2))
        for a,b in closed:
            if budget <= 0:
                break
            edge = frozenset((a,b))
            passages.add(edge)
            if self._isolates_pillar(passages,a,b):
                passages.remove(edge)
                continue
            connect(a,b)
            budget -= 1
        return grid

    @staticmethod
    def _bands(size, minimum):
        """Half-open room intervals separated by exactly one wall cell."""
        interior = size-2
        count = max(1,(interior+1)//(minimum+1))
        available = interior-(count-1)
        width,remainder = divmod(available,count)
        bands=[]
        start=1
        for index in range(count):
            end=start+width+(index < remainder)
            bands.append((start,end))
            start=end+1
        return bands

    @staticmethod
    def _isolates_pillar(passages,a,b):
        for x in range(min(a[0],b[0])-1,max(a[0],b[0])+1):
            for y in range(min(a[1],b[1])-1,max(a[1],b[1])+1):
                cycle=((x,y),(x+1,y),(x+1,y+1),(x,y+1))
                if all(frozenset((cycle[i],cycle[(i+1)%4])) in passages for i in range(4)):
                    return True
        return False

    @staticmethod
    def _clear(grid,x0,y0,x1,y1):
        for y in range(y0,y1):
            for x in range(x0,x1):
                grid[y][x]=0

    def clear_corner_area(self, grid: List[List[int]], corner: Tuple[int, int]) -> None:
        # Corner rooms are already open and connected. Do not erase their walls:
        # doing so would undo the corridor structure near the start and exit.
        grid[corner[1]][corner[0]]=0


class Maze:
    """Procedurally generated maze."""
    
    def __init__(self, level: int, complexity: Optional[MazeComplexity] = None, grid_size: int = 0, layout=None):
        """Generate a maze for the given level.
        
        Args:
            level: Current level number (1-based).
            complexity: Optional maze complexity level. If None, calculated from level.
            grid_size: Grid size (width/height in cells). Always provided by level_config.get_maze_grid_size().
            layout: A level_layout.Layout to build the maze from instead of generating one (optional).
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
        
        # Wall blocks no shot can destroy; only a hand-made layout has them
        self.strong_cells: FrozenSet[Tuple[int, int]] = frozenset()
        if layout is None:
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
        else:
            # A hand-made layout: its walls, its start and its exit
            self.grid = layout.grid()
            self.strong_cells = layout.strong_walls
            start_grid, exit_grid = layout.start, layout.exit
        
        # Convert grid to blocks and their wall segments
        self.converter = GridToWallsConverter(self.position_calculator, self.strong_cells)
        self.wall_renderer = WallRenderer()
        self.wall_debris = WallDebris()
        # Spatial grid for efficient collision detection
        self.spatial_grid = SpatialGrid(
            config.SCREEN_WIDTH,
            config.SCREEN_HEIGHT,
            cell_size=150.0  # Optimal cell size for this game
        )
        self.wall_generation = 0  # Goes up each time a block is destroyed
        # Centre lines of the physics gates' planks, for everything that sees walls (set by the game each frame)
        self.gate_segments: List[WallSegment] = []
        self.rebuild_walls()
        
        # Set start position
        if layout is None:
            self.start_pos = self.position_calculator.get_start_position(start_grid)
        else:
            self.start_pos = self.position_calculator.grid_center_to_screen(*start_grid)
        
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
        # Screen areas of the outer ring's blocks, which wear down but are never destroyed
        self.unbreakable_blocks = frozenset(
            self.converter.cell_rect(x, y) for x, y in self.blocks if self.converter.on_perimeter(self.grid, x, y)
        )
        # Screen areas of the strong walls, which shots never mark
        self.strong_blocks = frozenset(self.converter.cell_rect(x, y) for x, y in self.strong_cells)
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
    
    def damage_wall(self, wall: WallSegment, impact: Optional[Tuple[float, float]] = None,
                    *, damage: int = 1) -> bool:
        """Damage the block a wall segment is a face of. Returns True if the block was destroyed.
        
        The whole block goes at once, and the faces of its neighbours that
        looked onto it become walls. Either way the shot knocks rock loose.
        A block of the outer ring cracks and sheds rock but is never destroyed.

        Args:
            wall: The wall segment that was hit.
            impact: Where the shot landed, for the chips it knocks off.
            damage: Hit points removed in one impact (rail shots remove the whole block).
            
        Returns:
            True if the block was destroyed (hit points reached 0), False otherwise.
        """
        if wall not in self.walls:
            return False

        cell = wall.cell
        if cell in self.strong_cells:
            # Metal: the shot strikes sparks and leaves no mark
            self.wall_debris.spark(impact if impact is not None else wall.start)
            return False
        if cell not in self.blocks:
            # A loose segment that belongs to no block
            destroyed = wall.damage(damage)
            if destroyed:
                self.spatial_grid.update_wall(wall)
                self.walls = [w for w in self.walls if w.active]
            return destroyed

        faces = [w for w in self.walls if w.cell == cell]
        hit_points = self.blocks[cell] - damage
        if not wall.destructible:
            # The outer ring wears down like any block, but its last hit point never goes
            hit_points = max(1, hit_points)
        for face in faces:
            face.hit_points = hit_points
        if hit_points > 0:
            if hit_points < self.blocks[cell]:
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
            
            if not self.is_open(pos, 15):
                continue
            
            positions.append(pos)
        
        return positions
    
    def is_open(self, pos: Tuple[float, float], radius: float) -> bool:
        """Whether a circle of this radius at pos sits in open space: centre inside the maze and outside every block, touching no wall."""
        cell = (int((pos[0] - self.offset_x) // self.cell_size_x), int((pos[1] - self.offset_y) // self.cell_size_y))
        if not (0 <= cell[0] < self.grid_width and 0 <= cell[1] < self.grid_height) or cell in self.blocks:
            return False
        for wall in self.spatial_grid.get_nearby_walls(pos, radius):
            if wall.active:
                segment = wall.get_segment()
                if circle_line_collision(pos, radius, segment[0], segment[1]):
                    return False
        return True
    
    def open_spot_near(self, origin: Tuple[float, float], radius: float,
                       max_offset: float, min_offset: float = 0.0, attempts: int = 20) -> Tuple[float, float]:
        """A random open position between min_offset and max_offset from origin, for something appearing there.
        
        Falls back to origin itself when no open spot turns up, so nothing is placed inside a block.
        """
        for _ in range(attempts):
            angle = random.uniform(0, 2 * math.pi)
            offset = random.uniform(min_offset, max_offset)
            pos = (origin[0] + math.cos(angle) * offset, origin[1] + math.sin(angle) * offset)
            if self.is_open(pos, radius):
                return pos
        return origin
    
    def update(self, dt: float) -> None:
        """Advance the rock knocked loose by shots."""
        self.wall_debris.update(dt)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the maze."""
        self.wall_renderer.draw(
            screen, self.walls, blocks=self.block_fills, wounds=self.block_wounds, unbreakable=self.unbreakable_blocks,
            strong=self.strong_blocks
        )
        self.wall_debris.draw(screen)
        
        # Draw exit marker
        if self.exit.active:
            self.exit.draw(screen)

