# Re-paced levels: a 24-level arc, boss levels, then a bounded endless game

## Purpose

The progression front-loads everything and then only gets more crowded. All ten enemy types have appeared by level 11 (six of them by level 5), the Jev hunter flies from level 1, maze size jumps around between hand-set and formula levels, and past level 20 the only thing that grows is the enemy count: 35 at level 20, 60 at level 40, in a 40x40 maze whose cells are about 28x21 px on a 1352x878 display.

This work replaces that with:

- a **designed arc of 24 levels** that introduces one thing at a time and rises steadily;
- **boss levels** at 6, 12, 18 and 24, built around the split boss and mother boss, with a locked exit;
- an **endless game from level 25** that keeps getting harder without getting more crowded.

Scoring, stars, enemy behaviour and the look of the game do not change.

## Terms

- **Ordinary level**: any level that is not a boss level.
- **Boss level**: a level whose configuration contains at least one split boss or mother boss.
- **Enemy count**: every enemy on the level except bosses and the hunter. Anemones are included.
- **Arena**: a small maze with complexity `empty` (perimeter walls only).

## 1. The arc (levels 1–24)

Every arc level has its own file, `levels/1.json` to `levels/24.json`, in the existing format. The table is the content of those files. Seeds are `100 + level`.

Columns: St static, Pa patrol, Ag aggressive, Rp replay ship, Fl flocker, Fh flighthouse, Eg egg, An anemone, SB split boss, MB mother boss.

| Level | Grid | Complexity | St | Pa | Ag | Rp | Fl | Fh | Eg | An | SB | MB | Count | Hunter | Purpose |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10 | empty | 4 | | | | | | | | | | 4 | no | Fly and shoot |
| 2 | 12 | simple | 2 | 2 | | | | | | | | | 4 | no | Patrol introduced |
| 3 | 14 | simple | 2 | 1 | 2 | | | | | | | | 5 | no | Aggressive introduced |
| 4 | 16 | simple | 2 | 1 | 1 | | | | | | | | 4 | yes | Hunter introduced |
| 5 | 18 | simple | 2 | 1 | 1 | 2 | | | | | | | 6 | yes | Replay ship introduced |
| 6 | 12 | empty | | | | 2 | | | | | 1 | | 2 | no | **Boss: split boss** |
| 7 | 20 | normal | 2 | 1 | 2 | 1 | | | | 2 | | | 8 | yes | Anemone introduced |
| 8 | 22 | normal | 2 | | | | 6 | | | 2 | | | 10 | yes | Flocker swarm introduced |
| 9 | 22 | normal | 2 | 2 | 2 | 1 | 2 | | | 2 | | | 11 | yes | Mix so far |
| 10 | 24 | normal | 2 | 2 | 2 | 1 | 2 | 1 | | 2 | | | 12 | yes | Flighthouse introduced |
| 11 | 24 | normal | 3 | 2 | 2 | 2 | 2 | 1 | | 2 | | | 14 | yes | Peak before the boss |
| 12 | 14 | empty | | | | | 6 | | | | 2 | | 6 | no | **Boss: two split bosses** |
| 13 | 26 | complex | 2 | 2 | 2 | 1 | 2 | 1 | 1 | 2 | | | 13 | yes | Egg introduced |
| 14 | 26 | complex | 3 | 2 | 2 | 2 | 2 | 1 | 1 | 2 | | | 15 | yes | |
| 15 | 28 | complex | | | | | 10 | 1 | 1 | 4 | | | 16 | yes | Flocker swarm |
| 16 | 28 | complex | 3 | 2 | 3 | 2 | 3 | 1 | 1 | 2 | | | 17 | yes | |
| 17 | 30 | complex | 3 | 3 | 3 | 2 | 3 | 1 | 1 | 3 | | | 19 | yes | Peak before the boss |
| 18 | 14 | empty | | | | | | | 4 | | | 1 | 4 | no | **Boss: mother boss** |
| 19 | 30 | extreme | 3 | 3 | 3 | 2 | 3 | 1 | 1 | 4 | | | 20 | yes | |
| 20 | 30 | extreme | 3 | 3 | 3 | 3 | 3 | 1 | 1 | 4 | | | 21 | yes | |
| 21 | 32 | extreme | 4 | 3 | 3 | 3 | 3 | 1 | 1 | 4 | | | 22 | yes | |
| 22 | 32 | extreme | 4 | 3 | 3 | 3 | 3 | 2 | 1 | 4 | | | 23 | yes | |
| 23 | 32 | extreme | 4 | 3 | 4 | 3 | 3 | 2 | 1 | 4 | | | 24 | yes | Peak before the boss |
| 24 | 16 | empty | | | | 2 | 2 | | 2 | | 1 | 1 | 6 | no | **Boss: mother and split boss** |

