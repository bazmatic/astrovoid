# The level editor

Date: 2026-10-15. Status: design, awaiting review.

## Purpose

Levels are generated from a seed, a maze complexity and enemy counts, so a designer can tune how many enemies a level
has but not where anything is. This adds a small in-game editor to lay a level out by hand: walls, every enemy type,
the player's start, the exit and the Jev beacon. It is switched on by an environment variable, is operated with the
arrow keys, and should look as good as the game's own menus.

Success: a level can be opened, changed cell by cell, saved, played as laid out, and reverted to its generated form.

## What was decided

- **Explicit layout in the level file** (not tweaks on top of the seed, not a blank canvas): the editor opens a level
  as it plays today and saving writes exact positions. Files without a layout behave exactly as before.
- **Entry:** with `ASTROVOID_EDITOR=1` the main menu gains an **EDITOR** item. Without the variable the item does not
  exist.
- **Placeable:** walls, all eleven enemy types, the player's start, the exit, and the Jev beacon spot.
- **Palette strip** to choose what to place.
- **Saving overwrites `levels/N.json`**; git is the undo. No playtest key and no undo/redo in the editor.
- **Delete reverts a level to its generated form** by removing its layout.

## The level file

A level file gains one optional key:

```json
"layout": {
  "walls":   [[col, row], ...],
  "start":   [col, row],
  "exit":    [col, row],
  "enemies": [{"type": "flocker", "cell": [col, row]}, ...],
  "beacon":  [col, row]
}
```

- `walls` are the interior rock cells. The border ring is always walls and is not listed.
- `type` is one of `static`, `patrol`, `aggressive`, `replay`, `flocker`, `flighthouse`, `egg`, `anemone`,
  `split_boss`, `mother_boss`, `rules_hunter`.
- The Jev beacon is `layout.beacon` (`null` for none). While a layout exists it takes the place of the `hunter` key,
  which is left untouched.
- `maze.grid_size` still sets the grid (square, as now). `seed`, `maze.complexity` and `enemies` are left alone by
  the editor.

**With a layout, the layout rules.**

- The maze grid is built from `walls` plus the border. `start` and `exit` place the ship and the exit portal.
- Enemies are created at their own cells, one each, by the same constructors the spawn manager uses. The random
  position picking is skipped. A Rules hunter gets its pilot worker as it does today.
- Enemy counts (`level_config.get_level_*_count`, `get_level_enemy_counts`, `is_boss_level`) are read from the layout's
  enemy list while a layout exists, so boss-level behaviour (exit locked, infinite ammo, no beacon) follows what is
  actually placed.
- The `enemies` counts in the file are ignored while a layout exists and are never rewritten, so removing the layout
  gives back exactly the level that was there before.

A layout is checked when it loads: cells in range, no enemy or start or exit on a wall, start and exit not the same
cell. A layout that fails the check is ignored with a logged warning and the level generates from its seed.

## The editor

A new game state `STATE_EDITOR`, entered from the main menu.

**Level picker.** A grid of level numbers (1 to 30, scrolling on from there). Arrows and Enter choose, Esc returns to
the menu. A level with a layout is marked.

**Loading a level to edit.** If the file has a layout, that is loaded. Otherwise the editor runs the real
`start_level()` for that level and reads back the grid, the ship's start, the exit and every enemy's type and cell, so
what is edited is what plays today. (Any Rules hunter worker created is closed at once.)

**Editing view.**

- The maze is drawn with the game's own rock renderer, so blocks look as they do in play.
- Enemies, the start ship, the exit and the beacon are drawn as their real sprites at their cells, not animated.
- A glowing cursor marks the current cell. The cell's contents show beside it.
- A palette strip runs down the left, where the in-game HUD sits: Wall, the eleven enemies, Start, Exit, Beacon, with
  the selected item lit.
- A hint row along the bottom lists the keys.

**Keys.**

| Key | Action |
|---|---|
| Arrows | Move the cursor |
| Tab, Shift+Tab (or `[` `]`) | Next or previous palette item |
| Space | Place the selected item at the cursor |
| Delete, Backspace | Remove what is at the cursor |
| S | Save |
| X | Delete the layout: revert this level to its generated form (asks first) |
| Esc | Back to the picker (asks first if there are unsaved edits) |

**Rules.**

- The border cells cannot be edited.
- One enemy per cell; placing on an occupied cell replaces it. A wall cell holds nothing else, and placing a wall
  removes whatever was there.
- Start, exit and beacon are single items: placing one moves it.
- Start and exit cannot go on a wall or on each other.

## Saving and reverting

- **Save** writes the file with `layout` added or replaced and every other key kept as it was. A file that does not
  exist yet (levels without one) is created with `seed` and `maze.grid_size` from the level as it generated. A short
  "saved" flash confirms it. A file the editor creates also carries `"created_by_editor": true`; that marker is how
  revert knows to delete it.
- **Revert** (`X`) removes the `layout` key. If the file contained nothing else the generator needs (it was created by
  the editor), the file is deleted so the level falls back to its formulas. The editor then reloads the level in its
  generated form. It asks first, and says what will be lost.
- Both act on the file on disk, and the game reads level files afresh each time, so the next play shows the change.

## Look

The editor uses the menus' styling: animated backdrop, neon panels, pill-shaped key hints, the menu fonts and
`COLOR_NEON_*` colours. The cursor and the selected palette item pulse gently. Nothing needs the mouse.

## Tests and documentation

Tests:

- a layout builds the maze it describes (walls, start, exit) and spawns each enemy at its cell and only those;
- `is_boss_level` and the count getters follow a layout; removing the layout restores the file's own counts;
- an invalid layout is ignored with a warning and the level generates from its seed;
- loading a generated level into the editor and saving it unchanged plays the same level;
- editing rules: border not editable, one enemy per cell, wall clears a cell, start and exit are single;
- save keeps the other keys; revert removes only the layout, and deletes an editor-created file;
- the EDITOR menu item exists only with `ASTROVOID_EDITOR` set;
- the editor draws every palette item and the picker without error on the real driver.

Documentation: the `layout` key in `levels/README.md`, and the editor's keys and variable in `README.md`.

## Risks

- A saved layout for levels 1 to 24 must still satisfy `tests/test_level_arc.py` (pacing rules). The editor does not
  enforce them; the test catches a violation.
- The layout path is a second way to build a level. Both must produce a playable level (start and exit reachable);
  the editor does not check that the exit can be reached.

## Out of scope

- Playtesting from inside the editor, undo and redo, resizing the grid, choosing the maze complexity or seed.
- Mouse editing.
- Checking that the exit is reachable from the start.
- Per-enemy settings (speeds, health), or a non-square grid.
