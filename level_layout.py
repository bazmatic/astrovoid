"""A level's hand-made layout: the exact walls, start, exit, enemies and beacon, in grid cells.

A level file may carry one under "layout" (see levels/README.md). Cells are (col, row) pairs; the border ring of the
grid is always wall and is never listed.
"""
import math
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

Cell = Tuple[int, int]

ENEMY_TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone',
               'split_boss', 'mother_boss', 'rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet')
# Enemies that never move, which a gate's plank must not cover (it would rock on them for ever)
ANCHORED_KINDS = ('anemone', 'flighthouse')
# Enemies flown by a pilot, which the game makes itself (they need a pilot and a view of the game)
HUNTER_KINDS = ('rules_hunter', 'neural_hunter', 'boss_viber', 'vibelet')


class LayoutError(ValueError):
    """A layout that cannot be played."""


GATE_MOTORS = ('cw', 'ccw')


@dataclass(frozen=True)
class GatePlacement:
    """A physics gate: a plank on a pin at the centre of `cell`, turned `angle` degrees; `motor` is None (free),
    'cw' or 'ccw'."""
    cell: Cell
    angle: int = 0
    motor: Optional[str] = None


def plank_cells(placement):
    """The cells a gate's plank crosses at its angle (its tips are one cell from the pin)."""
    col, row = placement.cell
    dx, dy = math.cos(math.radians(placement.angle)), math.sin(math.radians(placement.angle))
    cells = set()
    for i in range(9):
        t = (i - 4) / 4
        cells.add((math.floor(col + 0.5 + dx * t), math.floor(row + 0.5 + dy * t)))
    return frozenset(cells)


def _segment_gap(a, b):
    """The shortest distance between two segments, each ((x1, y1), (x2, y2))."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    def to_segment(p, seg):
        (x1, y1), (x2, y2) = seg
        length = (x2 - x1) ** 2 + (y2 - y1) ** 2
        t = max(0.0, min(1.0, ((p[0] - x1) * (x2 - x1) + (p[1] - y1) * (y2 - y1)) / length))
        return math.hypot(p[0] - (x1 + t * (x2 - x1)), p[1] - (y1 + t * (y2 - y1)))

    if cross(a[0], a[1], b[0]) * cross(a[0], a[1], b[1]) < 0 and cross(b[0], b[1], a[0]) * cross(b[0], b[1], a[1]) < 0:
        return 0.0
    return min(to_segment(a[0], b), to_segment(a[1], b), to_segment(b[0], a), to_segment(b[1], a))


def planks_overlap(a, b):
    """Whether two gates' planks share a cell or cross or touch (planks that do would never settle)."""
    if plank_cells(a) & plank_cells(b):
        return True

    def segment(g):
        dx, dy = math.cos(math.radians(g.angle)), math.sin(math.radians(g.angle))
        x, y = g.cell[0] + 0.5, g.cell[1] + 0.5
        return (x - dx, y - dy), (x + dx, y + dy)

    return _segment_gap(segment(a), segment(b)) < 0.2


@dataclass(frozen=True)
class Layout:
    grid_size: int
    walls: FrozenSet[Cell]
    start: Cell
    exit: Cell
    enemies: Tuple[Tuple[str, Cell], ...] = ()
    beacon: Optional[Cell] = None
    gates: Tuple[GatePlacement, ...] = ()

    def __post_init__(self):
        # One order for the enemies (by row, column, type), so two layouts of the same level are equal
        object.__setattr__(self, 'enemies', tuple(sorted(self.enemies, key=lambda e: (e[1][1], e[1][0], e[0]))))
        object.__setattr__(self, 'gates', tuple(sorted(self.gates, key=lambda g: (g.cell[1], g.cell[0]))))

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
        out = {
            'walls': [list(cell) for cell in sorted(self.walls, key=order)],
            'start': list(self.start),
            'exit': list(self.exit),
            'enemies': [{'type': kind, 'cell': list(cell)}
                        for kind, cell in sorted(self.enemies, key=lambda e: (order(e[1]), e[0]))],
            'beacon': list(self.beacon) if self.beacon is not None else None,
        }
        if self.gates:
            out['gates'] = [{'cell': list(g.cell), **({'angle': g.angle} if g.angle else {}),
                             **({'motor': g.motor} if g.motor else {})} for g in self.gates]
        return out


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
    gates = []
    for entry in data.get('gates', ()):
        if not isinstance(entry, dict) or 'cell' not in entry:
            raise LayoutError(f'gate {entry!r} needs a cell')
        cell = _cell(entry['cell'], grid_size, 'gate')
        angle, motor = entry.get('angle', 0), entry.get('motor')
        if not (isinstance(angle, int) and not isinstance(angle, bool) and 0 <= angle < 180 and angle % 45 == 0):
            raise LayoutError(f'gate at {cell} has angle {angle!r}; it must be 0, 45, 90 or 135')
        if motor is not None and motor not in GATE_MOTORS:
            raise LayoutError(f'gate at {cell} has motor {motor!r}; it must be cw or ccw')
        placement = GatePlacement(cell, angle, motor)
        blocked = {'a wall': walls, 'the start': {start}, 'the exit': {exit_},
                   'the beacon': {beacon} if beacon is not None else set(),
                   'an enemy': {c for _, c in enemies}, 'another gate': {g.cell for g in gates}}
        for what, cells in blocked.items():
            if cell in cells:
                raise LayoutError(f'gate at {cell} is on {what}')
        kept_clear = {'the start': {start}, 'the exit': {exit_},
                      'an anchored enemy': {c for kind, c in enemies if kind in ANCHORED_KINDS}}
        for plank in plank_cells(placement):
            if plank in walls or not (1 <= plank[0] <= grid_size - 2 and 1 <= plank[1] <= grid_size - 2):
                raise LayoutError(f'the plank of the gate at {cell} runs into a wall at {plank}')
            for what, cells in kept_clear.items():
                if plank in cells:
                    raise LayoutError(f'the plank of the gate at {cell} covers {what} at {plank}')
        for other in gates:
            if planks_overlap(placement, other):
                raise LayoutError(f'the plank of the gate at {cell} overlaps the plank of the gate at {other.cell}')
        gates.append(placement)
    return Layout(grid_size, walls, start, exit_, tuple(enemies), beacon, tuple(gates))
