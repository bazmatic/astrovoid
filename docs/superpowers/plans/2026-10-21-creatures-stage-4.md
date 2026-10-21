# Creatures and Traits, Stage 4 (Egg, Anemone, Flocker, Flighthouse) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Egg, Anemone, Flocker and Flighthouse (`egg`, `anemone`, `flocker`, `flighthouse`) onto Creatures,
and delete their classes, `EnemyUpdater`, and their hit loops. After this stage only the enemy hunters are not
Creatures.

**Architecture:** Each kind gets a Body moved out of its class (`egg`, `anemone`, `flocker`, `flighthouse`) and its
behaviour as traits: `grows` and `hatches` (Egg); `anchored`, `pullsShip` (a crowd trait), `flinchesWhenHit` and
`flingsShip` (Anemone); `flocks` (a crowd brain using `FlockerNeighborCache`) and `tweets` (Flocker); `scans` and
`launchesFlock` (Flighthouse). Each task deletes its kind's old update call and hit loop as it goes. Task 6 deletes
the classes.

**Tech Stack:** Python 3.10, pygame 2.6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md` (stage 4). Stages 1–3 are done; read
`creatures/` and `entities/squid.py` (how a Body was moved out of a class) before starting.

## Global Constraints

- Branch `refactor/enemy-catalogue`, starting from the commit that adds this plan. At `fcb0bd6` the full suite is 2221
  passed, 0 failed.
- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`. After
  every task the whole suite passes.
- Never stage `.codegraph/`, `assets/neural/hunter.npz` or `tools/ppo_neural.py` (someone else's uncommitted work:
  never stage, edit or revert it). Stage files by name.
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Units: velocities are px per frame at 60 FPS; `dt` counts frames. The Flighthouse's rates are per second
  (`dt / config.FPS`), as today.
- Numeric drift is allowed; behaviour must stay the same. Eggs grow, harden and hatch Squidlets, or burst when shot.
  Anemones stay rooted, pull the player's ship in when they can see it, fling it on contact and clamp shut when hit.
  Flockers flock, seek the nearest friend and fire together. Flighthouses sweep, lock on to the player and launch
  Flockers. Bit-identical play is not required.
- Kind keys never change. Use the glossary's words.
- `tuning` keeps only the Body's look. A trait's numbers go in its own catalogue entry. A `config.py` constant goes
  when its last reader goes; one still read elsewhere (level rules, spawning, the hunter) stays, taken from the
  catalogue.
- **Speed gate (Task 6):** a frame (update plus draw) on levels 1, 7, 8, 9, 15, 18 and 40 may be at most 20% slower
  than at this stage's start. Measure as stage 3 did: CPU time (`time.process_time`), alternating a worktree at the
  start commit with this stage's end, five rounds each, medians. Over 20%: stop, report the numbers to the user, and
  do not go on.
- Rendering changes are checked on the real display driver at 1352×878 (cocoa, `pygame.HIDDEN`, read pixels with
  `pygame.surfarray.pixels3d`), against a worktree of the previous commit. Clear the screen before each `draw_game()`.
- Compare each kind's behaviour with the previous commit the way stage 3 did (a short script over 1800 frames on a
  level with that kind; feed the command recorder a seeded random mix of player commands). Record the numbers in the
  commit message. A gap should be explained (a different random stream, say) before you accept it.

## Review Focus

1. **Hatching is not a kill**: a hatched Egg drops no pickup, scores nothing and leaves no death portrait; a burst
   one does all three. Pinned in Task 2 (`test_hatching_is_not_a_kill_and_bursting_is`).
2. **Several Anemones never pull harder than one at full strength**, a shield stops the pull, and a wall or gate
   between an Anemone and the ship stops that one's pull. Pinned in Task 3 (`test_anemones_together_pull_no_harder_than_one`,
   `test_a_wall_or_a_shield_stops_the_pull`).
3. **A blast does not move an anchored creature** (Anemone, Flighthouse): `handle_blast` adds velocity to anything
   without `apply_momentum`. Pinned in Task 3 (`test_a_blast_does_not_uproot_an_anchored_creature`).
