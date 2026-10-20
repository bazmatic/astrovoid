"""The editor's rules: what is in each cell, what may be placed where. No drawing and no files."""
import enemy_kinds
from level_layout import GatePlacement, Layout, plank_cells, planks_overlap
from maze.config import MazeComplexity
from maze.generator import Maze
from physics.obstacle_world import plank_fits
from policies.ammo import AMMO_POLICIES, DEFAULT_AMMO_POLICY
from policies.exit import DEFAULT_EXIT_POLICY, EXIT_POLICIES, OpenAfterTime, TypeCleared

PALETTE = ('wall',) + enemy_kinds.kinds() + ('start', 'exit', 'beacon', 'gate', 'motor_gate')
GATE_KINDS = ('gate', 'motor_gate')
GATE_ANGLES = (0, 45, 90, 135)
GATE_TURN = 45
TIMER_STEP = 10
SHORTEST_TIMER = 10


def _empty_maze(level, layout):
    """The maze a layout makes on this screen: the pixels a gate's plank must fit in."""
    return Maze(level, complexity=MazeComplexity.EMPTY, grid_size=layout.grid_size, layout=layout)


class EditorModel:
    def __init__(self, level, layout, exit_policy=DEFAULT_EXIT_POLICY, ammo_policy=DEFAULT_AMMO_POLICY,
                 maze_for=_empty_maze):
        """`maze_for(level, layout)` builds the maze whose pixels decide whether a gate's plank fits."""
        self.level = level
        self._maze_for = maze_for
        self._mazes = {}
        self.exit_policy = exit_policy
        self.ammo_policy = ammo_policy
        self.grid_size = layout.grid_size
        self.walls = set(layout.walls)
        self.enemies = {cell: kind for kind, cell in layout.enemies}
        self.start = layout.start
        self.exit = layout.exit
        self.beacon = layout.beacon
        self.gates = {gate.cell: gate for gate in layout.gates}
        self.cursor = layout.start
        self.palette_index = 0
        self.dirty = False

    @property
    def selected(self):
        return PALETTE[self.palette_index]

    def move(self, dx, dy):
        """Move the cursor, staying inside the interior (the border cannot be edited)."""
        last = self.grid_size - 2
        col, row = self.cursor
        self.cursor = (min(max(col + dx, 1), last), min(max(row + dy, 1), last))

    def step_palette(self, delta):
        self.palette_index = (self.palette_index + delta) % len(PALETTE)

    def contents(self, cell):
        """What is in a cell: 'wall', an enemy type, 'start', 'exit', 'beacon', 'gate', 'motor_gate', or None."""
        if cell in self.walls:
            return 'wall'
        if cell == self.start:
            return 'start'
        if cell == self.exit:
            return 'exit'
        if cell in self.enemies:
            return self.enemies[cell]
        if cell == self.beacon:
            return 'beacon'
        if cell in self.gates:
            return 'motor_gate' if self.gates[cell].motor else 'gate'
        return None

    def place(self):
        """Put the selected item at the cursor. False (and nothing changes) if the rules refuse it."""
        cell, item = self.cursor, self.selected
        here = self.contents(cell)
        if item == 'wall':
            if here in ('start', 'exit') or not self._gates_fit(walls=self.walls | {cell}):
                return False
            self.enemies.pop(cell, None)
            if self.beacon == cell:
                self.beacon = None
            self.walls.add(cell)
        elif item in enemy_kinds.kinds():
            if here is not None and here not in enemy_kinds.kinds():
                return False                               # a wall, the start, the exit or the beacon is there
            if item in enemy_kinds.anchored() and not self._gates_fit(clear=self._kept_clear() | {cell}):
                return False                               # a plank over it would rock on it for ever
            self.enemies[cell] = item
        elif item in GATE_KINDS:
            if here is not None and here not in GATE_KINDS:
                return False
            if here == item:                               # the same kind again: keep its angle and direction
                return True
            motor = 'cw' if item == 'motor_gate' else None
            gate = next((g for g in (GatePlacement(cell, angle, motor) for angle in GATE_ANGLES)
                         if self._plank_fits(g)), None)
            if gate is None:
                return False
            self.gates[cell] = gate
        else:                                              # start, exit, beacon: one each, so this moves it
            if here is not None and here != item:
                return False
            if item in ('start', 'exit'):
                moved = (self._kept_clear() - {getattr(self, item)}) | {cell}
                if not self._gates_fit(clear=moved):
                    return False
            setattr(self, item, cell)
        self.dirty = True
        return True

    def remove(self):
        """Take away what is at the cursor. The start and the exit cannot be removed, only moved."""
        cell, here = self.cursor, self.contents(self.cursor)
        if here in (None, 'start', 'exit'):
            return False
        if here == 'wall':
            self.walls.discard(cell)
        elif here == 'beacon':
            self.beacon = None
        elif here in GATE_KINDS:
            del self.gates[cell]
        else:
            del self.enemies[cell]
        self.dirty = True
        return True

    def _kept_clear(self):
        """The cells no plank may cover: the start, the exit and the anchored enemies."""
        return {self.start, self.exit} | {cell for cell, kind in self.enemies.items() if kind in enemy_kinds.anchored()}

    def _maze(self, walls):
        key = frozenset(walls)
        if key not in self._mazes:
            if len(self._mazes) > 8:
                self._mazes.clear()
            self._mazes[key] = self._maze_for(self.level, Layout(self.grid_size, key, self.start, self.exit))
        return self._mazes[key]

    def _plank_fits(self, gate, walls=None, clear=None):
        """Whether the gate's plank stays inside the interior and clear of walls, other planks, the start, the exit
        and anchored enemies: by the layout's cell rules, and in pixels on the maze this screen makes."""
        walls = self.walls if walls is None else walls
        clear = self._kept_clear() if clear is None else clear
        last = self.grid_size - 2
        others = [other for cell, other in self.gates.items() if cell != gate.cell]
        if not all(1 <= col <= last and 1 <= row <= last and (col, row) not in walls and (col, row) not in clear
                   for col, row in plank_cells(gate)):
            return False
        if any(planks_overlap(gate, other) for other in others):
            return False
        return plank_fits(self._maze(walls), gate, others, keep_clear=clear)

    def _gates_fit(self, walls=None, clear=None):
        """Whether every gate that fits now would still fit with these walls and kept-clear cells.

        A gate that already doesn't fit (a level saved on a screen of another shape) is left out, so it can't
        stop edits elsewhere; the cursor says so when it is on it."""
        misfits = set(self.misfit_gates())
        return all(self._plank_fits(gate, walls, clear) for cell, gate in self.gates.items() if cell not in misfits)

    def misfit_gates(self):
        """The cells of the gates whose planks don't fit as things stand, in row order."""
        return sorted((cell for cell, gate in self.gates.items() if not self._plank_fits(gate)),
                      key=lambda cell: (cell[1], cell[0]))

    def turn_gate(self):
        """Turn the gate under the cursor clockwise to the next angle its plank fits at, 45 degrees at a time
        (wrapping at 180). False if there is no gate or it fits at no other angle."""
        gate = self.gates.get(self.cursor)
        if gate is None:
            return False
        for step in range(1, len(GATE_ANGLES)):
            turned = GatePlacement(gate.cell, (gate.angle + step * GATE_TURN) % 180, gate.motor)
            if self._plank_fits(turned):
                self.gates[gate.cell] = turned
                self.dirty = True
                return True
        return False

    def flip_gate(self):
        """Reverse the motor of the gate under the cursor. False for no gate or a free gate."""
        gate = self.gates.get(self.cursor)
        if gate is None or gate.motor is None:
            return False
        self.gates[gate.cell] = GatePlacement(gate.cell, gate.angle, 'ccw' if gate.motor == 'cw' else 'cw')
        self.dirty = True
        return True

    def cycle_exit_policy(self):
        self.exit_policy = _next_policy(EXIT_POLICIES, self.exit_policy)
        self.dirty = True

    def cycle_ammo_policy(self):
        self.ammo_policy = _next_policy(AMMO_POLICIES, self.ammo_policy)
        self.dirty = True

    def adjust_timer(self, delta):
        """Lengthen or shorten a timer exit. False if the exit has no timer or is already at its shortest."""
        if not isinstance(self.exit_policy, OpenAfterTime):
            return False
        seconds = max(SHORTEST_TIMER, self.exit_policy.seconds + delta)
        if seconds == self.exit_policy.seconds:
            return False
        self.exit_policy = OpenAfterTime(seconds)
        self.dirty = True
        return True

    def toggle_exit_type(self, kind):
        """Add an enemy kind to a kill-these exit, or take it out. The last kind can't be taken out."""
        if not isinstance(self.exit_policy, TypeCleared) or kind not in enemy_kinds.kinds():
            return False
        kinds = self.exit_policy.enemy_types
        if kind in kinds:
            if len(kinds) == 1:
                return False
            kinds = tuple(k for k in kinds if k != kind)
        else:
            kinds = kinds + (kind,)
        self.exit_policy = TypeCleared(kinds)
        self.dirty = True
        return True

    def to_layout(self):
        return Layout(self.grid_size, frozenset(self.walls), self.start, self.exit,
                      tuple((kind, cell) for cell, kind in self.enemies.items()), self.beacon,
                      tuple(self.gates.values()))


def _next_policy(registry, policy):
    names = registry.names()
    return registry.starter(names[(names.index(policy.name) + 1) % len(names)])
