# The Level Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An in-game editor, switched on by `ASTROVOID_EDITOR=1`, to lay a level out cell by cell (walls, eleven enemy types, start, exit, Jev beacon), save it as an explicit `layout` in the level file, and revert it to the generated level.

**Architecture:** A level file gains an optional `layout` block. `level_layout.py` parses and checks it; `level_config` reads enemy counts and the beacon from it while it exists; `Maze` and `Game.start_level` build the level from it instead of the generator. The editor is a new game state: a pure `EditorModel` (rules), `editor/files.py` (save/revert on disk), and `rendering/level_editor.py` (picker, view, keys), drawing the real maze and sprites.

**Tech Stack:** Python 3.10, pygame, pytest (`venv/bin/python -m pytest`).

**Spec:** `docs/superpowers/specs/2026-10-15-level-editor-design.md`

## Global Constraints

- Level files without a `layout` behave exactly as before.
- The grid is square (`maze.grid_size`, 5 to 100); the border ring is always wall and is never listed or editable.
- Enemy types, verbatim: `static`, `patrol`, `aggressive`, `replay`, `flocker`, `flighthouse`, `egg`, `anemone`, `split_boss`, `mother_boss`, `rules_hunter`.
- The editor exists only when the environment variable `ASTROVOID_EDITOR` is set to a non-empty value.
- Saving never changes a file's `seed`, `maze` or `enemies` keys; revert removes only `layout` (and deletes a file the editor created).
- No playtest, no undo/redo, no mouse, no grid resizing.
- Write Python edits with Python or the Edit tool; macOS `sed` fails on these edits.
- Tests run with the dummy SDL driver; rendering is also checked once on the real driver (Task 4).
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Never commit `assets/neural/hunter.npz` or the local `"hunterPilot": "neural"` in `config/settings.json`.

## Review Focus

- A layout whose exit is walled in loads and plays (unwinnable); the editor does not check reachability. Expected: documented, not a crash.
- A layout with a mistake (enemy on a wall, cell out of range, missing key) must never crash level start: it is ignored with a warning and the level generates.
- Saving a layout for levels 1 to 24 can break `tests/test_level_arc.py` pacing rules; expected: the test fails loudly, nothing silent.
- Saving when the level file cannot be written (read-only, frozen bundle): expected: a visible message in the editor, no crash and no lost edits.
- Holding an arrow key moves the cursor repeatedly; the cursor never leaves the interior; a held key is released when the editor closes.

---

### Task 1: The layout format and level_config

**Files:**
- Create: `level_layout.py`
- Modify: `level_config.py`
- Test: `tests/test_level_layout.py`

**Interfaces:**
- Produces:
  - `level_layout.ENEMY_TYPES: tuple[str, ...]`, `level_layout.LayoutError(ValueError)`.
  - `level_layout.Layout` (frozen dataclass): `grid_size: int`, `walls: frozenset[tuple[int,int]]`, `start: (col,row)`, `exit: (col,row)`, `enemies: tuple[tuple[str,(col,row)], ...] = ()`, `beacon: (col,row) | None = None`; methods `grid() -> list[list[int]]` (indexed `[row][col]`, border and walls are 1), `counts() -> dict[str,int]` (every type present), `to_json() -> dict`.
  - `level_layout.parse_layout(data: dict, grid_size: int) -> Layout` (raises `LayoutError`).
  - `level_config.get_level_layout(level) -> Layout | None` (None when there is no layout or it is invalid, with a logged warning in the invalid case).
  - While a layout exists: `get_level_enemy_counts`, `get_level_anemone_count`, `get_level_split_boss_count`, `get_level_mother_boss_count`, `get_level_rules_hunter_count`, `get_level_egg_count` read from it, and `get_level_hunter_config` returns `{"spawn_cell": [col, row]}` for a beacon or `False` for none.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_level_layout.py
import pytest

import level_config
from level_layout import ENEMY_TYPES, Layout, LayoutError, parse_layout


def data(**changes):
    base = {
        'walls': [[3, 3], [4, 3]],
        'start': [1, 1], 'exit': [7, 7],
        'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'flocker', 'cell': [2, 6]},
                    {'type': 'rules_hunter', 'cell': [6, 2]}],
        'beacon': [3, 5],
    }
    base.update(changes)
    return base


def test_a_layout_parses_and_describes_its_grid():
    layout = parse_layout(data(), 9)
    assert layout.start == (1, 1) and layout.exit == (7, 7) and layout.beacon == (3, 5)
    grid = layout.grid()
    assert len(grid) == 9 and all(len(row) == 9 for row in grid)
    assert grid[0] == [1] * 9 and all(row[0] == 1 and row[8] == 1 for row in grid)   # the border
    assert grid[3][3] == 1 and grid[3][4] == 1 and grid[3][5] == 0                    # [row][col]
    assert layout.counts()['static'] == 1 and layout.counts()['rules_hunter'] == 1
    assert set(layout.counts()) == set(ENEMY_TYPES)


def test_a_layout_round_trips_through_json():
    layout = parse_layout(data(), 9)
    assert parse_layout(layout.to_json(), 9) == layout


def test_a_layout_without_a_beacon_has_none():
    assert parse_layout(data(beacon=None), 9).beacon is None
    without = data()
    del without['beacon']
    assert parse_layout(without, 9).beacon is None


@pytest.mark.parametrize('changes', [
    {'start': [0, 1]},                                            # on the border
    {'exit': [9, 7]},                                             # outside the grid
    {'exit': [1, 1]},                                             # the same cell as the start
    {'walls': [[1, 1]]},                                          # a wall on the start
    {'enemies': [{'type': 'dragon', 'cell': [5, 5]}]},            # unknown type
    {'enemies': [{'type': 'static', 'cell': [3, 3]}]},            # on a wall
    {'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'egg', 'cell': [5, 5]}]},   # two in one cell
    {'enemies': [{'type': 'static'}]},                            # no cell
    {'beacon': [3, 3]},                                           # on a wall
    {'walls': [[3]]},                                             # not a pair
])
def test_a_mistaken_layout_is_rejected(changes):
    with pytest.raises(LayoutError):
        parse_layout(data(**changes), 9)


def test_missing_start_is_rejected():
    broken = data()
    del broken['start']
    with pytest.raises(LayoutError):
        parse_layout(broken, 9)


def file_with(layout, **extra):
    return {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9},
            'enemies': {'static': 7, 'egg': 2, 'split_boss': 1}, **extra, **({'layout': layout} if layout else {})}


def test_counts_come_from_the_layout_while_it_exists(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data()))
    counts = level_config.get_level_enemy_counts(3)
    assert (counts.static, counts.flocker, counts.egg, counts.total) == (1, 1, 0, 1)
    assert level_config.get_level_rules_hunter_count(3) == 1
    assert level_config.get_level_split_boss_count(3) == 0
    assert level_config.get_level_egg_count(3) == 0
    assert level_config.is_boss_level(3)                                  # a Rules hunter is on it


