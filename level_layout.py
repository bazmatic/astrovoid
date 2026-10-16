"""A level's hand-made layout: the exact walls, start, exit, enemies and beacon, in grid cells.

A level file may carry one under "layout" (see levels/README.md). Cells are (col, row) pairs; the border ring of the
grid is always wall and is never listed.
"""
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

Cell = Tuple[int, int]

ENEMY_TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone',
               'split_boss', 'mother_boss', 'rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet')
# Enemies flown by a pilot, which the game makes itself (they need a pilot and a view of the game)
HUNTER_KINDS = ('rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet')


class LayoutError(ValueError):
    """A layout that cannot be played."""


@dataclass(frozen=True)
class Layout:
    grid_size: int
    walls: FrozenSet[Cell]
    start: Cell
    exit: Cell
    enemies: Tuple[Tuple[str, Cell], ...] = ()
    beacon: Optional[Cell] = None

    def __post_init__(self):
        # One order for the enemies (by row, column, type), so two layouts of the same level are equal
        object.__setattr__(self, 'enemies', tuple(sorted(self.enemies, key=lambda e: (e[1][1], e[1][0], e[0]))))

    def grid(self):
        """The maze grid, indexed [row][col]: 1 for a wall (the border and `walls`), 0 for open."""
        n = self.grid_size
        grid = [[1 if row in (0, n - 1) or col in (0, n - 1) else 0 for col in range(n)] for row in range(n)]
        for col, row in self.walls:
            grid[row][col] = 1
        return grid

    def counts(self):
        counts = dict.fromkeys(ENEMY_TYPES, 0)
        for kind, _ in self.enemies:
            counts[kind] += 1
        return counts

    def to_json(self):
        order = lambda cell: (cell[1], cell[0])
        return {
            'walls': [list(cell) for cell in sorted(self.walls, key=order)],
            'start': list(self.start),
            'exit': list(self.exit),
            'enemies': [{'type': kind, 'cell': list(cell)}
                        for kind, cell in sorted(self.enemies, key=lambda e: (order(e[1]), e[0]))],
            'beacon': list(self.beacon) if self.beacon is not None else None,
        }


def _cell(value, size, what):
    whole = lambda v: isinstance(v, int) and not isinstance(v, bool)
    if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(whole(v) for v in value)):
        raise LayoutError(f'{what} must be a [col, row] pair of whole numbers, not {value!r}')
    col, row = value
    if not (1 <= col <= size - 2 and 1 <= row <= size - 2):
        raise LayoutError(f'{what} {col},{row} is not inside the grid (cells 1 to {size - 2})')
    return (col, row)


def parse_layout(data, grid_size):
    """The Layout a level file's "layout" block describes; raises LayoutError if it cannot be played."""
    if not isinstance(data, dict):
        raise LayoutError('layout must be an object')
    for key in ('start', 'exit'):
        if key not in data:
            raise LayoutError(f'layout has no {key}')
    walls = frozenset(_cell(cell, grid_size, 'wall') for cell in data.get('walls', ()))
    start = _cell(data['start'], grid_size, 'start')
    exit_ = _cell(data['exit'], grid_size, 'exit')
    if start == exit_:
        raise LayoutError('start and exit are the same cell')
    for name, cell in (('start', start), ('exit', exit_)):
        if cell in walls:
            raise LayoutError(f'the {name} is on a wall')
    enemies, taken = [], set()
    for entry in data.get('enemies', ()):
        try:
            kind, raw = entry['type'], entry['cell']
        except (TypeError, KeyError):
            raise LayoutError(f'enemy {entry!r} needs a type and a cell')
        if kind not in ENEMY_TYPES:
            raise LayoutError(f'unknown enemy type {kind!r}')
        cell = _cell(raw, grid_size, f'{kind}')
        if cell in walls or cell in taken:
            raise LayoutError(f'{kind} at {cell} is on a wall or shares a cell')
        taken.add(cell)
        enemies.append((kind, cell))
    beacon = data.get('beacon')
    if beacon is not None:
        beacon = _cell(beacon, grid_size, 'beacon')
        if beacon in walls:
            raise LayoutError('the beacon is on a wall')
    return Layout(grid_size, walls, start, exit_, tuple(enemies), beacon)
