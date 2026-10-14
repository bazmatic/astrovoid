"""The editor's rules: what is in each cell, what may be placed where. No drawing and no files."""
from level_layout import ENEMY_TYPES, Layout

PALETTE = ('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon')


class EditorModel:
    def __init__(self, level, layout):
        self.level = level
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

    def to_layout(self):
        return Layout(self.grid_size, frozenset(self.walls), self.start, self.exit,
                      tuple((kind, cell) for cell, kind in self.enemies.items()), self.beacon)
