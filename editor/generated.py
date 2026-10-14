"""A generated level, read back as the layout it plays as."""
from entities.jev_beacon import JevBeacon
from level_layout import Layout

_LISTS = {'enemies': None, 'replay_enemies': 'replay', 'flockers': 'flocker', 'flighthouses': 'flighthouse',
          'split_bosses': 'split_boss', 'mother_bosses': 'mother_boss', 'eggs': 'egg', 'anemones': 'anemone',
          'rules_hunters': 'rules_hunter'}


def generated_layout(game, level):
    """Start the level as it plays today (from its seed) and describe what it made as a Layout."""
    game.level = level
    game.start_level()
    maze = game.maze
    cell = lambda pos: maze.position_calculator.screen_to_grid(*pos)
    enemies = []
    for attr, kind in _LISTS.items():
        for enemy in getattr(game.entity_manager, attr):
            enemies.append((kind or enemy.type, cell(enemy.get_pos())))
    walls = frozenset((col, row) for row in range(1, maze.grid_height - 1)
                      for col in range(1, maze.grid_width - 1) if maze.grid[row][col])
    beacon = next((cell(c.get_pos()) for c in game.powerup_crystals if isinstance(c, JevBeacon)), None)
    layout = Layout(maze.grid_width, walls, cell((game.ship.x, game.ship.y)), cell((maze.exit.x, maze.exit.y)),
                    tuple(enemies), beacon)
    game._close_rules_hunters()                          # any Rules hunter's pilot thread is not needed here
    return layout