def test_without_the_layout_the_files_own_counts_return(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(None))
    assert level_config.get_level_layout(3) is None
    assert level_config.get_level_enemy_counts(3).static == 7
    assert level_config.get_level_egg_count(3) == 2
    assert level_config.get_level_split_boss_count(3) == 1


def test_the_beacon_comes_from_the_layout(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data()))
    assert level_config.get_level_hunter_config(3) == {'spawn_cell': [3, 5]}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data(beacon=None)))
    assert level_config.get_level_hunter_config(3) is False


def test_an_invalid_layout_is_ignored_with_a_warning(monkeypatch, caplog):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file_with(data(start=[0, 0])))
    assert level_config.get_level_layout(3) is None
    assert 'layout' in caplog.text.lower()
    assert level_config.get_level_enemy_counts(3).static == 7             # the file's counts apply
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_level_layout.py -q 2>&1 | tail -4`
Expected: collection error, `ModuleNotFoundError: No module named 'level_layout'`.

- [ ] **Step 3: Write `level_layout.py`**

```python
"""A level's hand-made layout: the exact walls, start, exit, enemies and beacon, in grid cells.

A level file may carry one under "layout" (see levels/README.md). Cells are (col, row) pairs; the border ring of the
grid is always wall and is never listed.
"""
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple

Cell = Tuple[int, int]

ENEMY_TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone',
               'split_boss', 'mother_boss', 'rules_hunter')


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
    try:
        col, row = value
        col, row = int(col), int(row)
    except (TypeError, ValueError):
        raise LayoutError(f'{what} must be a [col, row] pair, not {value!r}')
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
```

- [ ] **Step 4: Teach `level_config.py` about layouts**

Add to the imports `import logging` and `from level_layout import Layout, LayoutError, parse_layout`. Add this function after `load_level_config`:

```python
def get_level_layout(level: int) -> Optional[Layout]:
    """The level file's hand-made layout, or None if it has none or it cannot be played (that is logged)."""
    data = load_level_config(level)
    if not data or 'layout' not in data:
        return None
    try:
        return parse_layout(data['layout'], get_maze_grid_size(level))
    except (LayoutError, TypeError, ValueError, KeyError) as exc:
        logging.getLogger(__name__).warning('Level %d: ignoring its layout: %s', level, exc)
        return None
```

Then add a layout preamble as the first statements of each of these functions (the existing body stays below it):

- `get_level_enemy_counts(level)`:

```python
    layout = get_level_layout(level)
    if layout is not None:
        counts = layout.counts()
        return EnemyCounts(total=counts['static'] + counts['patrol'] + counts['aggressive'],
                           static=counts['static'], patrol=counts['patrol'], aggressive=counts['aggressive'],
                           replay=counts['replay'], flocker=counts['flocker'], flighthouse=counts['flighthouse'],
                           egg=counts['egg'], anemone=counts['anemone'])
```
- `get_level_anemone_count`, `get_level_split_boss_count`, `get_level_mother_boss_count`, `get_level_rules_hunter_count`, `get_level_egg_count` (the key is `anemone`, `split_boss`, `mother_boss`, `rules_hunter`, `egg`):

```python
    layout = get_level_layout(level)
    if layout is not None:
        return layout.counts()['anemone']      # the type this function counts
```
- `get_level_hunter_config(level)`:

```python
    layout = get_level_layout(level)
    if layout is not None:
        return {'spawn_cell': list(layout.beacon)} if layout.beacon is not None else False
```

Beware: `get_level_layout` calls `get_maze_grid_size`, which reads the file again; that is fine (no function reads a layout recursively).

- [ ] **Step 5: Run the tests**

Run: `venv/bin/python -m pytest tests/test_level_layout.py tests/test_rules_hunter_level.py tests/test_level_arc.py -q 2>&1 | tail -5`
Expected: pass.

- [ ] **Step 6: Update the spec and commit**

Two decisions made in planning, recorded in the spec: the beacon lives inside `layout` as `"beacon"` (not the `hunter` key) so that revert restores the file exactly, and a file the editor creates carries `"created_by_editor": true` so revert knows to delete it. In `docs/superpowers/specs/2026-10-15-level-editor-design.md`: in the layout JSON add `"beacon": [col, row] | null`, replace the sentence "The Jev beacon uses the existing `hunter` key ..." with "The Jev beacon is `layout.beacon` (null for none); while a layout exists it takes the place of the `hunter` key, which is left untouched.", and in "Saving and reverting" add "A file the editor creates also carries `\"created_by_editor\": true`; that marker is how revert knows to delete it."

