# Level files

Levels 1 to 24 are a designed arc: each has a file here, `{level}.json`, that says exactly what is on it. Levels from 25 have no file and come from the formulas in `level_rules.py`.

A file can exist for any level, and can state as much or as little as it likes. Whatever it leaves out comes from the formulas.

## Format

```json
{
  "seed": 107,
  "maze": { "complexity": "normal", "grid_size": 20 },
  "enemies": {
    "static": 2, "patrol": 1, "aggressive": 2, "replay": 1,
    "flocker": 0, "flighthouse": 0, "egg": 0, "anemone": 2,
    "split_boss": 0, "mother_boss": 0
  },
  "hunter": false
}
```

- **seed**: random seed for the maze and enemy positions. Default: the level number. Arc levels use `100 + level`.
- **maze.complexity**: `empty` (perimeter walls only), `simple`, `normal`, `complex` or `extreme`.
- **maze.grid_size**: width and height in cells, 5 to 100. Bigger means more, smaller cells.
- **enemies**: a count for each type. Anemone counts in a file are taken as given; the formulas would hold them to what the maze has room for.
- **hunter**: leave it out for the normal rule. `false` means no Jev beacon, so no hunter. `{"spawn_cell": [col, row]}` places the beacon at that cell.

## Boss levels

A level with at least one `split_boss` or `mother_boss` is a boss level, whatever its number:

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

## Levels without a file

- **Ordinary levels from 25**: grid 32, `extreme`. The enemy count is 25 at level 25 and rises by one every two levels to 36 (`difficulty.maxEnemyCount`). Each added enemy goes to the next of aggressive, replay, flocker, static, patrol, anemone.
- **Every sixth level** (`difficulty.bossLevelInterval`) is a boss level in a 16-cell open arena: split bosses, then a mother boss, then both, gaining a boss each time round up to three.
- **Enemy speed and damage** grow 5% a level after level 4 and stop at 2.5 times.
- **An arc level whose file is missing** gets `3 + level` enemies of the types introduced by then.
