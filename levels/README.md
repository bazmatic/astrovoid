# Level files

Levels 1 to 24 are a designed arc: each has a file here, `{level}.json`, that says exactly what is on it. Levels 25–30 also have custom files. Later levels come from the formulas in `level_rules.py` unless a file overrides them.

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

- **seed**: random seed for the maze, enemy positions and the bulges of the curved cave rock (so a level's rock is the same every time, hand-made layouts included). Default: the level number. Arc levels use `100 + level`.
- **maze.complexity**: `empty` (perimeter walls only), `simple`, `normal`, `complex` or `extreme`.
- **maze.grid_size**: width and height in cells, 5 to 100. Bigger means more, smaller cells.
- **enemies**: a count for each type. Anemone counts in a file are taken as given; the formulas would hold them to what the maze has room for.
- **vibehouse**: a pink Flighthouse variant that launches Neural-piloted Vibelets when its searchlight sees the player or an ally. It has five hit points and uses the Flighthouse launch cadence. Add it through the editor or an `enemies.vibehouse` count.
- **rules_hunter**: Rules hunters on the level (the Rules pilot's hunter ship as an enemy, hostile only to the player). A level with one is a boss level. Level 25 has one.
- **neural_hunter**: Neural hunters on the level (the neural pilot's hunter ship as an enemy, in magenta, hostile only to the player). Like the Rules hunter it takes 12 hits and makes a boss level. Without an installed neural model (`assets/neural/hunter.npz`) the level starts without it.
- **belemnite**: Belemnites on the level: spiky squids in pointed shells that chase the player as Jellies do, never overlapping one another. They have no guns, take 3 hits, and explode when they die, hurting the player, the hunter, nearby walls and other enemies (so one can set off the next).
- **hunter**: `false` forbids an ally. `{"earned": true}` allows enemy kills to drop a beacon only after 65% of the starting enemies have been defeated (at least four kills). The usual 3% drop chance still applies after that threshold. No beacon starts on an earned level. An explicit `{"spawn_cell": [col, row]}` remains available for custom encounters.
- **layout**: an exact, hand-made level, written by the level editor (see the main README). While it is present it replaces the generated maze, the random enemy positions and the `enemies` counts. Those are kept, untouched, so removing the layout restores the generated level. `beacon` takes the place of `hunter`. A layout that cannot be played (a cell out of range, an enemy on a wall, a missing start) is ignored with a warning and the level generates from its seed.

Generated mazes carve a connected network of broad corridors with continuous wall runs.
Complexity controls corridor density and the number of alternate routes; openings stay
at least roughly 70 pixels wide where the arena size allows. Corner rooms connect to
the same network as the rest of the maze. Seeds reproduce layouts, and training can
supply a different seed for each episode. Exact `layout` maps keep their authored geometry.

Level 31 introduces a Vibehouse in a central courtyard, with four offset entrances,
short walls for searchlight cover, and outer approach lanes. Two Crabs, two Flockers,
and two Belemnites guard the approaches. Destroy the Vibehouse to open the exit;
ammo is unlimited, and there are no gates or allied beacons.

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

  **walls** are drawn as curved cave rock over their cells (see Walls in the main README); the cells still decide what is open. The rock never pinches a passage or a gate's swing, and leaves the start, the exit, the beacon and each enemy as much room as square walls would.

  **strong_walls** (optional): wall blocks that no shot can destroy, drawn as riveted metal plate, and square (never curved). Use them where the player must not blast a way round, such as the walls of a pen whose only way in is its door. Everything that sees walls sees them; a shot at one strikes sparks and leaves no mark. A cell may be a wall or a strong wall, not both, and everywhere this page says "a wall" below, a strong wall counts too.

  **gates** (optional): each is a plank on a pin at the centre of `cell`. `angle` is in degrees clockwise on screen, a multiple of 45 from 0 up to but not including 180 (default 0, horizontal). `motor` is `"cw"` or `"ccw"` for a motor gate, and left out for a free gate. A gate may not share a cell with a wall, the start, the exit, the beacon, an enemy or another gate, and its plank (three cells long, so it covers its own cell and the one either side) may not cross a wall, leave the interior, cover the start, the exit, an anemone or a flighthouse, or share a cell with, cross or touch another gate's plank (planks that overlap would creep at rest); a layout that breaks this is ignored. Cells are not square on screen, so the game also measures each plank in pixels when the level starts: a gate whose plank would touch a wall or another plank there is left out (with a warning in the log). The level editor makes the same check on its own screen, so a gate placed there fits screens of that shape. A gate that doesn't fit the editor's screen (from a level saved on another screen, or written by hand) doesn't stop other edits; the cursor says "doesn't fit" over it, and R turns it to an angle that does.

  Cells are `[col, row]`; the border ring is always wall. Types: static, patrol, aggressive, replay, flocker, flighthouse, vibehouse, egg, anemone, split_boss, mother_boss, rules_hunter, neural_hunter, boss_viber, vibelet, belemnite. The editor does not check that the exit can be reached. A file the editor creates for a level that had none carries `"created_by_editor": true`, so reverting deletes it again.

## Boss levels

A level with at least one `split_boss`, `mother_boss` or `rules_hunter` is a boss level, whatever its number:

- the exit is locked until every enemy on the level is dead, including the ships a boss leaves behind and anything that hatches;
- ammo is infinite, so the level can always be finished;
- no Jev beacon appears, so no hunter flies, unless the file places one.

The campaign introduces a single Split Boss at 12, two at 18, and a Mother at 24. Piloted hunter encounters also use clear-all exits and unlimited ammo. Level 30 introduces the Boss Viber with two Vibelets.

## The hunter

The hunter is summoned by collecting a Jev beacon. Campaign levels 1–9 and the boss/duel encounters forbid allies. Other eligible campaign levels use `{"earned": true}`: first defeat 65% of the enemies present at the start, rounded up, with a minimum of four kills. Eligible kills can then drop one beacon at the normal 3% chance. It must still be collected to summon the ally.

Levels without files also have no starting beacon and use this earned-kill threshold wherever allies are allowed. Existing explicit spawn overrides remain supported for editor-authored encounters.

## Campaign progression

| First level | New threat | Introduction |
| --- | --- | --- |
| 1 | Urchin | Four passive targets |
| 2 | Crab | One shooter among familiar enemies |
| 3 | Jelly | One chaser |
| 4 | Egg | One egg; introduces the Squidlets it can hatch |
| 5 | Flocker | One flocker before mixed groups |
| 7 | Anemone | One anchored hazard |
| 8 | Squiddler | One tougher armed enemy |
| 9 | Belemnite | One explosive chaser |
| 10 | Flighthouse | One reinforcement spawner |
| 12 | Squiddler Boss | One boss with two flockers |
| 19 | Vibelet | One fragile neural ship |
| 21 | Viber | One full-sized neural ship |
| 23 | Terminator | One Rules pilot, after the Viber introduction |
| 24 | Mother | One Mother with a modest escort |
| 30 | Boss Viber | One boss with two familiar Vibelets |

Level 6 is a practice arena. Level 18 repeats Split Boss combat with two bosses.
Ordinary stages through 23 add only one starting enemy at a time, from four at
level 1 to 24 at level 23, with no sudden introductory swarms. Existing maze
walls, gates, starts and exits are retained except that the level 6 practice
arena is enlarged to avoid a maze-size drop. Enemy placements are retuned to
leave the opening clear. Counts in the file agree with its saved layout.

Level 25 remains a single-Terminator duel, and 26 a Viber encounter. Level 27's
Belemnite population is reduced from 27 to ten. Levels 28 and 29 keep their
specialist layouts and enemy mixes, with earned allies instead of starting
beacons. Neural encounters need the installed model, as before.

`tests/test_level_arc.py` checks the effective layouts, first appearances,
introductory counts, gradual crowd sizes, and spawn clearance. Removing a layout
restores the same enemy mix through its matching `enemies` block.

## Levels without a file

- **Ordinary levels from 25**: grid 32, `extreme`. The enemy count is 25 at level 25 and rises by one every two levels to 36 (`difficulty.maxEnemyCount`). Each added enemy goes to the next of aggressive, replay, flocker, static, patrol, anemone.
- **Every sixth level** (`difficulty.bossLevelInterval`) is a boss level in a 16-cell open arena: split bosses, then a mother boss, then both, gaining a boss each time round up to three.
- **Enemy speed and damage** grow 5% a level after level 4 and stop at 2.5 times.
- **An arc level whose file is missing** gets `3 + level` enemies of the types introduced by then.

## Level 28: Clockwork Reef

A gate-free, three-chamber hunt. Permanent reef walls put the main crossings at
opposite ends, creating an S-shaped route from the western start to the eastern
exit. Rock plugs in the other ends can be blasted into shortcuts. Belemnites
beside those plugs and the scattered cover make explosions useful, but dangerous
at close range.

Destroy both flighthouses (north in the middle chamber, south in the eastern
chamber) to open the exit. Other enemies may remain alive. Ammo is unlimited;
there is no hunter beacon and no neural model is required.

Start directly with `START_LEVEL=28 ./run.sh`.

## Level 29: Spiral Siege

A square spiral winds from the northwest start around the outside and into the
central exit chamber. Strong walls preserve the spiral; two three-block rock
sections let the player blast shortcuts through its coils. Belemnites beside
those sections make the shortcuts dangerous at close range.

Destroy both flighthouses, one on the outer turn and one in the core, to open
the exit. Ammo is unlimited. There are no gates, hunter beacons or neural enemies.

Start directly with `START_LEVEL=29 ./run.sh`.
