# Level files

Levels 1 to 24 are a designed arc: each has a file here, `{level}.json`, that says exactly what is on it. Levels from 25 have no file, except level 25 (the Rules hunter boss), and come from the formulas in `level_rules.py`.

A file can exist for any level, and can state as much or as little as it likes. Whatever it leaves out comes from the formulas.

## Format

```json
{
  "seed": 107,
  "maze": { "complexity": "normal", "grid_size": 20 },
  "enemies": {
    "static": 2, "patrol": 1, "aggressive": 2, "replay": 1,
    "flocker": 0, "flighthouse": 0, "egg": 0, "anemone": 2,
    "split_boss": 0, "mother_boss": 0, "rules_hunter": 0
  },
  "hunter": false
}
```

- **seed**: random seed for the maze and enemy positions. Default: the level number. Arc levels use `100 + level`.
- **maze.complexity**: `empty` (perimeter walls only), `simple`, `normal`, `complex` or `extreme`.
- **maze.grid_size**: width and height in cells, 5 to 100. Bigger means more, smaller cells.
- **enemies**: a count for each type. Anemone counts in a file are taken as given; the formulas would hold them to what the maze has room for.
- **rules_hunter**: Rules hunters on the level (the Rules pilot's hunter ship as an enemy, hostile only to the player). A level with one is a boss level. Level 25 has one.
- **neural_hunter**: Neural hunters on the level (the neural pilot's hunter ship as an enemy, in magenta, hostile only to the player). Like the Rules hunter it takes 12 hits and makes a boss level. Without an installed neural model (`assets/neural/hunter.npz`) the level starts without it.
- **belemnite**: Belemnites on the level: spiky squids in pointed shells that chase the player as Jellies do, never overlapping one another. They have no guns, take 3 hits, and explode when they die, hurting the player, the hunter, nearby walls and other enemies (so one can set off the next).
- **hunter**: leave it out for the normal rule. `false` means no Jev beacon, so no hunter. `{"spawn_cell": [col, row]}` places the beacon at that cell.
- **layout**: an exact, hand-made level, written by the level editor (see the main README). While it is present it replaces the generated maze, the random enemy positions and the `enemies` counts. Those are kept, untouched, so removing the layout restores the generated level. `beacon` takes the place of `hunter`. A layout that cannot be played (a cell out of range, an enemy on a wall, a missing start) is ignored with a warning and the level generates from its seed.

```json
"layout": {
  "walls":   [[3, 3], [4, 3]],
  "strong_walls": [[5, 3]],
  "start":   [1, 1],
  "exit":    [7, 7],
  "enemies": [{"type": "flocker", "cell": [2, 6]}],
  "beacon":  [3, 5],
  "gates":   [{"cell": [5, 5], "angle": 45, "motor": "cw"}, {"cell": [6, 3]}]
}
```

  **strong_walls** (optional): wall blocks that no shot can destroy, drawn as riveted metal plate. Use them where the player must not blast a way round, such as the walls of a pen whose only way in is its door. Everything that sees walls sees them; a shot at one strikes sparks and leaves no mark. A cell may be a wall or a strong wall, not both, and everywhere this page says "a wall" below, a strong wall counts too.

  **gates** (optional): each is a plank on a pin at the centre of `cell`. `angle` is in degrees clockwise on screen, a multiple of 45 from 0 up to but not including 180 (default 0, horizontal). `motor` is `"cw"` or `"ccw"` for a motor gate, and left out for a free gate. A gate may not share a cell with a wall, the start, the exit, the beacon, an enemy or another gate, and its plank (three cells long, so it covers its own cell and the one either side) may not cross a wall, leave the interior, cover the start, the exit, an anemone or a flighthouse, or share a cell with, cross or touch another gate's plank (planks that overlap would creep at rest); a layout that breaks this is ignored. Cells are not square on screen, so the game also measures each plank in pixels when the level starts: a gate whose plank would touch a wall or another plank there is left out (with a warning in the log). The level editor makes the same check on its own screen, so a gate placed there fits screens of that shape. A gate that doesn't fit the editor's screen (from a level saved on another screen, or written by hand) doesn't stop other edits; the cursor says "doesn't fit" over it, and R turns it to an angle that does.

  Cells are `[col, row]`; the border ring is always wall. Types: static, patrol, aggressive, replay, flocker, flighthouse, egg, anemone, split_boss, mother_boss, rules_hunter, neural_hunter, boss_viber, vibelet, belemnite. The editor does not check that the exit can be reached. A file the editor creates for a level that had none carries `"created_by_editor": true`, so reverting deletes it again.

## Boss levels

A level with at least one `split_boss`, `mother_boss` or `rules_hunter` is a boss level, whatever its number:

- the exit is locked until every enemy on the level is dead, including the ships a boss leaves behind and anything that hatches;
- ammo is infinite, so the level can always be finished;
- no Jev beacon appears, so no hunter flies, unless the file places one.

In the arc these are levels 6, 12, 18 and 24.

## The hunter

The hunter is summoned by collecting a Jev beacon. Without a `hunter` entry: no beacon before level 4 (`game.hunterFirstLevel`), none on boss levels, and one placed in the maze on every other level (`game.hunterLevelInterval`). Wherever a beacon is allowed, a destroyed enemy can also drop one (`powerups.jevBeaconSpawnChance`) while no hunter is flying.

## Pacing rules for the arc

`tests/test_level_arc.py` checks these, so a level can be retuned freely as long as they hold:

- at most one enemy type appears for the first time on any level;
- from one ordinary level to the next, the enemy count (everything except bosses) rises by at most 2 and falls by at most 1;
- bosses appear only on levels 6, 12, 18 and 24;
- ordinary mazes never shrink and stop at 32;
- anemones fit the maze.

A saved layout on levels 1 to 24 must still satisfy these rules.

## Levels without a file

- **Ordinary levels from 25**: grid 32, `extreme`. The enemy count is 25 at level 25 and rises by one every two levels to 36 (`difficulty.maxEnemyCount`). Each added enemy goes to the next of aggressive, replay, flocker, static, patrol, anemone.
- **Every sixth level** (`difficulty.bossLevelInterval`) is a boss level in a 16-cell open arena: split bosses, then a mother boss, then both, gaining a boss each time round up to three.
- **Enemy speed and damage** grow 5% a level after level 4 and stop at 2.5 times.
- **An arc level whose file is missing** gets `3 + level` enemies of the types introduced by then.
