# Anemone: an enemy that pulls the ship off course

## Purpose

Every existing enemy chases, shoots or sits still. None of them acts on the player's motion, although momentum is the core of how the ship flies. The anemone fills that gap: a rooted creature that draws the ship toward it, so the player has to plan a path past it, burn against it, or shoot it to buy a window.

## Approved behaviour

### The pull

- The anemone never moves and is not knocked by shots.
- It pulls the player's ship toward its centre whenever all of these hold: the anemone is active, it is not stunned (see below), the ship is active, the ship's shield is not up, the ship's centre is within reach, and no active wall lies on the straight line between the two centres.
- Reach is `reachCells` (3.5) times the mean of the maze's cell width and height.
- Strength is an acceleration added to the ship's velocity each frame, directed at the anemone. It is zero at the edge of reach and rises linearly to `peakPull` at the anemone's surface (distance = anemone radius + ship radius): `peakPull * (1 - (d - contact) / (reach - contact))`, clamped to 0..`peakPull`.
- `peakPull` is `pullThrustFraction` (0.8) times `SHIP_THRUST_FORCE`, so a straight burn outward always wins.
- The pull is added once per update, exactly as thrust is (thrust is not scaled by `dt`), and the ship's speed is then capped at its normal maximum.
- Only the player is pulled. Projectiles, other enemies and the Jev hunter are unaffected.
- When several have hold of the ship, their pulls are added and the total is limited to `peakPull`, so a straight burn still wins.

### Getting caught

- Contact is handled like every other enemy: skipped while the shield is up, otherwise `ship.check_circle_collision` bounces the ship and `scoring.record_enemy_collision()` is called.
- On a contact that registers, the ship is additionally given an outward kick: its velocity is set to `flingSpeed` (5.0, under the 8.0 speed cap) directly away from the anemone.
- The anemone is then stunned for `releaseFrames` (60), so the ship is not dragged straight back in.

### Fighting it

- `hitPoints`: 4.
- Each projectile hit that does not kill it stuns it for `flinchFrames` (90). A stun never shortens one already running; it takes the longer of the two.
- While stunned it does not pull. Contact still hurts.
- A kill behaves like the flighthouse's: `die()`, destroy sound, kill credit for player shots, and the usual chance of a powerup crystal.
- The Jev hunter can see and shoot it like any other enemy.

### Where it appears

- Count by level (revised 2026-10-07, "lots after level 4"): 0 before `firstLevel` (4); from then `baseCount` (4) `+ (level - firstLevel) // levelsPerExtra` (2), capped at `maxCount` (8).
- That number is held to what the maze has room for: the fields of pull together cover at most `maxCoverage` (0.4) of the maze's cells, and there is always room for one.
- A level file may set `"anemone": n` under `enemies` to override; that number is used as given. `levels/4.json` sets 3.
- It takes positions from the same pool as other enemies, and none is placed within its reach of the player's start.

### Look

- A short fleshy column with a ring of about a dozen tentacles around a mouth, in pink with teal tips, drawn procedurally in the style of the urchin and squid.
- Tentacles sway at rest. When pulling, they lean toward the ship and the mouth glows in proportion to the current pull strength.
- A few faint streaks drift inward across its reach to show the range. They are dim enough not to be mistaken for projectiles and are not drawn while stunned.
- Stunned: tentacles fold in over the mouth and the colour dulls; they reopen over the last third of the stun.
- Death uses the shared dying hook (`die()`, `update_death`, `draw_death`) with a short wilt-and-fade.

## Components

- **`entities/anemone.py`**
  - `pull_acceleration(anemone_pos, anemone_radius, ship_pos, ship_radius, reach, peak_pull) -> (ax, ay)`: pure function, no pygame, no walls.
  - `Anemone`: owns position, radius, hit points, stun timer, animation phase. `update(dt)`, `take_damage() -> bool`, `stun(frames)`, `is_stunned`, `pull_on(ship, maze) -> (ax, ay)` (applies the conditions above, including the wall check), `draw`, plus the dying hook used by other enemies.
- **`game_handlers/entity_manager.py`**: an `anemones` list, cleared with the others and included in the spawn-position list, `get_all_active_enemies`, and the dying update/draw groups.
- **`game_handlers/enemy_updater.py`**: `update_anemones(anemones, dt, maze, ship, scoring)`: updates each one, applies its pull to the ship's velocity, handles contact, fling and release stun.
- **`game_handlers/collision_handler.py`**: a projectile-vs-anemone branch (damage, flinch stun or kill). `handle_projectile_enemy_collisions` gains an `anemones` argument.
- **`game_handlers/spawn_manager.py`**: one more spawn config.
- **`level_rules.py` / `level_config.py`**: `get_anemone_count(level)`, an `anemone` field on `EnemyCounts`, and the level-file override.
- **`config/settings.json` / `config.py`**: an `anemone` block (`size`, `hitPoints`, `reachCells`, `pullThrustFraction`, `flingSpeed`, `releaseFrames`, `flinchFrames`, `firstLevel`, `levelsPerExtra`, `maxCount`, `color`, `tipColor`).
- **`game.py`**: alias the list, call the updater, pass the list to the collision handler and to the hunter's perception, draw them, and include the count when requesting spawn positions.

The wall check uses `line_line_collision` from `utils.math_utils` against active walls, as the flighthouse's field-of-view check does; no new geometry code.

## Testing

Written first, in the style of the existing enemy tests.

- **Pull maths:** zero at and beyond reach; `peak_pull` at the surface; linear in between; always directed at the anemone; never exceeds `peak_pull`.
- **Pull conditions:** no pull when stunned, when the shield is up, or with a wall between; pull with a clear line.
- **Escape:** a ship at the surface thrusting straight out gains distance; a ship coasting past inside reach has its path bent toward the anemone.
- **Contact:** records one enemy collision, leaves the ship moving away at `flingSpeed`, and stuns the anemone; no effect with the shield up.
- **Damage:** survives three hits and dies on the fourth; each non-fatal hit stuns; kill credit, sound and crystal only on the last; a shorter stun does not cut a longer one.
- **Counts:** the level schedule above, and the level-file override.
- **Wiring:** an anemone is spawned on a level that should have one, appears in `get_all_active_enemies`, and dying ones are updated and drawn by the entity manager.
- **Visuals:** draws without error alive, pulling, stunned and dying; leaves the screen opaque; a pulling anemone is brighter at the mouth than an idle one.

Final check: a capture from the real game on the real display driver showing an anemone with the ship in reach.

## Out of scope

- Pulling projectiles, other enemies or the Jev hunter.
- Telling the Jev pilot about the pull.
- A moving or wall-mounted variant.
- New sounds; it reuses the existing collision and destroy sounds.
