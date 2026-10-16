"""The editor's rules: what is in each cell, what may be placed where. No drawing and no files."""
import enemy_names
from level_layout import ENEMY_TYPES, Layout
from policies.ammo import AMMO_POLICIES, DEFAULT_AMMO_POLICY
from policies.exit import DEFAULT_EXIT_POLICY, EXIT_POLICIES, OpenAfterTime, TypeCleared

PALETTE = ('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon')
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
        """What is in a cell: 'wall', an enemy type, 'start', 'exit', 'beacon', or None."""
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
        return None

    def place(self):
        """Put the selected item at the cursor. False (and nothing changes) if the rules refuse it."""
        cell, item = self.cursor, self.selected
        here = self.contents(cell)
        if item == 'wall':
            if here in ('start', 'exit'):
                return False
            self.enemies.pop(cell, None)
            if self.beacon == cell:
                self.beacon = None
            self.walls.add(cell)
        elif item in ENEMY_TYPES:
            if here is not None and here not in ENEMY_TYPES:
                return False                               # a wall, the start, the exit or the beacon is there
            self.enemies[cell] = item
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
        else:
            del self.enemies[cell]
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
                      tuple((kind, cell) for cell, kind in self.enemies.items()), self.beacon)


def _next_policy(registry, policy):
    names = registry.names()
    return registry.starter(names[(names.index(policy.name) + 1) % len(names)])