```bash
git add level_layout.py level_config.py tests/test_level_layout.py docs/superpowers/specs/2026-10-15-level-editor-design.md
git commit -m "feat: level files can carry an explicit layout

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Playing a layout

**Files:**
- Modify: `maze/generator.py` (`Maze.__init__`), `game_handlers/spawn_manager.py`, `game.py`
- Test: `tests/test_layout_play.py`

**Interfaces:**
- Consumes: `Layout`, `level_config.get_level_layout`.
- Produces:
  - `Maze(level, complexity=None, grid_size=0, layout=None)`: with a layout the grid, `start_pos` (the cell's centre) and exit come from it and the generator is not run.
  - `game_handlers.spawn_manager.make_enemy(kind, pos, level, command_recorder) -> (entity_list_attr: str, entity)` for every type except `rules_hunter`.
  - `SpawnManager.spawn_from_layout(layout, maze, level, command_recorder) -> list[(x, y)]` (the pixel positions of Rules hunters, which the game flies itself).
  - `Game._spawn_rules_hunters_at(positions)`; `Game._spawn_rules_hunters` calls it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_layout_play.py
import math

import pygame
import pytest

import config
import level_config
from entities.jev_beacon import JevBeacon
from entities.rules_hunter import RulesHunter
from level_layout import parse_layout
from maze.config import MazeComplexity
from maze.generator import Maze
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_rules_hunter import SilentWorker

LAYOUT = {
    'walls': [[3, 3], [4, 3]],
    'start': [1, 1], 'exit': [7, 7],
    'enemies': [{'type': 'static', 'cell': [5, 5]}, {'type': 'flocker', 'cell': [2, 6]},
                {'type': 'replay', 'cell': [6, 4]}, {'type': 'rules_hunter', 'cell': [6, 2]}],
    'beacon': [3, 5],
}


def file(layout=LAYOUT):
    return {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 9}, 'enemies': {'static': 5},
            'layout': layout}


def test_a_maze_is_built_from_a_layout():
    pygame.init()
    pygame.display.set_mode((320, 240))
    layout = parse_layout(LAYOUT, 9)
    maze = Maze(3, complexity=MazeComplexity.EMPTY, grid_size=9, layout=layout)
    assert maze.grid == layout.grid()
    calc = maze.position_calculator
    assert calc.screen_to_grid(*maze.start_pos) == (1, 1)
    assert calc.screen_to_grid(maze.exit.x, maze.exit.y) == (7, 7)
    assert (3, 3) in maze.blocks and (3, 5) not in maze.blocks


@pytest.fixture
def played(game, monkeypatch):  # noqa: F811
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file() if level == 3 else None)
    game._rules_worker_factory = SilentWorker
    game.level = 3
    game.start_level()
    return game


def cells(game, items):
    calc = game.maze.position_calculator
    return [calc.screen_to_grid(*item.get_pos()) for item in items]


def test_start_and_exit_and_rock_are_where_the_layout_says(played):
    calc = played.maze.position_calculator
    assert calc.screen_to_grid(played.ship.x, played.ship.y) == (1, 1)
    assert calc.screen_to_grid(played.maze.exit.x, played.maze.exit.y) == (7, 7)
    assert played.maze.grid == parse_layout(LAYOUT, 9).grid()


def test_each_enemy_is_at_its_cell_and_only_those_exist(played):
    assert cells(played, played.enemies) == [(5, 5)]
    assert cells(played, played.flockers) == [(2, 6)]
    assert cells(played, played.replay_enemies) == [(6, 4)]
    assert cells(played, played.rules_hunters) == [(6, 2)] and isinstance(played.rules_hunters[0], RulesHunter)
    assert len(list(played.entity_manager.get_all_enemies())) == 4
    assert played.enemies[0].type == 'static'


def test_the_beacon_lies_at_its_cell(played):
    beacons = [c for c in played.powerup_crystals if isinstance(c, JevBeacon)]
    assert [played.maze.position_calculator.screen_to_grid(*b.get_pos()) for b in beacons] == [(3, 5)]


def test_it_is_a_boss_level_because_a_rules_hunter_is_on_it(played):
    assert played.boss_level and played.ship.infinite_ammo


def test_restarting_does_not_pile_up_enemies(played):
    played.start_level()
    assert len(list(played.entity_manager.get_all_enemies())) == 4


def test_a_broken_layout_falls_back_to_the_generated_level(game, monkeypatch, caplog):  # noqa: F811
    broken = dict(LAYOUT, start=[0, 0])
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: file(broken) if level == 3 else None)
    game.level = 3
    game.start_level()
    assert game.maze.grid != parse_layout(LAYOUT, 9).grid()
    assert len(game.enemies) == 5                                          # the file's own `static: 5`
    assert 'ignoring its layout' in caplog.text
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_layout_play.py -q 2>&1 | tail -6`
Expected: failures (`unexpected keyword argument 'layout'`).

- [ ] **Step 3: `Maze` takes a layout**

In `maze/generator.py`, change the signature to `def __init__(self, level: int, complexity: Optional[MazeComplexity] = None, grid_size: int = 0, layout=None):`, add `layout: A level_layout.Layout to build the maze from instead of generating one (optional).` to the docstring's Args, and replace this block:

```python
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
```

with:

```python
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
            start_grid, exit_grid = layout.start, layout.exit
```

Then replace `self.start_pos = self.position_calculator.get_start_position(start_grid)` with:

```python
        if layout is None:
            self.start_pos = self.position_calculator.get_start_position(start_grid)
        else:
            self.start_pos = self.position_calculator.grid_center_to_screen(*start_grid)
```

- [ ] **Step 4: The enemy factory and `spawn_from_layout`**

In `game_handlers/spawn_manager.py` add this module-level function (below the imports/`SpawnConfig`, above `class SpawnManager`):

```python
def make_enemy(kind, pos, level, command_recorder):
    """One enemy of a type at a position, and the entity manager list it belongs in: (list attribute, entity).

    Rules hunters are not made here: they need a pilot worker and a view of the game, which Game provides.
    """
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.flocker_enemy_ship import FlockerEnemyShip
    from entities.flighthouse_enemy import FlighthouseEnemy
    from entities.split_boss import SplitBoss
    from entities.mother_boss import MotherBoss
    from entities.egg import Egg
    from entities.anemone import Anemone
    if kind in ('static', 'patrol', 'aggressive'):
        return 'enemies', Enemy(pos, kind, level)
    if kind == 'flocker':
        return 'flockers', FlockerEnemyShip(pos)
    if kind == 'flighthouse':
        return 'flighthouses', FlighthouseEnemy(pos, level)
    if kind == 'egg':
        return 'eggs', Egg(pos)
    if kind == 'anemone':
        return 'anemones', Anemone(pos)
    recorded = {'replay': ('replay_enemies', ReplayEnemyShip), 'split_boss': ('split_bosses', SplitBoss),
                'mother_boss': ('mother_bosses', MotherBoss)}
    if kind in recorded:
        attr, cls = recorded[kind]
        entity = cls(pos, command_recorder)
        entity.current_replay_index = 0
        return attr, entity
    raise ValueError(f'cannot make an enemy of type {kind!r}')
```

and this method on `SpawnManager` (after `spawn_all_enemies`):

```python
    def spawn_from_layout(self, layout, maze, level, command_recorder):
        """Create the enemies a layout places, each at the centre of its cell, and no others.

        Returns the pixel positions of its Rules hunters, which the game makes and flies itself.
        """
        self._anemone_keep_clear = None
        self.entity_manager.clear_all()
        rules_hunters = []
        for kind, cell in layout.enemies:
            pos = maze.position_calculator.grid_center_to_screen(*cell)
            if kind == 'rules_hunter':
                rules_hunters.append(pos)
                continue
            attr, entity = make_enemy(kind, pos, level, command_recorder)
            getattr(self.entity_manager, attr).append(entity)
        return rules_hunters
```

- [ ] **Step 5: `Game.start_level` plays a layout**

In `game.py`:

1. In `start_level`, replace `self.maze = Maze(self.level, complexity=maze_complexity, grid_size=maze_grid_size)` with:

```python
        layout = level_config.get_level_layout(self.level)
        self.maze = Maze(self.level, complexity=maze_complexity, grid_size=maze_grid_size, layout=layout)
```

2. Make the random spawn positions conditional: change `spawn_positions = self.maze.get_valid_spawn_positions(` to `spawn_positions = [] if layout is not None else self.maze.get_valid_spawn_positions(` (the whole call is the else-branch of the expression; keep its arguments unchanged).

3. Replace the two spawning statements

```python
        self.spawn_manager.spawn_all_enemies(
            self.level, spawn_positions, self.command_recorder, enemy_counts, split_boss_count, mother_boss_count,
            anemone_keep_clear=(self.maze.start_pos, anemone_reach)
        )
        self._spawn_rules_hunters(spawn_positions)
```

with:

```python
        if layout is None:
            self.spawn_manager.spawn_all_enemies(
                self.level, spawn_positions, self.command_recorder, enemy_counts, split_boss_count, mother_boss_count,
                anemone_keep_clear=(self.maze.start_pos, anemone_reach)
            )
            self._spawn_rules_hunters(spawn_positions)
        else:
            self._spawn_rules_hunters_at(
                self.spawn_manager.spawn_from_layout(layout, self.maze, self.level, self.command_recorder))
```

4. Split `_spawn_rules_hunters`: keep it choosing positions and replace its `for pos in candidates[:count]: self.rules_hunters.append(RulesHunter(...))` loop with `self._spawn_rules_hunters_at(candidates[:count])`, and add:

```python
    def _spawn_rules_hunters_at(self, positions):
        """Make a Rules hunter at each position, each with its own pilot worker."""
        for pos in positions:
            self.rules_hunters.append(RulesHunter(pos, self._make_rules_worker(), ProtagonistSurroundings(self)))
```

(The warning about "room for N of M" in `_spawn_rules_hunters` stays where it is.)

- [ ] **Step 6: Run the tests**

Run: `venv/bin/python -m pytest tests/test_layout_play.py tests/test_rules_hunter_game.py tests/test_level_layout.py -q 2>&1 | tail -6`
Expected: pass.

- [ ] **Step 7: Regression and commit**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -7`
Expected: only the 4 known local-setting failures (`test_hunter_integration` x2, `test_hunter_powerups`, `test_pilot_selection`).

```bash
git add maze/generator.py game_handlers/spawn_manager.py game.py tests/test_layout_play.py
git commit -m "feat: a level with a layout plays exactly that

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The editor's model and files

**Files:**
- Create: `editor/__init__.py` (empty), `editor/model.py`, `editor/files.py`, `editor/generated.py`
- Test: `tests/test_editor_model.py`, `tests/test_editor_files.py`

**Interfaces:**
- Consumes: `Layout`, `parse_layout`, `ENEMY_TYPES`, `level_config`.
- Produces:
  - `editor.model.PALETTE: tuple[str, ...]` = `('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon')`.
  - `EditorModel(level: int, layout: Layout)` with attributes `level`, `grid_size`, `walls: set`, `enemies: dict[cell, type]`, `start`, `exit`, `beacon`, `cursor`, `palette_index`, `dirty`; `selected -> str`; `move(dx, dy)`; `step_palette(delta)`; `contents(cell) -> str | None` (one of `'wall'`, an enemy type, `'start'`, `'exit'`, `'beacon'`); `place() -> bool`; `remove() -> bool`; `to_layout() -> Layout`.
  - `editor.files.level_path(level) -> str`; `save_layout(path, layout, defaults) -> None`; `revert_layout(path) -> bool`.
  - `editor.generated.generated_layout(game, level) -> Layout` (runs the real `start_level` and reads back what it made).

- [ ] **Step 1: Write the failing model tests**

```python
# tests/test_editor_model.py
import pytest

from editor.model import PALETTE, EditorModel
from level_layout import ENEMY_TYPES, parse_layout


def model():
    layout = parse_layout({
        'walls': [[3, 3]], 'start': [1, 1], 'exit': [7, 7],
        'enemies': [{'type': 'static', 'cell': [5, 5]}], 'beacon': [3, 5]}, 9)
    return EditorModel(3, layout)


def at(m, cell, item=None):
    m.cursor = cell
    if item is not None:
        m.palette_index = PALETTE.index(item)


def test_the_palette_lists_everything_placeable():
    assert PALETTE == ('wall',) + ENEMY_TYPES + ('start', 'exit', 'beacon')


def test_the_cursor_starts_on_the_start_and_stays_in_the_interior():
    m = model()
    assert m.cursor == (1, 1)
    for _ in range(20):
        m.move(-1, -1)
    assert m.cursor == (1, 1)
    for _ in range(20):
        m.move(1, 1)
    assert m.cursor == (7, 7)                                 # grid 9: cells 1 to 7


def test_stepping_the_palette_wraps_round():
    m = model()
    m.step_palette(-1)
    assert m.selected == 'beacon'
    m.step_palette(1)
    assert m.selected == 'wall'


def test_a_wall_is_placed_on_an_empty_cell_and_removed():
    m = model()
    at(m, (2, 2), 'wall')
    assert m.place() and m.contents((2, 2)) == 'wall' and m.dirty
    assert m.remove() and m.contents((2, 2)) is None


def test_a_wall_replaces_an_enemy_or_the_beacon_but_never_the_start_or_exit():
    m = model()
    at(m, (5, 5), 'wall')
    assert m.place() and m.contents((5, 5)) == 'wall' and (5, 5) not in m.enemies
    at(m, (3, 5), 'wall')
    assert m.place() and m.beacon is None
    at(m, (1, 1), 'wall')
    assert not m.place() and m.contents((1, 1)) == 'start'
    at(m, (7, 7), 'wall')
    assert not m.place() and m.contents((7, 7)) == 'exit'


def test_one_enemy_per_cell_and_a_new_one_replaces_the_old():
    m = model()
    at(m, (5, 5), 'flocker')
    assert m.place() and m.contents((5, 5)) == 'flocker'
    assert list(m.enemies.values()).count('static') == 0


def test_an_enemy_cannot_go_on_a_wall_the_start_or_the_beacon():
    m = model()
    for cell in ((3, 3), (1, 1), (7, 7), (3, 5)):
        at(m, cell, 'egg')
        assert not m.place()
    assert m.dirty is False


def test_start_exit_and_beacon_are_single_so_placing_moves_them():
    m = model()
    at(m, (2, 2), 'start')
    assert m.place() and m.start == (2, 2) and m.contents((1, 1)) is None
    at(m, (6, 6), 'exit')
    assert m.place() and m.exit == (6, 6)
    at(m, (4, 4), 'beacon')
    assert m.place() and m.beacon == (4, 4) and m.contents((3, 5)) is None


def test_start_and_exit_cannot_land_on_each_other_or_on_something():
    m = model()
    at(m, (7, 7), 'start')
    assert not m.place()
    at(m, (3, 3), 'exit')
    assert not m.place()
    at(m, (5, 5), 'start')
    assert not m.place()                                      # an enemy is there


def test_start_and_exit_cannot_be_removed_but_the_beacon_can():
    m = model()
    at(m, (1, 1))
    assert not m.remove()
    at(m, (3, 5))
    assert m.remove() and m.beacon is None


def test_removing_from_an_empty_cell_changes_nothing():
    m = model()
    at(m, (4, 6))
    assert not m.remove() and not m.dirty


def test_the_model_makes_a_valid_layout_of_what_it_holds():
    m = model()
    at(m, (2, 2), 'wall'); m.place()
    at(m, (4, 4), 'patrol'); m.place()
    layout = m.to_layout()
    assert (2, 2) in layout.walls and ('patrol', (4, 4)) in layout.enemies
    assert parse_layout(layout.to_json(), 9) == layout
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_editor_model.py -q 2>&1 | tail -4`
Expected: `ModuleNotFoundError: No module named 'editor'`.