Every file states every enemy count explicitly (zeros included), its maze complexity and its grid size, so no arc level depends on a formula.

### Rules the arc obeys

These are checked by a test over the 24 files, so later tuning cannot break them silently.

- At most one enemy type appears for the first time on any level.
- From one ordinary level to the next ordinary level, the enemy count rises by at most 2 and never falls by more than 1. (Level 4 dips by one to make room for the hunter.)
- Bosses appear only on levels 6, 12, 18 and 24.
- Grid size never falls from one ordinary level to the next, and never exceeds 32.
- Anemone counts never exceed `anemones_that_fit(grid_size)`.

## 2. Boss levels

- **Exit lock.** The exit is locked while any split boss or mother boss is alive. This extends the existing rule that locks it while any egg is alive, and uses the same locked look and unlock ripple. The two rules combine: on a mother boss level the boss and every egg must be dead.
- **What does not hold the exit.** The two replay ships a boss leaves behind when it dies, and babies hatched from eggs, do not lock the exit.
- **The rule is general.** It is "any boss alive locks the exit", not "this is level 6". A level file that places a boss on any level gets the lock.
- **No hunter** on boss levels.
- **Infinite ammo** on boss levels, so a locked exit can never leave the player stuck with no shots. Each shot still costs score as usual.
- **Arena.** Boss levels use a small `empty` maze. The 300 px start clearance still applies, so the boss never starts next to the player.

## 3. The hunter

- New setting `game.hunterFirstLevel`, value 4. No hunter flies before it.
- From that level on, the hunter flies on every ordinary level (`hunterLevelInterval` stays 1 and keeps its meaning) and on no boss level.
- A level file can still override this either way: `"hunter": false` forbids it, and a `"hunter"` object places one, as today. Today any non-null value means "place one"; `false` becomes a new, explicit "none".

## 4. Endless (level 25 onward)

Levels from 25 have no files and are produced by `level_rules.py`.

### Ordinary levels

- **Maze:** grid 32, `extreme`. `difficulty.maxMazeSize` becomes 32.
- **Enemy count:** `min(36, 24 + (level - 23) // 2)`, so 25 at levels 25–26, rising by one every two levels and reaching 36 at level 47. Levels that are boss levels do not use this.
- **Mix:** start from the level 23 mix (St 4, Pa 3, Ag 4, Rp 3, Fl 3, Fh 2, Eg 1, An 4). Each extra enemy goes to the next type in the repeating order aggressive, replay, flocker, static, patrol, anemone. Flighthouses stay at 2 and eggs at 1. At the cap this gives St 6, Pa 5, Ag 6, Rp 5, Fl 5, Fh 2, Eg 1, An 6.
- **No bosses.**

### Boss levels

- Every sixth level: 30, 36, 42 and so on (`level % 6 == 0`).
- The kind cycles: split bosses, then mother boss, then both.
- Each full turn of that cycle adds one boss to every kind, up to three bosses on a level in total. Level 30 has 2 split bosses, 36 has 1 mother boss, 42 has one of each; 48 has 3 split bosses, 54 has 2 mother bosses, 60 has 2 split and 1 mother; from 66 on every boss level has three.
- Escorts match the arc: flockers with split bosses (6), eggs with the mother boss (4), and replay ships, flockers and eggs (2 each) with both.
- Arena of grid 16, `empty`. No hunter. Exit locked as in section 2.

### Strength

Difficulty past the count cap comes from the enemies themselves, but with ceilings, because two of today's curves have none.

