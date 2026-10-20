"""A generated level, read back as the layout it plays as."""
from entities.jev_beacon import JevBeacon
from level_layout import Layout


def generated_layout(game, level):
    """Start the level as it plays today (from its seed) and describe what it made as a Layout."""
    game.level = level
    game.start_level()
    maze = game.maze
    cell = lambda pos: maze.position_calculator.screen_to_grid(*pos)
    enemies = []
    for enemy in game.entity_manager.get_all_enemies():
        enemies.append((enemy.type, cell(enemy.get_pos())))
    walls = frozenset((col, row) for row in range(1, maze.grid_height - 1)
                      for col in range(1, maze.grid_width - 1) if maze.grid[row][col])
    beacon = next((cell(c.get_pos()) for c in game.powerup_crystals if isinstance(c, JevBeacon)), None)
    start, exit_ = cell((game.ship.x, game.ship.y)), cell((maze.exit.x, maze.exit.y))
    open_cells = {(col, row) for row in range(1, maze.grid_height - 1) for col in range(1, maze.grid_width - 1)
                  if not maze.grid[row][col]}
    taken = {start, exit_} | ({beacon} if beacon is not None else set())
    layout = Layout(maze.grid_width, walls, start, exit_, tuple(spread_out(enemies, open_cells, taken)), beacon)
    game._close_enemy_hunters()                          # any enemy hunter's pilot (and thread) is not needed here
    return layout


def spread_out(enemies, open_cells, taken):
    """The enemies, one to a cell. A generated level can put two enemies in one cell (a flock packs tightly);
    each one after the first moves to the nearest free open cell, so none is lost. `taken` are cells that hold
    something else (start, exit, beacon)."""
    used = set(taken)
    placed = []
    for kind, cell in enemies:
        if cell in open_cells and cell not in used:
            spot = cell
        else:
            free = [c for c in open_cells if c not in used]
            if not free:
                logging.getLogger(__name__).warning('No free cell for a %s near %s; it is left out', kind, cell)
                continue
            spot = min(free, key=lambda c: (max(abs(c[0] - cell[0]), abs(c[1] - cell[1])),
                                            abs(c[0] - cell[0]) + abs(c[1] - cell[1]), c[1], c[0]))
        used.add(spot)
        placed.append((kind, spot))
    return placed