- [ ] **Step 3: Write `editor/model.py`**

```python
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
```

- [ ] **Step 4: Run the model tests**

Run: `venv/bin/python -m pytest tests/test_editor_model.py -q 2>&1 | tail -4`
Expected: all pass. (Placing `start` onto its own cell is allowed and counts as a change; that is fine.)

- [ ] **Step 5: Write the failing file and generated-layout tests**

```python
# tests/test_editor_files.py
import json

import pygame
import pytest

import level_config
from editor.files import revert_layout, save_layout
from editor.generated import generated_layout
from level_layout import parse_layout
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture

LAYOUT = parse_layout({'walls': [[3, 3]], 'start': [1, 1], 'exit': [7, 7],
                       'enemies': [{'type': 'static', 'cell': [5, 5]}], 'beacon': None}, 9)
DEFAULTS = {'seed': 3, 'maze': {'complexity': 'empty', 'grid_size': 9}}


def test_saving_adds_the_layout_and_keeps_every_other_key(tmp_path):
    path = tmp_path / '3.json'
    path.write_text(json.dumps({'seed': 7, 'maze': {'complexity': 'normal', 'grid_size': 9},
                                'enemies': {'static': 2}, 'hunter': False}))
    save_layout(str(path), LAYOUT, DEFAULTS)
    data = json.loads(path.read_text())
    assert data['seed'] == 7 and data['enemies'] == {'static': 2} and data['hunter'] is False
    assert parse_layout(data['layout'], 9) == LAYOUT
    assert 'created_by_editor' not in data


def test_saving_a_level_without_a_file_creates_one(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    data = json.loads(path.read_text())
    assert data['seed'] == 3 and data['maze'] == DEFAULTS['maze'] and data['created_by_editor'] is True
    assert parse_layout(data['layout'], 9) == LAYOUT


def test_the_saved_file_keeps_each_cell_on_one_line(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert '"start": [1, 1]' in path.read_text()


def test_reverting_removes_only_the_layout(tmp_path):
    path = tmp_path / '3.json'
    path.write_text(json.dumps({'seed': 7, 'enemies': {'static': 2}}))
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert revert_layout(str(path)) is True
    assert json.loads(path.read_text()) == {'seed': 7, 'enemies': {'static': 2}}


def test_reverting_a_file_the_editor_made_deletes_it(tmp_path):
    path = tmp_path / '30.json'
    save_layout(str(path), LAYOUT, DEFAULTS)
    assert revert_layout(str(path)) is True
    assert not path.exists()


def test_reverting_with_nothing_to_revert_changes_nothing(tmp_path):
    path = tmp_path / '3.json'
    assert revert_layout(str(path)) is False
    path.write_text(json.dumps({'seed': 7}))
    assert revert_layout(str(path)) is False
    assert json.loads(path.read_text()) == {'seed': 7}


def test_an_unwritable_path_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        save_layout(str(tmp_path / 'no' / 'such' / 'dir' / '3.json'), LAYOUT, DEFAULTS)


def test_a_generated_level_loads_as_the_layout_it_plays_as(game, monkeypatch):  # noqa: F811
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {
        'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12},
        'enemies': {'static': 2, 'flocker': 1, 'egg': 1}} if level == 3 else None)
    layout = generated_layout(game, 3)
    assert layout.grid_size == 12
    assert layout.grid() == game.maze.grid
    calc = game.maze.position_calculator
    assert layout.start == calc.screen_to_grid(game.ship.x, game.ship.y)
    assert layout.exit == calc.screen_to_grid(game.maze.exit.x, game.maze.exit.y)
    assert layout.counts()['static'] == 2 and layout.counts()['flocker'] == 1 and layout.counts()['egg'] == 1
    assert layout == parse_layout(layout.to_json(), 12)                      # and it is a playable layout


def test_playing_the_loaded_layout_gives_the_same_level(game, monkeypatch, tmp_path):  # noqa: F811
    plain = {'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12},
             'enemies': {'static': 2, 'flocker': 1}}
    files = {3: dict(plain)}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: files.get(level))
    layout = generated_layout(game, 3)
    before = (list(game.maze.grid), sorted(e.get_pos() for e in game.entity_manager.get_all_enemies()))
    files[3]['layout'] = layout.to_json()
    game.level = 3
    game.start_level()
    after = (list(game.maze.grid), sorted(e.get_pos() for e in game.entity_manager.get_all_enemies()))
    assert after[0] == before[0]
    # positions are cell centres now, so compare cells
    calc = game.maze.position_calculator
    cell = lambda pos: calc.screen_to_grid(*pos)
    assert sorted(map(cell, after[1])) == sorted(map(cell, before[1]))
```

- [ ] **Step 6: Write `editor/files.py` and `editor/generated.py`**

```python
# editor/files.py
"""Saving a layout into a level file, and taking it out again."""
import json
import os
import re

CREATED_MARKER = 'created_by_editor'


def level_path(level):
    from utils.resource_path import resource_path
    return resource_path(f'levels/{level}.json')


def _write(path, data):
    text = json.dumps(data, indent=2)
    text = re.sub(r'\[\s*(-?\d+),\s*(-?\d+)\s*\]', r'[\1, \2]', text)     # a cell on one line
    with open(path, 'w') as handle:
        handle.write(text + '\n')


def _read(path):
    with open(path) as handle:
        return json.load(handle)


def save_layout(path, layout, defaults):
    """Write `layout` into the level file, keeping every other key. A level with no file gets one made from
    `defaults` (its seed and maze), marked as the editor's own so that reverting can delete it again."""
    if os.path.exists(path):
        data = _read(path)
    else:
        data = {**defaults, CREATED_MARKER: True}
    data['layout'] = layout.to_json()
    _write(path, data)


def revert_layout(path):
    """Take the layout out of the level file. True if there was one. A file the editor made is deleted."""
    if not os.path.exists(path):
        return False
    data = _read(path)
    if 'layout' not in data:
        return False
    del data['layout']
    if data.get(CREATED_MARKER):
        os.remove(path)
    else:
        _write(path, data)
    return True
```

```python
# editor/generated.py
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
```

- [ ] **Step 7: Run the tests, adjust and commit**

Run: `venv/bin/python -m pytest tests/test_editor_model.py tests/test_editor_files.py -q 2>&1 | tail -10`
Expected: pass. If `test_a_generated_level_loads_as_the_layout_it_plays_as` fails because the start or exit cell falls outside the interior (`1..size-2`), the generator's corner is one cell in, so it should not; if two generated enemies share a cell the layout is invalid: in that case have `generated_layout` drop the later duplicate (keep the first) and say so in the commit message. Do not weaken the assertions.