| | Today | New |
|---|---|---|
| Patrol and aggressive speed | +10% per level after level 4, no ceiling (4.5x at level 40) | +5% per level after level 4, at most 2.5x (reached at level 35) |
| Damage | +10% per level after level 4, no ceiling | +5% per level after level 4, at most 2.5x |
| Fire interval | 5% shorter per level, floor at 60% | unchanged |
| Fire range | +5% per level, capped at 600 px | unchanged (already capped) |

`difficulty.tutorialLevels` stays 4 and keeps its meaning for these curves only.

### Levels 1–24 without a file

The formulas must still give a sane answer if an arc file is missing or unreadable (tests replace the loader, and a broken file should not produce a 36-enemy level 1). For a level below 25 with no file:

- enemy count is `min(24, 3 + level)`;
- only types already introduced by that level are used (patrol 2, aggressive 3, replay 5, anemone 7, flocker 8, flighthouse 10, egg 13), shared out in the same repeating order as the endless mix;
- grid size is `min(32, 10 + 2 * (level - 1))`, with complexity `empty` at level 1, `simple` to 5, `normal` to 11, `complex` to 17, `extreme` after;
- bosses only if `level % 6 == 0`, using the endless boss rules.

A test asserts all 24 files exist and load, so this path is a safety net, not the design.

## 5. Saved profiles

Bests and stars are stored by level number and would refer to different levels after this change.

- The profiles file gains a top-level `"levels_version": 2`.
- On load, a file with no version or a lower one has every profile's `bests` cleared. Each profile's unlocked `level` and `total_score` are kept. The file is saved straight away with the new version, so this happens once.
- New profile files are written with the version.

## 6. Code changes

- **`levels/`**: 24 files written from the table; `README.md` rewritten to match the real rules and the new `"hunter": false`.
- **`level_rules.py`**: new count, mix, maze, boss and strength rules above; `is_boss_level(level)` for levels without a file. The square-root count formulas for replay, flocker, flighthouse, egg, split boss and mother boss go away, with their `baseCount` and `scaleFactor` settings.
- **`level_config.py`**: `level_has_hunter` applies the first level, the boss-level rule and `false`; a helper answers "is this a boss level" from the resolved boss counts.
- **`game.py`**: the exit lock also checks for living bosses.
- **`profiles.py`**: version and one-off clearing of bests.
- **`config.py`, `config/settings.json`**: `game.hunterFirstLevel`, `difficulty.maxEnemyCount` (36), `difficulty.bossLevelInterval` (6), speed and damage growth and ceilings; `maxMazeSize` 32; anemone `firstLevel` 7. Removed settings are removed from both files.
- The stray `print` calls in `get_maze_complexity` are removed.

## 7. Testing

Tests are written first.

- **Arc:** all 24 files load; the rules in section 1 hold; each file matches the table for bosses and hunter.
- **Endless:** count formula and cap; the mix at levels 25, 35 and 47; boss levels fall on multiples of 6 with the right kind and number through level 66; ordinary endless levels have no bosses; speed and damage stop at their ceilings.
- **Fallback:** a level below 25 with no file gets a count and types within the bounds above.
- **Hunter:** none on levels 1–3, present on 4, absent on 6 and 30, `"hunter": false` respected, a placed hunter still placed.
- **Exit lock:** starting a real level with a boss, the exit is locked; killing the boss unlocks it even with the boss's two replay ships alive; with a mother boss it stays locked until the eggs are dead too.
- **Profiles:** an old file loads with bests cleared and level and total kept, and is rewritten with the version; a current file keeps its bests.
- **Existing tests** that pin the old schedule (`test_anemone_levels.py`, hunter interval tests) are updated to the new schedule.
- **Spawn room:** every arc level and endless levels 25, 47 and 66 place all their enemies at 1352x878 with the start clearance.

Then a played check on the real display of levels 4, 6, 12, 18, 24 and one endless level past 47. Whether the curve feels right is a judgement for play, and the level files are the place to tune it.

## Not included

- New boss enemies or new boss behaviour.
- Boss health bars, boss music, or any marking of boss levels in level select.
- Changes to scoring or star thresholds.
- Changes to how any enemy type behaves.
