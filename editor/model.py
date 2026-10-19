"""The editor's rules: what is in each cell, what may be placed where. No drawing and no files."""
import enemy_names
from level_layout import ENEMY_TYPES, GatePlacement, Layout, plank_cells
from policies.ammo import AMMO_POLICIES, DEFAULT_AMMO_POLICY
from policies.exit import DEFAULT_EXIT_POLICY, EXIT_POLICIES, OpenAfterTime, TypeCleared

PALETTE = ('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon', 'gate', 'motor_gate')
GATE_KINDS = ('gate', 'motor_gate')
GATE_TURN = 45
TIMER_STEP = 10
SHORTEST_TIMER = 10


class EditorModel:
    def __init__(self, level, layout, exit_policy=DEFAULT_EXIT_POLICY, ammo_policy=DEFAULT_AMMO_POLICY):
        self.level = level
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
            if here in ('start', 'exit') or self._under_a_plank(cell):
                return False
            self.enemies.pop(cell, None)
            if self.beacon == cell:
                self.beacon = None
            self.walls.add(cell)
        elif item in ENEMY_TYPES:
            if here is not None and here not in ENEMY_TYPES:
                return False                               # a wall, the start, the exit or the beacon is there
            self.enemies[cell] = item
        elif item in GATE_KINDS:
            if here is not None and here not in GATE_KINDS:
                return False
            gate = GatePlacement(cell, 0, 'cw') if item == 'motor_gate' else GatePlacement(cell)
            if not self._plank_fits(gate):
                return False
            self.gates[cell] = gate
        else:                                              # start, exit, beacon: one each, so this moves it
            if here is not None and here != item:
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

    def _plank_fits(self, gate):
        """Whether the gate's plank stays inside the interior and clear of walls."""
        last = self.grid_size - 2
        return all(1 <= col <= last and 1 <= row <= last and (col, row) not in self.walls
                   for col, row in plank_cells(gate))

    def _under_a_plank(self, cell):
        return any(cell in plank_cells(gate) for gate in self.gates.values())

    def turn_gate(self):
        """Turn the gate under the cursor 45 degrees clockwise (wrapping at 180). False if there is no gate or the
        turned plank would cross a wall."""
        gate = self.gates.get(self.cursor)
        if gate is None:
            return False
        turned = GatePlacement(gate.cell, (gate.angle + GATE_TURN) % 180, gate.motor)
        if not self._plank_fits(turned):
            return False
        self.gates[gate.cell] = turned
        self.dirty = True
        return True

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
        if not isinstance(self.exit_policy, TypeCleared) or kind not in enemy_names.KINDS:
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