```bash
git add editor tests/test_editor_model.py tests/test_editor_files.py
git commit -m "feat: the editor's model, level file saving and generated-level loading

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The editor screen and its wiring

**Files:**
- Create: `rendering/level_editor.py`
- Modify: `config.py` (state + `editor_enabled`), `rendering/main_menu.py`, `game_handlers/state_handlers.py`, `game.py`
- Test: `tests/test_level_editor.py`

**Interfaces:**
- Consumes: `EditorModel`, `PALETTE`, `editor.files`, `generated_layout`, `make_enemy`, `Maze(layout=)`.
- Produces:
  - `config.STATE_EDITOR`, `config.editor_enabled() -> bool` (the `ASTROVOID_EDITOR` variable is set and non-empty).
  - `LevelEditor(game, screen)` with `open_picker()`, `handle_key(event) -> bool`, `update(dt)`, `draw()`; attributes `mode` (`'picker'`, `'edit'`), `model`, `flash` (text), `confirm` (None or `(action, text)`).
  - A main-menu item `"EDITOR"` only when `config.editor_enabled()`; `Game.level_editor`.

- [ ] **Step 1: Read the three things to copy from**

Read `config.py` `observer_mode_enabled` (about line 921) for the env-var idiom, `rendering/menu_components.py` (`Button`, `render_pill`, `render_hint_row`, `build_panel`, `render_title`) for signatures, and `rendering/level_select_menu.py` for how the existing level grid is drawn; reuse their look. Also read how `Game.handle_events` hands `KEYDOWN` to `state_handler_registry` (game.py, `elif event.type == pygame.KEYDOWN:`) so the new handler receives keys.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_level_editor.py
import json
import os

import pygame
import pytest

import config
import level_config
from editor import files
from editor.model import PALETTE
from level_layout import parse_layout
from rendering.level_editor import LevelEditor
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode='')


@pytest.fixture
def editor(game, monkeypatch, tmp_path):  # noqa: F811
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    game.state = config.STATE_EDITOR
    monkeypatch.setattr(files, 'level_path', lambda level: str(tmp_path / f'{level}.json'))
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: (
        json.loads((tmp_path / f'{level}.json').read_text()) if (tmp_path / f'{level}.json').exists() else
        ({'seed': 5, 'maze': {'complexity': 'normal', 'grid_size': 12}, 'enemies': {'static': 2}}
         if level == 3 else None)))
    ed = LevelEditor(game, screen)
    ed.tmp = tmp_path
    return ed


def open_level(ed, level=3):
    ed.open_picker()
    ed.picker_index = level - 1
    ed.handle_key(key(pygame.K_RETURN))


def test_the_editor_env_var_gates_the_feature(monkeypatch):
    monkeypatch.delenv('ASTROVOID_EDITOR', raising=False)
    assert config.editor_enabled() is False
    monkeypatch.setenv('ASTROVOID_EDITOR', '')
    assert config.editor_enabled() is False
    monkeypatch.setenv('ASTROVOID_EDITOR', '1')
    assert config.editor_enabled() is True


def test_the_main_menu_has_an_editor_item_only_with_the_variable(monkeypatch):
    from rendering.main_menu import MainMenu
    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.delenv('ASTROVOID_EDITOR', raising=False)
    assert 'EDITOR' not in MainMenu(screen).menu_options
    monkeypatch.setenv('ASTROVOID_EDITOR', '1')
    options = MainMenu(screen).menu_options
    assert options.index('EDITOR') == options.index('QUIT') - 1


def test_the_picker_chooses_a_level_with_the_arrows_and_opens_it(editor):
    editor.open_picker()
    assert editor.mode == 'picker' and editor.picker_index == 0
    editor.handle_key(key(pygame.K_RIGHT))
    editor.handle_key(key(pygame.K_DOWN))
    assert editor.picker_index == 1 + editor.PICKER_COLUMNS
    editor.picker_index = 2
    editor.handle_key(key(pygame.K_RETURN))
    assert editor.mode == 'edit' and editor.model.level == 3 and editor.model.grid_size == 12


def test_escape_leaves_the_picker_for_the_main_menu(editor):
    editor.open_picker()
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.game.state == config.STATE_MENU


def test_arrows_tab_space_and_delete_edit_the_level(editor):
    open_level(editor)
    model = editor.model
    start = model.cursor
    editor.handle_key(key(pygame.K_RIGHT))
    assert model.cursor == (start[0] + 1, start[1])
    editor.handle_key(key(pygame.K_TAB))
    assert model.selected == PALETTE[1]
    editor.handle_key(key(pygame.K_TAB, pygame.KMOD_SHIFT))
    assert model.selected == 'wall'
    editor.handle_key(key(pygame.K_SPACE))
    assert model.contents(model.cursor) == 'wall' and model.dirty
    editor.handle_key(key(pygame.K_BACKSPACE))
    assert model.contents(model.cursor) is None


def test_saving_writes_the_layout_and_clears_the_dirty_mark(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_SPACE))                       # something to save (a wall, if it can)
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_s))
    data = json.loads((editor.tmp / '3.json').read_text())
    assert parse_layout(data['layout'], 12) == editor.model.to_layout()
    assert editor.model.dirty is False and 'saved' in editor.flash.lower()


def test_a_save_that_cannot_be_written_says_so_and_keeps_the_edits(editor, monkeypatch):
    open_level(editor)
    editor.model.dirty = True
    monkeypatch.setattr(files, 'level_path', lambda level: str(editor.tmp / 'no' / 'dir' / '3.json'))
    editor.handle_key(key(pygame.K_s))
    assert 'could not' in editor.flash.lower() and editor.model.dirty is True


def test_leaving_with_unsaved_edits_asks_first(editor):
    open_level(editor)
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.mode == 'edit' and editor.confirm is not None
    editor.handle_key(key(pygame.K_n))
    assert editor.confirm is None and editor.mode == 'edit'
    editor.handle_key(key(pygame.K_ESCAPE))
    editor.handle_key(key(pygame.K_y))
    assert editor.mode == 'picker'


def test_leaving_a_clean_level_does_not_ask(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_ESCAPE))
    assert editor.mode == 'picker' and editor.confirm is None


def test_x_asks_then_reverts_to_the_generated_level(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_s))                           # a layout now exists on disk
    assert (editor.tmp / '3.json').exists()
    editor.handle_key(key(pygame.K_x))
    assert editor.confirm is not None
    editor.handle_key(key(pygame.K_y))
    assert not (editor.tmp / '3.json').exists()                  # the editor made that file, so it is deleted
    assert 'revert' in editor.flash.lower() and editor.model.dirty is False


def test_x_with_no_layout_says_there_is_nothing_to_revert(editor):
    open_level(editor)
    editor.handle_key(key(pygame.K_x))
    assert editor.confirm is None and 'nothing' in editor.flash.lower()


def test_every_screen_and_palette_item_draws(editor):
    editor.open_picker()
    editor.update(0.016)
    editor.draw()
    open_level(editor)
    for index in range(len(PALETTE)):
        editor.model.palette_index = index
        editor.model.place()
        editor.update(0.016)
        editor.draw()
    editor.model.dirty = True
    editor.handle_key(key(pygame.K_ESCAPE))
    editor.draw()                                                # with the confirmation showing


def test_holding_an_arrow_repeats_and_releasing_stops(editor, monkeypatch):
    open_level(editor)
    start = editor.model.cursor
    editor.handle_key(key(pygame.K_RIGHT))
    pressed = {pygame.K_RIGHT: True}
    monkeypatch.setattr(pygame.key, 'get_pressed', lambda: type('K', (), {'__getitem__': lambda s, k: pressed.get(k, False)})())
    for _ in range(40):
        editor.update(0.05)
    assert editor.model.cursor[0] > start[0] + 2
    pressed.clear()
    stopped = editor.model.cursor
    for _ in range(10):
        editor.update(0.05)
    assert editor.model.cursor == stopped
```