4. **A Flighthouse watches the player only**, never the hunter, and a launched Flocker is a full Creature on the
   roster that first acts on the next frame. Pinned in Task 5 (`test_a_flighthouse_ignores_the_hunter`,
   `test_a_launched_flocker_is_a_creature_on_the_roster`).
5. **The death portrait** rescales what a Body keeps in world space (tentacles, the Egg's blobs). Stages 2–3 left
   this looking on the creature and on the deleted `jellyfish` attribute. Pinned in Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `rendering/enemy_death_portrait.py` | Rescale the Body's world-space state, not just the enemy's. |
| `entities/egg.py` → `EggBody` | The `egg` Body: sac, embryos, tears, jiggle, hatching or bursting. |
| `entities/anemone.py` → `AnemoneBody` | The `anemone` Body; `pull_acceleration` and `apply_pull` stay here as functions. |
| `entities/flocker_enemy_ship.py` → `entities/flocker.py` `FlockerBody` | The `flocker` Body: the bird, its wings, its death. |
| `entities/flighthouse_enemy.py` → `entities/flighthouse.py` `FlighthouseBody` | The `flighthouse` Body: base, lamp, beam, alert, launch flash, death. |
| `creatures/traits/growth.py` | `Grows`, `Hatches`. |
| `creatures/traits/rooted.py` | `Anchored`, `PullsShip`, `FlingsShip`. |
| `creatures/traits/combat.py` | `FlinchesWhenHit` (generic) replaces `BlinksWhenHit`. |
| `creatures/traits/flock.py` | `Flocks` (crowd brain), `Tweets`. |
| `creatures/traits/lighthouse.py` | `Scans`, `LaunchesFlock`. |
| `entities/flocker_neighbor_cache.py` | Kept, for `Flocks`. |
| `game_handlers/enemy_updater.py` | Deleted in Task 6. |

---

### Task 1: The death portrait rescales the Body

**Files:**
- Modify: `rendering/enemy_death_portrait.py`
- Test: `tests/test_enemy_death.py`

**Interfaces:**
- Produces: `EnemyDeathPortrait` rescales `tentacles` (chains of points) and `blobs` (with `x`, `y`, `radius`,
  `vx`, `vy`) on the enemy **and on `enemy.body`** when it has one. The lookup of `enemy.jellyfish` goes.

- [ ] **Step 1: Write the failing test**

`test_a_portrait_draws_its_squids_and_jellies_tentacles_on_its_own_surface`: for `'aggressive'` and `'replay'`, build
the creature at (4000, 3000), settle its Body's tentacles (60 Body updates), `die()`, `deepcopy`, wrap in
`EnemyDeathPortrait(snapshot, 40)`, and before any `update` assert every tentacle point of `portrait.enemy.body` lies
inside `(0, portrait.size)` on both axes.

- [ ] **Step 2: Run it to make sure it fails**

Expected: FAIL. The points are still near (4000, 3000).

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite**

- [ ] **Step 5: Commit**

### Task 2: The Egg as a Creature

**Files:**
- Create: `creatures/traits/growth.py`, `tests/test_egg_creature.py`
- Modify: `entities/egg.py` (the class becomes `EggBody`), `creatures/registry.py`, `config/enemies.json` (`egg`),
  `config.py`, `creatures/traits/spawning.py` (`LaysEggs` reads the egg's grown size from its `grows` entry),
  `game.py` (stop calling `update_eggs`), `game_handlers/collision_handler.py` (`shoot_into` passes `[]` for eggs),
  `tests/test_egg_visuals.py`, `tests/test_squidlet_creature.py`, `tests/test_spawn_in_open.py`,
  `tests/test_enemy_death.py`

**Interfaces:**
- Produces:
  - `grows` → `Grows(to: float, rateMin: float, rateMax: float, hitPointsGrown: int)`. `on_spawn` rolls
    `c.growth_rate` in `[rateMin, rateMax]`, remembers `c.start_radius = c.radius` and
    `c.start_hit_points = c.max_hit_points`, and sets `c.growth = 0.0`. `on_frame` adds the rate to `c.radius` (capped
    at `to`), sets `c.growth` (0 to 1), and rescales `max_hit_points` linearly from `start_hit_points` to
    `hitPointsGrown` (rounded), keeping the share of damage taken, as `Egg.update` does.
  - `hatches` → `Hatches(into: str, countMin: int, countMax: int, spread: float)`. `__init__` rejects an unknown kind.
    `on_spawn` rolls `c.hatch_count`. `on_frame`, once `c.growth >= 1`, spawns `hatch_count` creatures of kind `into`
    (open spots between `spread / 2` and `spread` away, as `Egg.pop` does). It then sets `c.hatched = True` and calls
    `c.die()` directly, **not** `enc.kill`: no pickup, no kill counted, no sound.
  - Body `egg` → `entities.egg.EggBody(creature)`: everything `Egg` draws and animates (sac, embryos, tears, blobs,
    the hatched or burst death). It reads `c.radius`, `c.growth`, `c.hatch_count`, `c.hatched`, `c.hit_points`,
    `c.max_hit_points` and `c.death_progress`. Trait-kept state it reads before the first frame (`growth`,
    `hatch_count`, `hatched`) counts as 0 / 1 / False, so a fresh egg draws (editor preview). On `hit` it jiggles.
    `DEATH_DURATION = 30.0`.
- Catalogue `egg`: `tuning` keeps `size` (8, the laid size) and `color`. Traits in order: `coasts`,
  `bouncesOffWalls`, `ramsShip`, `shovedByShots`, `takesHits {"hitPoints": 2}`,
  `grows {"to": 24, "rateMin": 0.01, "rateMax": 0.04, "hitPointsGrown": 4}`,
  `hatches {"into": "baby", "countMin": 1, "countMax": 3, "spread": 60}`, `dropsPickup`.
- `config.EGG_MAX_SIZE` and `EGG_INITIAL_SIZE` stay while `hunter/spawn.py` and others read them, taken from the
  catalogue. The rest of `EggSettings` goes when nothing reads it.

- [ ] **Step 1: Write the failing tests**

`tests/test_egg_creature.py`:
- `test_an_egg_grows_hardens_and_hatches_squidlets`: an Egg with `rateMin = rateMax = 1.0` in an Encounter hatches
  on frame 16. Its hit points go 2 → 4 on the way. It leaves `hatch_count` Squidlet Creatures on the roster.
- `test_hatching_is_not_a_kill_and_bursting_is`: a hatching egg calls neither `collision_handler.drop_pickup` nor
  `record_kill`; an egg shot to death calls both once.
- `test_a_shot_shoves_an_egg`.
- `test_a_fresh_egg_draws` and `test_a_hatched_and_a_burst_egg_die_differently` (the Body's `ending`).
- `test_a_mother_lays_creature_eggs`: `LaysEggs` puts an `egg` Creature on the roster.

Move `tests/test_egg_visuals.py` onto the Body (as stage 3 moved the squid's), `Egg.pop` callers onto `Hatches`, and
the Egg in `tests/test_enemy_death.py`'s lists onto `creatures.build('egg', …)`.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement, moving the drawing out of `Egg` into `EggBody` unchanged**

- [ ] **Step 4: Run the full suite; compare on level 18 (Mother and eggs) and level 13; check on the real display**

- [ ] **Step 5: Commit**

### Task 3: The Anemone as a Creature

**Files:**
- Create: `creatures/traits/rooted.py`, `tests/test_anemone_creature.py`
- Modify: `entities/anemone.py` (the class becomes `AnemoneBody`; `pull_acceleration` and `apply_pull` stay),
  `creatures/registry.py`, `creatures/traits/combat.py` (`FlinchesWhenHit` replaces `BlinksWhenHit`),
  `entities/squid.py` (`flinch` event), `config/enemies.json` (`anemone`, `replay`), `config.py`, `game.py` (stop calling
  `update_anemones`; drop the `reach_px` loop in `start_level`), `game_handlers/collision_handler.py` (no anemones
  in `shoot_into`), `tests/test_anemone.py`, `tests/test_anemone_game.py`, `tests/test_anemone_visuals.py`,
  `tests/test_gates_seen.py`, `tests/test_enemy_death.py`, `tests/test_traits_combat.py`,
  `tests/test_squiddler_creature.py`, `tests/test_squid.py`

**Interfaces:**
- Produces:
  - `anchored` → `Anchored`: `on_spawn` remembers `c.anchor`. `on_frame` puts the creature back on its anchor and
    zeroes its velocity. Also add `Creature.apply_momentum(vx, vy)`, which adds to the velocity. `Anchored` stops
    that working by holding the creature in place, so `handle_blast` treats every Creature through the same path.
  - `pullsShip` → `PullsShip(reachCells: float, strength: float)`, `CROWD = True`. `on_spawn` sets
    `c.reach_px = reachCells * (maze.cell_size_x + maze.cell_size_y) / 2`. `on_crowd` adds up each live member's
    pull on
    `enc.ship`:
    - each pull is `pull_acceleration(...)` with peak `strength * config.SHIP_THRUST_FORCE`;
    - none from a member that is flinching (`c.flinch_timer > 0`);
    - none while the ship is shielded or inactive, or when a wall or gate is in the way (`Anemone._wall_between`,
      moved);
    - the total is capped at one Anemone's peak, then given to the ship with `apply_pull`;
    - it keeps `c.pull_fraction` and `c.pull_angle` for the Body.
  - `flinchesWhenHit` → `FlinchesWhenHit(frames: float, on: list[str] = ['hit'])`, in `creatures/traits/combat.py`,
    replacing `BlinksWhenHit`. It is generic: any creature can have it, and its Body decides what a flinch looks
    like. On any event in `on` it calls `flinch(c, frames, enc)`, a module function that:
    - sets `c.flinch_timer` and `c.flinch_total` to `frames`, never shortening a flinch already running;
    - emits `flinch` every time, even mid-flinch (a squid restarts its blink on each event, as today).
    `on_spawn` sets `c.flinch_timer = c.flinch_total = 0`; `on_frame` counts `c.flinch_timer` down by `dt`.
    Other traits read `c.flinch_timer > 0` to hold back while flinching (`PullsShip` does).
    - The squids: the `blink` event becomes `flinch`; the Squid Body starts a blink on it, its blink length still
      its own (30 frames, scaled by damage). The `replay` entry (the only one with it today) replaces
      `blinksWhenHit` with `flinchesWhenHit {"frames": 30, "on": ["hit", "hit_wall", "rammed"]}`, in the same place.
      `BlinksWhenHit` is deleted; `tests/test_squiddler_creature.py` and `tests/test_squid.py` follow the rename.
  - `flingsShip` → `FlingsShip(speed: float, releaseFrames: float)`: on `rammed`, throws `enc.ship` straight back
    out at `speed` (`Anemone.fling`, moved), puts itself back on its anchor, and flinches for `releaseFrames` (`flinch(c, releaseFrames, enc)`).
  - Body `anemone` → `entities.anemone.AnemoneBody(creature)`: the drawing and the sway and streak animation. It reads
    `c.flinch_timer`, `c.flinch_total`, `c.pull_fraction`, `c.pull_angle`, `c.reach_px` and the hit points; missing
    trait state counts as 0.
- Catalogue `anemone`: `tuning` keeps `size`, `color`, `tipColor`. Traits in order: `anchored`, `ramsShip`,
  `flingsShip {"speed": 5.0, "releaseFrames": 60}`, `pullsShip {"reachCells": 3.5, "strength": 0.8}`,
  `flinchesWhenHit {"frames": 90}`, `takesHits {"hitPoints": 4}`, `dropsPickup`.
  `firstLevel` and `maxCoverage` are level rules, not the Anemone's behaviour. They stay in `tuning` while
  `level_rules`/`level_config` read them; say so in a comment in `config.py`.
- `config.ANEMONE_REACH_CELLS` stays while `game.py`'s spawn keep-clear reads it, taken from the `pullsShip` entry.

- [ ] **Step 1: Write the failing tests**

`tests/test_anemone_creature.py`:
- `test_an_anemone_pulls_the_ship_toward_it`.
- `test_anemones_together_pull_no_harder_than_one`: three anemones around the ship; the change in its velocity is
  at most `0.8 * SHIP_THRUST_FORCE`.
- `test_a_wall_or_a_shield_stops_the_pull`.
- `test_touching_it_flings_the_ship_out_and_it_lets_go`: after a ram the ship moves away at 5.0 and the anemone is
  flinching for 60 frames.
- `test_a_hit_clamps_it_shut_for_90_frames` and `test_four_hits_kill_it`.

`tests/test_traits_combat.py` (generic flinch, on a `RecordingBody` creature):
- `test_a_flinch_lasts_its_frames_and_a_new_one_never_shortens_it`: `frames=90`, a hit, 60 frames, then a flinch of
  10 via `flinch`: `flinch_timer == 30`; 30 more frames and it is 0.
- `test_it_flinches_only_on_its_events`: `on=['hit_wall']`; a `hit` emits no `flinch`, a `hit_wall` emits one.
- `test_a_squid_blinks_when_it_flinches`: a built `replay` is rammed; its Body is blinking. A built `baby` is not.
- `test_a_blast_does_not_uproot_an_anchored_creature`: `handle_blast` at its side, then one Encounter step: it is
  where it was, at rest.

Move `tests/test_anemone*.py` and the Anemone uses in `tests/test_gates_seen.py` and `tests/test_enemy_death.py`
onto Creatures. In `tests/test_anemone_game.py`, the cases that call `update_anemones` or
`handle_projectile_enemy_collisions` go through the Encounter.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite; compare on levels 7 (13 anemones) and 15; check on the real display**

- [ ] **Step 5: Commit**

### Task 4: The Flocker as a Creature

**Files:**
- Create: `creatures/traits/flock.py`, `entities/flocker.py`, `tests/test_flocker_creature.py`
- Modify: `entities/flocker_neighbor_cache.py` (works on any objects with `x`, `y`, `vx`, `vy`, `active`),
  `creatures/traits/combat.py` (`Gun` keeps `c.just_fired`), `creatures/registry.py`, `config/enemies.json`
  (`flocker`), `config.py`, `game.py` (stop calling `update_flockers`), `hunter/duel_enemies.py` (stop calling
  `update_flockers`), `game_handlers/collision_handler.py` (no flockers in `shoot_into`),
  `entities/flighthouse_enemy.py` (`_spawn_flocker` builds a Creature until Task 5), `tests/test_enemy_death.py`,
  `tests/test_hunter_targeting.py`
- Delete: `entities/flocker_enemy_ship.py` (its drawing moves to `entities/flocker.py`)

**Interfaces:**
- Produces:
  - `Gun` sets `c.just_fired` to True on the frame it fires, and False on every other frame.
  - `flocks` → `Flocks(separationRadius, alignmentRadius, cohesionRadius, separationWeight, alignmentWeight,
    cohesionWeight, seekWeight, closeRange, closeAngle, syncChance)`, `CROWD = True`, `REQUIRES = ('thrusters', 'gun')`.
    `on_crowd` builds one `FlockerNeighborCache` over the crowd, then sets each member's controls for the **next**
    frame. (At the end of a frame the positions are those the next frame starts from, so the old order is kept.)
    - **Steering**: separation, alignment and cohesion from the cache, and seek toward `enc.target_for(c)`, with
      their weights (the `_calculate_*_cached` maths, moved). It turns (`turn = ±1`) when more than
      `2 * SHIP_ROTATION_SPEED` off the wanted heading, and thrusts when within 45°.
    - **Firing**: it fires (`fire`, `aim` = target) when the target is within `c.gun_range`, the gun is loaded, and
      either the target is within `closeRange` and within `closeAngle` of its heading, or, with chance `syncChance`,
      a neighbour within `cohesionRadius` `just_fired` or is about to (gun cooldown at most `0.2 * FPS`).
  - `tweets` → `Tweets(chance: float, quietMin: float, quietMax: float)`: when its quiet time has run out, each frame
    it plays `enc.world.sound_manager.play_tweet()` with this chance. Then it is quiet for a random `quietMin` to
    `quietMax` frames: that is what today's code does, though its comment says seconds.
  - Body `flocker` → `entities.flocker.FlockerBody(creature)`: the bird, the wing flap, the death.
- Catalogue `flocker`: `tuning` keeps `size`, `color`. Traits in order: `flocks {…today's numbers…, "closeRange": 150,
  "closeAngle": 30, "syncChance": 0.8}`, `thrusters {"speedShare": 0.4}`, `gun {"intervalMin": 300, "intervalMax": 300,
  "strengthLevel": 1}`, `ramsShip`, `tweets {"chance": 0.01, "quietMin": 3, "quietMax": 8}`, `takesHits {"hitPoints": 1}`,
  `dropsPickup`.

- [ ] **Step 1: Write the failing tests**

`tests/test_flocker_creature.py`:
- `test_flockers_keep_apart_and_head_for_their_target`: eight Flockers bunched together and a target 600 px away;
  after 120 frames none overlap and their mean distance to the target has dropped.
- `test_a_flocker_fires_at_close_range_when_facing_its_target`.
- `test_a_neighbour_firing_sets_off_the_flock`: one member `just_fired`; with `syncChance = 1` a loaded neighbour
  within the cohesion radius fires on the next frame.
- `test_one_hit_kills_a_flocker` and `test_a_fresh_flocker_draws`.

Move the Flocker cases in `tests/test_enemy_death.py` and `tests/test_hunter_targeting.py`. The latter's last
`update_X` case becomes `test_a_creature_targets_the_nearest_hunter[flocker]`.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite (with `tests/test_duel_enemies.py`); compare on level 8 (33 flockers); check on the real display**

- [ ] **Step 5: Commit**

### Task 5: The Flighthouse as a Creature

**Files:**
- Create: `creatures/traits/lighthouse.py`, `entities/flighthouse.py`, `tests/test_flighthouse_creature.py`
- Modify: `creatures/registry.py`, `config/enemies.json` (`flighthouse`), `config.py`, `game.py` (stop calling
  `update_flighthouses`), `game_handlers/collision_handler.py` (no flighthouses in `shoot_into`),
  `tests/test_flighthouse_visuals.py`, `tests/test_gates_seen.py`, `tests/test_enemy_hit_points.py`,
  `tests/test_enemy_death.py`
- Delete: `entities/flighthouse_enemy.py` (its drawing moves to `entities/flighthouse.py`)

**Interfaces:**
- Produces:
  - `scans` → `Scans(coneDegrees: float, range: float, scanSpeed: float, trackSpeed: float)`, speeds in degrees
    per second. It watches the **player's ship only** (`enc.ship`, when active and not an observer), never the
    hunter.
    - It sees the ship when the ship is within `range`, within half the cone of `c.angle`, and no active wall or gate
      lies between them.
    - While it sees the ship it turns toward it at `trackSpeed`; otherwise it sweeps at `scanSpeed`.
    - It sets `c.sees_target` and `c.sighted_at` (the ship's position), and emits `sighted` on the frame it first
      sees the ship.
  - `launchesFlock` → `LaunchesFlock(into: str, speed: float)`. `on_spawn` sets `c.launch_cooldown = 0`.
    - It counts the cooldown down in seconds, and clears it on `sighted`.
    - While `c.sees_target` and the cooldown is done, it spawns `into` at its own position, facing `c.sighted_at`.
      The launch speed is `speed` × the child's top speed, read from the child's `thrusters` entry.
    - It then resets the cooldown to `level_rules.get_flighthouse_spawn_interval(c.level)` and emits `launched`.
  - Body `flighthouse` → `entities.flighthouse.FlighthouseBody(creature)`: base, lamp, beam (with its cache), alert
    (rising on `sees_target`), launch flash (on `launched`), death. Beam length and cone come from the `scans`
    entry's numbers, kept on the creature by `Scans.on_spawn` (`c.scan_range`, `c.scan_cone`).
- Catalogue `flighthouse`: `tuning` keeps `size`, `color`. Traits in order: `anchored`,
  `scans {"coneDegrees": 45, "range": 600, "scanSpeed": 90, "trackSpeed": 240}`,
  `launchesFlock {"into": "flocker", "speed": 0.8}`, `ramsShip`, `takesHits {"hitPoints": 5}`, `dropsPickup`.
  `spawnIntervalSeconds` stays in config while `level_rules.get_flighthouse_spawn_interval` reads it.

- [ ] **Step 1: Write the failing tests**

`tests/test_flighthouse_creature.py`:
- `test_it_sweeps_until_it_sees_the_player_then_tracks_and_launches`.
- `test_a_wall_or_a_gate_hides_the_player`.
- `test_a_flighthouse_ignores_the_hunter`: only the hunter is in its cone, and nothing launches.
- `test_a_launched_flocker_is_a_creature_on_the_roster`: the launched Flocker is facing the player at
  `0.8 × 0.4 × SHIP_MAX_SPEED`, and its first `on_frame` runs on the next frame.
- `test_five_hits_kill_it` and `test_a_fresh_flighthouse_draws`.

Move `tests/test_flighthouse_visuals.py` onto the Body, and the Flighthouse uses in `tests/test_gates_seen.py`,
`tests/test_enemy_hit_points.py` and `tests/test_enemy_death.py` onto Creatures.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite; compare on level 10 (one flighthouse) and level 15; check on the real display**

- [ ] **Step 5: Commit**

### Task 6: Delete the rest; the speed gate

**Files:**
- Delete: `game_handlers/enemy_updater.py`
- Modify: `game.py` (no `EnemyUpdater`), `hunter/duel_enemies.py` (no updater), `game_handlers/collision_handler.py`
  (`handle_projectile_enemy_collisions` keeps only the enemy hunters' loop, renamed `shoot_enemy_hunters(projectile,
  enemy_hunters) -> bool`, which `shoot_into` calls), `game_handlers/spawn_manager.py` (`make_enemy` builds every
  non-hunter kind with `creatures.build`), `config.py`, `main.py`, `ARCHITECTURE.md`, `GLOSSARY.md`, the test
  fixtures that build an `EnemyUpdater` (`tests/test_hunter_integration.py` and others: grep)
- Test: every test still importing a deleted name

- [ ] **Step 1: Delete, then run `grep -rn "enemy_updater\|EnemyUpdater\|FlockerEnemyShip\|FlighthouseEnemy\|from entities.egg import Egg\b\|from entities.anemone import Anemone\b" --include=*.py .`**

Expected: no hits outside `docs/`.

- [ ] **Step 2: Move or delete the remaining tests; keep the list (file::test, one line why)**

- [ ] **Step 3: Run the full suite**

- [ ] **Step 4: Speed gate**, as the Global Constraints say. Record the table in the validation file.

- [ ] **Step 5: Docs**: `ARCHITECTURE.md` (the four Bodies, the new traits, `EnemyUpdater` gone, "Adding New Enemy
  Types" now has no "otherwise" branch for non-hunters) and `GLOSSARY.md` (the Creatures line).

- [ ] **Step 6: Commit**

### Task 7: Hand back to the user

- [ ] **Step 1: Report**

- The speed numbers.
- What changed in play (the comparisons from Tasks 2–5).
- Every test deleted, with its reason.
- Anything in stage 5 (the enemy hunters) this work showed to be wrong.

Ask whether to write the plan for stage 5.
