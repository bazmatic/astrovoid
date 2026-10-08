"""Level spawn overrides, automatic placement, and safe spawn reservation."""
import math
import config
from utils.math_utils import circle_line_collision


def parse_hunter_cell(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'spawn_cell'}:
        raise ValueError('hunter must contain exactly spawn_cell')
    cell = value['spawn_cell']
    if (not isinstance(cell, list) or len(cell) != 2
            or any(type(v) is not int for v in cell)):
        raise ValueError('hunter.spawn_cell must contain two integers')
    return tuple(cell)


def resolve_hunter_spawn(value, maze, player):
    cell = parse_hunter_cell(value)
    if cell is None:
        # Furthest from the player first, so the hunter starts well away and has to come and help
        return _first_safe_cell(maze, player, lambda pos: -math.dist(pos, (player.x, player.y)))
    col, row = cell
    if not (0 <= col < maze.grid_width and 0 <= row < maze.grid_height):
        raise ValueError('hunter.spawn_cell is outside the maze')
    if maze.grid[row][col]:
        raise ValueError('hunter.spawn_cell is a wall cell')
    pos = maze.position_calculator.grid_center_to_screen(col, row)
    if any(w.active and circle_line_collision(pos, config.SHIP_SIZE, w.start, w.end)
           for w in maze.walls):
        raise ValueError('hunter.spawn_cell has insufficient wall clearance')
    if math.hypot(pos[0] - player.x, pos[1] - player.y) < config.SHIP_SIZE + player.radius:
        raise ValueError('hunter.spawn_cell overlaps the player')
    return pos


def nearest_hunter_spawn(near, maze, player):
    """The safe spawn closest to a point: where a summoned hunter appears."""
    return _first_safe_cell(maze, player, lambda pos: math.dist(pos, near))


def place_jev_beacon(maze, player):
    """Where a level's Jev beacon lies: a third of the way from the player's start to the exit.

    That is soon reached, and clear of the exit portal, which would hide it.
    """
    third = (player.x + (maze.exit.x - player.x) / 3, player.y + (maze.exit.y - player.y) / 3)
    return nearest_hunter_spawn(third, maze, player)


def _first_safe_cell(maze, player, order):
    """The centre of the first usable open cell, taking cells in ascending `order` of their centres."""
    candidates = [(col,row) for row in range(maze.grid_height)
                  for col in range(maze.grid_width) if not maze.grid[row][col]]
    candidates.sort(key=lambda cell: order(maze.position_calculator.grid_center_to_screen(*cell)))
    for candidate in candidates:
        try:
            return resolve_hunter_spawn({'spawn_cell':list(candidate)}, maze, player)
        except ValueError:
            continue
    raise ValueError('no safe hunter spawn exists in this maze')


def reserve_hunter_clearance(positions, hunter_pos, radius):
    if hunter_pos is None:
        return positions
    enemy_radius = max(config.STATIC_ENEMY_SIZE, config.DYNAMIC_ENEMY_SIZE,
        config.REPLAY_ENEMY_SIZE, config.FLOCKER_ENEMY_SIZE, config.FLIGHTHOUSE_ENEMY_SIZE,
        config.EGG_INITIAL_SIZE, config.BABY_SIZE,
        config.REPLAY_ENEMY_SIZE * config.SPLIT_BOSS_SIZE_MULTIPLIER,
        config.REPLAY_ENEMY_SIZE * config.MOTHER_BOSS_SIZE_MULTIPLIER)
    return [p for p in positions if math.hypot(p[0]-hunter_pos[0], p[1]-hunter_pos[1])
            >= radius + enemy_radius]