- [ ] **Step 3: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_level_editor.py -q 2>&1 | tail -6`
Expected: collection error (`rendering.level_editor` missing) or `AttributeError: ... STATE_EDITOR`.

- [ ] **Step 4: Config, menu and handler wiring**

1. `config.py`: add `"editor": "editor",` to `STATES_DEFAULTS`, `STATE_EDITOR = STATES_DEFAULTS["editor"]` after `STATE_FUN`, and next to `observer_mode_enabled`:

```python
def editor_enabled() -> bool:
    """Whether the level editor is switched on (environment variable ASTROVOID_EDITOR, any non-empty value)."""
    return bool(os.environ.get('ASTROVOID_EDITOR'))
```
(Use whatever the file already imports for `os`; add `import os` if it does not.)

2. `rendering/main_menu.py`: build the options list as

```python
        self.menu_options = ["START GAME", "LEVELS", "FUN", "SELECT PROFILE", "CONTROLS", "QUIT"]
        if config.editor_enabled():
            self.menu_options.insert(self.menu_options.index("QUIT"), "EDITOR")
```

3. `game_handlers/state_handlers.py`: in `MenuStateHandler.handle_keyboard` and `handle_controller` add, next to each `"FUN"` branch,

```python
            elif selected_option == "EDITOR":
                game.level_editor.open_picker()
                game.state = config.STATE_EDITOR
```
(match the indentation of the sibling branch in each method), add

```python
class EditorStateHandler(StateHandler):
    """The level editor: the editor itself reads the keys."""

    def handle_keyboard(self, event, game):
        return game.level_editor.handle_key(event)

    def handle_controller(self, event, game):
        return False
```
and register `config.STATE_EDITOR: EditorStateHandler(),` in `StateHandlerRegistry`.

4. `game.py`: import `from rendering.level_editor import LevelEditor`; after `self.fun_menu = FunMenu(screen)` add `self.level_editor = LevelEditor(self, screen)`; in `update` next to the `STATE_FUN` branch:

```python
        if self.state == config.STATE_EDITOR:
            self.level_editor.update(dt)
            return
```
(copy the exact shape of the FUN branch); in `draw`'s chain add `elif self.state == config.STATE_EDITOR: self.level_editor.draw()` beside the FUN branch.

- [ ] **Step 5: Write `rendering/level_editor.py`**

Build it from these parts (reuse the menu look: `build_menu_backdrop`, `AnimatedBackground`, `get_font`, `menu_scale`, the colour constants the FUN menu uses). The test file fixes the behaviour; the structure:

```python
"""The level editor screen: a level picker, then a cell-by-cell editor drawn with the game's own maze and sprites."""
import math

import pygame

import config
import level_config
from editor import files
from editor.generated import generated_layout
from editor.model import PALETTE, EditorModel
from game_handlers.spawn_manager import make_enemy
from entities.command_recorder import CommandRecorder
from level_layout import ENEMY_TYPES
from maze.config import MazeComplexity
from maze.generator import Maze
from rendering.fonts import get_font
from rendering.menu_components import AnimatedBackground, build_menu_backdrop, menu_scale

LEVELS_SHOWN = 30
REPEAT_DELAY = 0.25          # seconds a cursor key is held before it repeats
REPEAT_INTERVAL = 0.05
FLASH_SECONDS = 2.0
ARROWS = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}

LABELS = {'wall': 'Wall', 'static': 'Static', 'patrol': 'Patrol', 'aggressive': 'Aggro', 'replay': 'Replay',
          'flocker': 'Flocker', 'flighthouse': 'Lighthouse', 'egg': 'Egg', 'anemone': 'Anemone',
          'split_boss': 'Split boss', 'mother_boss': 'Mother boss', 'rules_hunter': 'Rules hunter',
          'start': 'Start', 'exit': 'Exit', 'beacon': 'Jev beacon'}
```

Required members and behaviour:

- `PICKER_COLUMNS = 6`; `mode`, `picker_index`, `model`, `flash`, `flash_left`, `confirm`, `_held`/`_held_for`; `LevelEditor.__init__(game, screen)` builds the backdrop and `AnimatedBackground`, and fonts.
- `open_picker()`: `mode = 'picker'`, `confirm = None`, `flash = ''`, clear the held key; picker cells are levels `1..LEVELS_SHOWN`; mark those where `level_config.get_level_layout(level)` is not None.
- `handle_key(event) -> bool`: returns True when it used the key. With `confirm` set: `Y` or `Enter` runs the pending action, `N` or `Esc` cancels. Picker: arrows move `picker_index` within range (left/right by 1, up/down by `PICKER_COLUMNS`), Enter/Space opens (`_open_level`), Esc sets `game.state = config.STATE_MENU`. Edit: arrows move (and remember the key for repeat), Tab / Shift+Tab (`event.mod & pygame.KMOD_SHIFT`) and `[` `]` step the palette, number keys are not needed, Space places, Delete/Backspace removes, `S` saves, `X` reverts, Esc leaves.
- `_open_level(level)`: `layout = level_config.get_level_layout(level) or generated_layout(self.game, level)`; `self.model = EditorModel(level, layout)`; `mode = 'edit'`; `_preview = None`; `self.defaults = {'seed': level_config.get_level_seed(level), 'maze': {'complexity': level_config.get_maze_complexity(level).name.lower(), 'grid_size': layout.grid_size}}` (read before calling `generated_layout`, since that starts the level).
- `_save()`: `files.save_layout(files.level_path(level), model.to_layout(), self.defaults)`; on success `model.dirty = False`, flash `'Saved level N'`; catch `OSError` and flash `'Could not save: <reason>'`, leaving `dirty` set.
- `_ask_leave()`: if `model.dirty` set `confirm = ('leave', 'Discard unsaved changes?  Y / N')`, else `_leave()`; `_leave()` is `open_picker()`.
- `_ask_revert()`: if `files.level_path` has no layout (read the file with `level_config`-independent JSON read via `files._read`, treating a missing file or missing key as none) flash `'Nothing to revert: no layout saved'`; else `confirm = ('revert', 'Delete this layout and return to the generated level?  Y / N')`. On confirm: `files.revert_layout(path)`, then reopen the level (`_open_level`) and flash `'Reverted to the generated level'`; `model.dirty` is False.
- `update(dt)`: advance the background and a pulse phase; count down `flash_left`; the held-key repeat: if `_held` is set and `pygame.key.get_pressed()[_held]` is true, `_held_for += dt` and once it passes `REPEAT_DELAY` move every `REPEAT_INTERVAL`; if the key is no longer pressed clear `_held`. Held-key state clears on `open_picker` and `_leave`.
- `draw()`: picker or edit view as below, plus the flash line and, when `confirm` is set, a centred panel with its text.

Drawing the edit view:

- `_preview`: rebuilt whenever the model changes (compare a cheap signature: `(frozenset(walls), tuple(sorted(enemies.items())), start, exit, beacon)`): `Maze(level, complexity=MazeComplexity.EMPTY, grid_size=size, layout=model.to_layout())`; an entity list built with `make_enemy(kind, centre, level, CommandRecorder())` for every enemy except `rules_hunter`, which is a `RulesHunter(centre, _NullWorker(), _NoView())` (a `_NullWorker` with `busy=False`, `submit` returning True, `poll`/`cancel`/`close` doing nothing; `_NoView` with `maze`, `enemies()`/`threats()`/`pickups()` returning `[]`, `friend()` returning `None`). `maze.draw(screen)` draws rock and exit; then each entity's `draw` (`Enemy.draw(screen, None)`; the others `draw(screen)`; if an entity's `draw` needs something else, wrap in try/except `TypeError` and fall back to a coloured circle). Draw a `Ship` at the start cell facing the exit and a `JevBeacon` at the beacon cell.
- Cursor: a rounded rectangle on the cursor cell (`calc.grid_to_screen` top-left, `cell_size_x/y`) in the neon colour, with a gentle pulse (`0.5 + 0.5 * math.sin(phase)` on its alpha and width), and below/above it a small pill naming the cell's contents.
- Palette strip: in the left zone (`config.UI_ZONE_WIDTH` wide) a vertical list, one row per `PALETTE` entry: a small coloured chip plus `LABELS[item]`, the selected row lit with a panel highlight. Shrink the font until the longest label fits the zone.
- Header: `Level N` and `Unsaved` (dirty) or `Saved`, top of the zone. Bottom hint row (`render_hint_row` or plain pills): `Arrows move   Tab item   Space place   Del remove   S save   X revert   Esc back`.
- Picker: title `EDIT LEVELS`; a grid of `PICKER_COLUMNS` columns of level-number tiles (like the level-select menu), the chosen tile lit, a dot on levels that have a layout; the hint row `Arrows choose   Enter edit   Esc back`.

The editor must never raise from `draw` for any model state.

- [ ] **Step 6: Run the tests and iterate**

Run: `venv/bin/python -m pytest tests/test_level_editor.py -q 2>&1 | tail -12`
Expected: pass. Fix the code, not the tests, unless a test contradicts the spec.

- [ ] **Step 7: Regression, a real-display look, and commit**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -7` (expect only the 4 known local-setting failures).

Then look at it on the real driver, as in the earlier visual checks (see the project memory: the dummy SDL driver hides rendering bugs): write a script in the scratchpad that sets `SDL_VIDEODRIVER=cocoa`, makes a `pygame.HIDDEN` display at `config.SCREEN_WIDTH x config.SCREEN_HEIGHT`, builds a `Game`, sets `ASTROVOID_EDITOR=1`, opens the editor on level 12 (a boss level with several enemy types) and on level 25, places one of every palette item, calls `draw()` and saves `editor-picker.png`, `editor-12.png`, `editor-25.png`. Read those images and confirm: rock looks like the game, enemies show as sprites, the cursor glows, the palette strip is legible and nothing is clipped, the hint row fits. Fix anything off before committing; say what you saw.

```bash
git add rendering/level_editor.py rendering/main_menu.py game_handlers/state_handlers.py game.py config.py tests/test_level_editor.py
git commit -m "feat: the level editor, switched on by ASTROVOID_EDITOR

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Documentation and the final check

**Files:**
- Modify: `levels/README.md`, `README.md`

- [ ] **Step 1: `levels/README.md`**

Add the `layout` key to the Format section after the `hunter` bullet:

```markdown
- **layout**: an exact, hand-made level, written by the level editor. While it is present it replaces the generated maze, the random enemy positions and the `enemies` counts (they are kept, untouched, so removing the layout restores the generated level). `beacon` takes the place of `hunter`. A layout that cannot be played (a cell out of range, an enemy on a wall, a missing start) is ignored with a warning and the level generates from its seed.

```json
"layout": {
  "walls":   [[3, 3], [4, 3]],
  "start":   [1, 1],
  "exit":    [7, 7],
  "enemies": [{"type": "flocker", "cell": [2, 6]}],
  "beacon":  [3, 5]
}
```

Cells are `[col, row]`; the border ring is always wall. Types: static, patrol, aggressive, replay, flocker, flighthouse, egg, anemone, split_boss, mother_boss, rules_hunter. The editor does not check that the exit can be reached.
```

Add `"created_by_editor": true` to the note that the editor marks files it creates, and a line to the pacing section: `A saved layout on levels 1 to 24 must still satisfy these rules.`

- [ ] **Step 2: `README.md`**

Add a section "Level editor" near the level docs: `Run with ASTROVOID_EDITOR=1 (for example ASTROVOID_EDITOR=1 ./run.sh); an EDITOR item appears in the main menu.` followed by the key table from the spec (arrows, Tab / Shift+Tab, Space, Delete or Backspace, S, X, Esc), and the sentence that saving overwrites `levels/N.json` and git is the undo.

- [ ] **Step 3: Full run and a last look**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -7`
Expected: only the 4 known local-setting failures.

Run once by hand: `ASTROVOID_EDITOR=1 WINDOWED=1 ./run.sh`, choose EDITOR, open a level, place a wall and an enemy, save, quit, start that level from LEVELS and confirm it plays as laid out; then reopen it in the editor and press `X` to revert. Report what you saw; if anything is off, do not claim success. (`git checkout levels/` undoes any file the check wrote.)

- [ ] **Step 4: Commit**

```bash
git add levels/README.md README.md
git commit -m "docs: the level editor and the layout key

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
