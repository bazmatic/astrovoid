# Creatures and Traits, Stage 3 (the Squids) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Squiddler, Squidlet, Squiddler Boss and Mother (`replay`, `baby`, `split_boss`, `mother_boss`) onto
Creatures, and delete `ReplayEnemyShip`, `Baby`, `SplitBoss`, `MotherBoss` and their update and hit loops.

**Architecture:** One `squid` Body draws all four kinds. Five new traits do what the classes did: `replaysPlayer` (a
Brain), `thrusters` (Propulsion, sharing the ship physics with `RotatingThrusterShip` through a new `physics/thrust.py`),
`blinksWhenHit`, `splitsOnDeath` and `laysEggs`. The Encounter gains `spawn`, so traits can put new enemies on the
roster. Eggs stay old code this stage; they hatch Squidlets through `make_enemy`.

**Tech Stack:** Python 3.10, pygame 2.6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md` (stage 3). Stages 1–2 are done
(`docs/superpowers/plans/2026-10-20-creatures-stage-1-2.md`); read `creatures/` before starting. It is small.

## Global Constraints

- Branch `refactor/enemy-catalogue`, starting from commit `4479984` (stage 2, the retrained neural pilot, and `main`
  merged in, which brought the Belemnite as a Creature). At that commit the full suite is 2190 passed, 0 failed.
- `tools/ppo_neural.py` has someone else's uncommitted work in it: never stage, edit or revert it.
- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`. After
  every task the whole suite passes.
- Never stage `.codegraph/` or `assets/neural/hunter.npz`. Stage files by name.
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Units: velocities are px per frame at 60 FPS; `dt` counts frames.
- Numeric drift in movement is allowed; behaviour must stay the same. Squiddlers fly the player's recorded moves, turn
  to face the target when the recording is idle, and fire when lined up. Bosses split into Squidlets. Mothers lay eggs.
  Bit-identical play is not required.
- Only the Squiddler blinks when hit, rammed or bounced off a wall, as today. Bosses and Squidlets do not.
- Kind keys (`replay`, `baby`, `split_boss`, `mother_boss`) never change. Use the glossary's words (GLOSSARY.md).
- `tuning` keeps only the Body's look (and `windowSize`, which the command recorder reads). A trait's numbers go in
  its own catalogue entry. A `config.py` constant goes when its last reader goes.
- **Speed gate (Task 5):** a frame (update plus draw) on levels 1, 8, 9 and 40 may be at most 20% slower than the
  stage 1 baseline in `docs/superpowers/validation/2026-10-20-frame-times.md`, and on levels 18, 42 and 48 at most
  20% slower than Task 1's baseline. Over that: stop, report the numbers to the user, and do not go on.
- Rendering changes are checked on the real display driver at 1352×878 (cocoa, `pygame.HIDDEN`, read pixels with
  `pygame.surfarray.pixels3d`), not only the dummy driver. Clear the screen before each `draw_game()` when capturing.
- Experiment tests that pin one seeded episode (`tests/test_experiment_*.py`) may fail from drift. Before changing
  one, run the same check on the previous commit across a few seeds. Make it look across seeds; never only loosen a
  limit, and the reworked test must also pass on the previous commit.

## Review Focus

1. **A boss killed by the hunter's shot** still splits into Squidlets and drops its pickup roll. Pinned in Task 4
   (`test_a_boss_killed_by_the_hunter_still_splits`).
2. **A Squiddler before the recording fills, or with no target** (observer mode, empty recorder) coasts without
   crashing and fires only at a target. Pinned in Task 2 (`test_before_the_window_fills_a_squiddler_only_coasts` and
   `test_with_no_target_a_squiddler_turns_nowhere_and_holds_fire`).
3. **The death portrait**: `deepcopy` of a killed squid copies its tentacles and draws its withdrawal. Pinned in Task 2
   (`test_a_dead_squiddler_copies_for_its_portrait`).
4. **The display-only squids** on the splash screen and the level-complete screen are never stepped by an Encounter,
   and still animate and draw. Pinned by `tests/test_splash_scene.py` and `tests/test_menu_visuals.py` (Task 2).
5. **Children and eggs land in open space**: a boss's Squidlets are never inside a wall, and a laid egg has room to
   grow. Pinned in Task 4 (`tests/test_spawn_in_open.py`, moved onto the traits).

---

## File Structure

| File | Responsibility |
|---|---|
| `physics/thrust.py` | Ship physics on any object with `x y vx vy angle radius prev_x prev_y`: thrust, coast, cap speed, sweep walls, turn toward. |
| `entities/rotating_thruster_ship.py` | Keeps its methods; their bodies call `physics/thrust.py`. Loses `avoid_enemy_ships` and `is_enemy_ship` (dead since stage 2). |
| `entities/squid.py` | The `squid` Body: mantle, tentacles, eyes and blinking, jet, death withdrawal. |
| `creatures/traits/brains.py` | Adds `ReplaysPlayer`. |
| `creatures/traits/propulsion.py` | Adds `Thrusters`. |
| `creatures/traits/combat.py` | `Gun` gains `strengthLevel`, `startsLoaded` and shot styling; adds `BlinksWhenHit`. |
| `creatures/traits/spawning.py` | `SplitsOnDeath`, `LaysEggs`. |
| `creatures/encounter.py` | Adds `spawn`. |
| `config/enemies.json`, `config.py`, `config/settings.json` | The four entries; settings that move out of `tuning`. |
| `rendering/splash_scene.py`, `rendering/level_complete_menu.py` | Their display squids are built Creatures. |
| `entities/egg.py` | Hatches Squidlets through `make_enemy`. |
| `hunter/spawn.py` | Reads the squids' sizes from the catalogue. |

---

### Task 1: Squid baseline and the shared thruster physics

**Files:**
- Create: `physics/thrust.py`
- Modify: `entities/rotating_thruster_ship.py` (`apply_thrust`, `update`, `check_wall_collision` call the new
  functions), `docs/superpowers/validation/2026-10-20-frame-times.md`
- Test: `tests/test_thrust_physics.py`

**Interfaces:**
- Produces, in `physics/thrust.py` (each acts on any object with `x`, `y`, `vx`, `vy`, `angle`, `radius`, `prev_x`,
  `prev_y`):
  - `apply_thrust(body, force: float, max_speed: float) -> None`: adds `force` along `body.angle`, then caps the speed
    at `max_speed`.
  - `coast(body, dt: float, friction: float) -> int`: saves `prev_x`/`prev_y`, applies friction and moves, then
    bounces off the screen edges (restitution `config.COLLISION_RESTITUTION`). Returns how many edges it bounced off.
  - `cap_speed(body, max_speed: float) -> None`.
  - `sweep_walls(body, walls, spatial_grid=None) -> bool`: the swept collision of `check_wall_collision`, from
    `(prev_x, prev_y)` to `(x, y)`, including the already-inside push-out. True on a hit.
  - `turn_toward(body, heading: float, rate: float) -> None`: snaps to `heading` when within `rate` degrees, else
    turns `rate` degrees toward it (as `ReplayEnemyShip._rotate_towards_player`).
- `RotatingThrusterShip.update` keeps its order: `coast`, call `on_edge_collision()` once per edge it returned, the
  thrust particles, then `cap_speed`. `check_wall_collision` calls `sweep_walls` and then `on_wall_collision()` on a
  hit. Behaviour of `Ship`, `HunterShip` and `FlockerEnemyShip` is unchanged, bit for bit.

- [ ] **Step 1: Record the squid baseline at `4479984`**

Run three times: `venv/bin/python -m tools.frame_timer --levels 18 42 48 --frames 600 --seed 1`
Expected: three rows each run. Add a "Squid baseline (4479984)" table with the medians to the validation file (level
18: a Mother and four eggs; 42: every squid kind; 48: three Squiddler Bosses).

- [ ] **Step 2: Write the failing tests**

`tests/test_thrust_physics.py`, on a `SimpleNamespace` body:
- `test_thrust_adds_force_along_the_heading_and_caps_speed`: angle 90, force 0.5, max 1.0, four thrusts →
  `vx == pytest.approx(0)`, `vy == pytest.approx(1.0)`.
- `test_coast_slows_moves_and_bounces_off_an_edge`: body at `x = radius - 1`, `vx = -2`: returns 1, `vx > 0`,
  `x == radius`, and `prev_x` is the position before the move.
- `test_sweep_walls_stops_a_fast_body_at_the_wall`: `prev_x = 100`, `x = 200`, a wall at x = 150 → True and
  `x < 150`.
- `test_turn_toward_snaps_within_one_step_and_turns_otherwise`: from 0 toward 3 at rate 5 → 3; from 0 toward 90 at
  rate 5 → 5; from 0 toward 270 at rate 5 → 355.
- `test_the_ships_fly_as_before`: a `HunterShip` thrusting and turning for 120 frames next to a wall in a small maze,
  with `random.seed(0)`, ends at the position, velocity and particle count recorded by running the same test body at
  `4479984` first (write the numbers into the test).

- [ ] **Step 3: Run them to make sure they fail**

Expected: FAIL, because `physics.thrust` cannot be imported.

- [ ] **Step 4: Implement `physics/thrust.py` and make `RotatingThrusterShip` call it**

Move the code; do not rewrite the maths.

- [ ] **Step 5: Run the new tests and the full suite**

Expected: all pass, with no change to `tests/test_ship.py`, `tests/test_hunter_*.py` or `tests/test_experiment_*.py`.

- [ ] **Step 6: Commit**

```bash
git add physics/thrust.py entities/rotating_thruster_ship.py tests/test_thrust_physics.py \
  docs/superpowers/validation/2026-10-20-frame-times.md
git commit -m "refactor: the thruster ships' physics as functions any body can use, and the squid baseline"
```

### Task 2: The Squiddler as a Creature

**Files:**
- Create: `entities/squid.py`, `tests/test_squid.py`, `tests/test_squiddler_creature.py`
- Modify: `creatures/traits/brains.py`, `creatures/traits/propulsion.py`, `creatures/traits/combat.py`,
  `creatures/registry.py`, `config/enemies.json` (`replay`), `config.py` (`ReplayEnemySettings` loses `hitPoints`;
  `REPLAY_ENEMY_HIT_POINTS` goes if nothing reads it), `game.py` (stop calling `update_replay_enemies`),
  `game_handlers/collision_handler.py` (`shoot_into` passes `[]` for `replay_enemies`),
  `rendering/splash_scene.py`, `rendering/level_complete_menu.py`, `tests/test_exit_policies_game.py`,
  `tests/test_hunter_targeting.py`, `tests/test_enemy_hit_points.py`

**Interfaces:**
- Consumes: Task 1's `physics/thrust.py`; stage 1–2's `Creature`, `Encounter`, `Gun`, `RamsShip`, `TakesHits`,
  `DropsPickup`.
- Produces:
  - Body `squid` → `entities.squid.Squid(creature)`. The drawing, tentacles, blinking, jet and death withdrawal of
    `ReplayEnemyShip`, moved over and reading the creature: `x`, `y`, `angle`, `radius`, `hit_points`,
    `max_hit_points`, `death_progress`. `DEATH_DURATION = 36.0`, `DEATH_FRICTION = 0.85`. Its own state:
    `tentacles`, `pulse_phase`, `jet`, `blink_timer`, `blink_state`, `is_blinking`, `blink_frame`.
    `update(c, dt, target)` advances the blink, the jet's decay and the tentacles. `on_event`: `thrust` raises `jet` by
    `JET_GAIN` (capped at 1); `blink` starts or restarts a blink (`trigger_blink`). Keep reading `config.REPLAY_ENEMY_COLOR`
    and the `MOTHER_BOSS_*` blink and glow constants, as today (all squids share them).
    `ReplayEnemyShip` stays as it is until Task 5: the other three kinds still use it.
  - `thrusters` → `Thrusters(speedShare: float, thrust: float = config.SHIP_THRUST_FORCE,
    turnRate: float = config.SHIP_ROTATION_SPEED, friction: float = config.SHIP_FRICTION)`. Its maximum speed is
    `speedShare * config.SHIP_MAX_SPEED`. `on_spawn` sets `c.prev_x, c.prev_y`. `on_frame`: turn toward
    `controls.heading` (`turn_toward`), or by `controls.turn * turnRate`; on `controls.thrust`, `apply_thrust` and emit
    `thrust`; then `coast`, `cap_speed`, and `sweep_walls` against `enc.maze`, emitting `hit_wall` on a hit.
  - `replaysPlayer` → `ReplaysPlayer(fireAngle: float = config.REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE)`,
    `REQUIRES = ('thrusters', 'gun')`. `on_spawn`: `c.replay_index = 0`. `on_frame` clears the controls, then:
    once `c.recorder` holds at least `config.REPLAY_ENEMY_WINDOW_SIZE` commands, it plays
    `get_replay_commands()[c.replay_index]` and steps the index round the list: `NO_ACTION` → `heading` = the target's
    bearing (none with no target), `ROTATE_LEFT` → `turn = -1`, `ROTATE_RIGHT` → `turn = 1`, `APPLY_THRUST` →
    `thrust`. Whatever the recording, when a target is within `c.gun_range` and within `fireAngle` of `c.angle`, it
    sets `thrust`, `fire`, and `aim` to the point `c.gun_range` ahead along `c.angle` (the squid fires where it
    faces). A `c.recorder` of None counts as an empty recording.
  - `Gun` gains `strengthLevel: Optional[int] = None` (the level whose strength fills omitted numbers; default the
    creature's), `startsLoaded: bool = False` (cooldown starts at 0), and shot styling: `shotSpeed: float = 1.0`
    (scales the projectile's `vx`, `vy`), `impact: float = 1.0`, `glowColor: Optional[list] = None`,
    `glowRadius: float = 1.0`, `glowIntensity: float = 0.0` (passed to `Projectile` as `impact_force_multiplier`,
    `glow_color` (a tuple), `glow_radius_multiplier`, `glow_intensity`).
  - `blinksWhenHit` → `BlinksWhenHit`: `on_event` emits `blink` on `hit`, `hit_wall` or `rammed`.
- Catalogue `replay`: `tuning` keeps `windowSize`, `size`, `color`. Traits in order: `replaysPlayer`,
  `thrusters {"speedShare": 0.3}`, `ramsShip`, `gun {"strengthLevel": 1, "startsLoaded": true}`, `blinksWhenHit`,
  `takesHits {"hitPoints": 3}`, `dropsPickup`.
- The display squids: `SplashScene.squid` and `LevelCompleteMenu.failed_squids` become `creatures.build('replay',
  (0.0, 0.0))`. They set the creature's `x`, `y`, `radius`, `angle` and the body's `jet`/`tentacles` as they set the
  ship's today, and animate with `squid.body.update(squid, dt, None)` where they called `squid.animate(dt)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_squiddler_creature.py` (use `tests/creature_parts.py`; a `CommandRecorder` filled with
`record_command` calls; `target(pos)` for the ship):
- `test_the_catalogue_builds_a_squiddler`: `isinstance(c.body, Squid)`, `c.radius == 15`, three hit points after
  spawn.
- `test_gun_level_one_strength_is_the_old_squid_gun`: `level_rules.get_enemy_strength(1)` gives
  `fire_interval_min == 60`, `fire_interval_max == 300`, `fire_range == 400`, and a built Squiddler on level 30 has
  `gun_range == 400` after one step.
- `test_a_squiddler_replays_the_recording`: a recorder holding `REPLAY_ENEMY_WINDOW_SIZE` `ROTATE_RIGHT` commands and a
  target far out of range: after 10 frames its angle has turned `10 * config.SHIP_ROTATION_SPEED` degrees; with
  `APPLY_THRUST` commands instead its speed rises and `'thrust'` reached the body (the jet is above 0).
- `test_on_no_action_it_turns_to_face_its_target`.
- `test_it_fires_where_it_faces_when_lined_up`: target 200 px dead ahead → one enemy shot on the first frame
  (`startsLoaded`) heading along `c.angle`; target 200 px behind → none.
- `test_before_the_window_fills_a_squiddler_only_coasts`: an empty recorder, `vx = 1`: after 30 frames it has moved,
  its angle has not changed, and it has not crashed.
- `test_with_no_target_a_squiddler_turns_nowhere_and_holds_fire`: a full recorder of `NO_ACTION`, no ship or hunter:
  its angle is unchanged after 30 frames, and no shots.
- `test_a_squiddler_blinks_when_hit_rammed_or_bounced`: a shot that does not kill, a ram and a wall bounce each start
  a blink (`body.is_blinking`); the same creature built without `blinksWhenHit` does not blink.
- `test_a_dead_squiddler_copies_for_its_portrait`: `deepcopy` after `kill`; the copy's `update_death(5.0)` then
  `draw_death` lights pixels; the copy's tentacles are not the original's lists.

`tests/test_squid.py`: move `tests/test_replay_enemy_visuals.py`'s tests onto the Body, built from `'replay'`
(`squid.tentacles` → `squid.body.tentacles`, `apply_thrust()` → `squid.emit('thrust', None)`,
`trigger_blink()` → `squid.emit('blink', None)`). Leave `tests/test_replay_enemy_visuals.py` in place until Task 5.

- [ ] **Step 2: Run them to make sure they fail**

Expected: FAIL, because `entities.squid` cannot be imported.

- [ ] **Step 3: Implement the traits, the Body, the catalogue entry and the display squids**

Move the `replay` cases of the tests below onto Creatures: `tests/test_exit_policies_game.py:134`
(`creatures.build('replay', …, recorder=game.command_recorder)`), the `ReplayEnemyShip` case of
`tests/test_hunter_targeting.py` (through the Encounter, like `test_a_creature_aims_at_the_nearest_hunter`), and the
Squiddler tests in `tests/test_enemy_hit_points.py` (through `Encounter.shoot`). Note each deleted test, with why, for
Task 6's list.

- [ ] **Step 4: Run the full suite, and watch level 11 (four Squiddlers) on the real display**

Expected: all pass. Compare with the previous commit (a worktree) over 1800 frames: the Squiddlers fly the same kind of
paths, blink on walls and hits, and fire when lined up. Record the numbers you compared in the commit message.

- [ ] **Step 5: Commit**

### Task 3: The Squidlet as a Creature

**Files:**
- Modify: `config/enemies.json` (`baby`), `config.py` (`BabySettings` loses `speedMultiplier`;
  `BABY_SPEED_MULTIPLIER` goes), `entities/egg.py` (`pop` makes each Squidlet with
  `make_enemy('baby', pos, 1, command_recorder)`), `game_handlers/collision_handler.py`
  (`_spawn_split_boss_children` makes Squidlets with `make_enemy`; `shoot_into` passes `[]` for `babies`), `game.py`
  (stop calling `update_babies`), `tests/test_star_game.py`, `tests/test_enemy_hit_points.py`,
  `tests/test_hunter_targeting.py`, `tests/test_squid.py`
- Test: `tests/test_squidlet_creature.py`

**Interfaces:**
- Consumes: Task 2's traits and Body.
- Catalogue `baby`: `tuning` keeps `size`. Traits in order: `replaysPlayer`, `thrusters {"speedShare": 0.5}`,
  `ramsShip`, `gun {"strengthLevel": 1, "startsLoaded": true}`, `takesHits {"hitPoints": 1}`, `dropsPickup`. No
  `blinksWhenHit`.

- [ ] **Step 1: Write the failing tests**

- `test_the_catalogue_builds_a_squidlet`: a Squid body, radius 10, one hit point.
- `test_a_squidlet_flies_faster_than_a_squiddler`: both thrusting for 120 frames from rest on a full `APPLY_THRUST`
  recording; the Squidlet's speed is `0.5 * SHIP_MAX_SPEED` and the Squiddler's `0.3 * SHIP_MAX_SPEED`
  (`pytest.approx`).
- `test_a_hatching_egg_puts_squidlet_creatures_on_the_roster`: `Egg.pop` into an `EnemyRoster`; every new entry is a
  `Creature` of type `baby`.
- `test_a_squidlet_does_not_blink_when_rammed`.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

Move the `Baby(…)` constructions in `tests/test_star_game.py` and `tests/test_enemy_hit_points.py` onto
`creatures.build('baby', …)`, and the `Baby` case of `tests/test_hunter_targeting.py` onto the Encounter.

- [ ] **Step 4: Run the full suite, and watch level 13 (three eggs) on the real display until they hatch**

- [ ] **Step 5: Commit**

### Task 4: The Squiddler Boss and the Mother as Creatures

**Files:**
- Create: `creatures/traits/spawning.py`, `tests/test_traits_spawning.py`, `tests/test_boss_creatures.py`
- Modify: `creatures/encounter.py` (`spawn`), `creatures/registry.py`, `config/enemies.json` (`split_boss`,
  `mother_boss`), `game.py` (stop calling `update_split_bosses` and `update_mother_bosses`),
  `game_handlers/collision_handler.py` (`shoot_into` passes `[]` for both), `hunter/spawn.py` (sizes from
  `enemy_kinds.kind(k).tuning['size']`), `tests/test_spawn_in_open.py`, `tests/test_hunter_combat.py`,
  `tests/test_hunter_targeting.py`, `tests/test_squid.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - `Encounter.spawn(kind: str, pos, level: int)`: `make_enemy(kind, pos, level, world.command_recorder)`, added to the
    roster, and returned. A Creature spawned during a frame first acts on the next one (or when a shot reaches it).
  - `splitsOnDeath` → `SplitsOnDeath(into: str, count: int, spread: float, speed: float)`; `__init__` raises
    `ValueError` for a kind the catalogue does not have. `on_death`: `count` children of kind `into`, each at a random
    bearing and a distance between `spread / 2` and `spread`. A spot not `enc.maze.is_open(pos, child_radius)` is
    replaced by `enc.maze.open_spot_near(c.get_pos(), child_radius, spread)`, where `child_radius` is the child kind's
    `tuning['size']`. Each child moves at `speed`, 45° to the left of the creature's direction of travel for the first
    child and 45° to the right for the rest (today's rule).
  - `laysEggs` → `LaysEggs(interval: int)`. `on_spawn`: `c.egg_cooldown = 0`. `on_frame`: count the cooldown down by
    `dt`. When it is done, lay an egg at a random offset within half the creature's radius. If that spot has no room
    for the egg's `tuning['maxSize']`, use `enc.maze.open_spot_near(c.get_pos(), max_size, c.radius)`. Lay with
    `enc.spawn('egg', pos, c.level)` and reset the cooldown to `interval`.
- Catalogue `split_boss`: `tuning` becomes `{"size": 30}`. Traits in order: `replaysPlayer`,
  `thrusters {"speedShare": 0.3}`, `ramsShip`, `gun {"strengthLevel": 1, "startsLoaded": true}`,
  `takesHits {"hitPoints": 8}`, `splitsOnDeath {"into": "baby", "count": 6, "spread": 80, "speed": 2.0}`,
  `dropsPickup`.
- Catalogue `mother_boss`: `tuning` becomes `{"size": 45, "lineGlowIntensityMax": 0.7,
  "blinkFrequencyMultiplierMax": 2.0, "blinkDurationMultiplierMax": 1.5}`. Traits in order: `replaysPlayer`,
  `thrusters {"speedShare": 0.15}`, `ramsShip`, `gun {"strengthLevel": 1, "startsLoaded": true, "shotSpeed": 1.6,
  "impact": 1.4, "glowColor": [255, 160, 100], "glowRadius": 1.8, "glowIntensity": 0.65}`,
  `takesHits {"hitPoints": 20}`, `laysEggs {"interval": 180}`, the same `splitsOnDeath` as the boss, `dropsPickup`.
- `config.py`: `SplitBossSettings` and the `SPLIT_BOSS_*` constants go once nothing reads them (the size multiplier's
  readers move to `tuning['size']`). `MotherBossSettings` keeps only the three look fields, and its other
  `MOTHER_BOSS_*` constants go.

- [ ] **Step 1: Write the failing tests**

`tests/test_traits_spawning.py` (stand-in world with a maze whose `is_open` and `open_spot_near` you control):
- `test_splitting_puts_its_children_on_the_roster_moving_apart`: 6 Squidlets, all within 40–80 px, the first moving
  45° left of the parent's travel and the others 45° right, each at speed 2.0.
- `test_a_child_with_no_room_moves_to_an_open_spot`.
- `test_an_unknown_child_kind_is_rejected`: `SplitsOnDeath.from_params({"into": "nosuch", …})` raises `ValueError`.
- `test_a_mother_lays_on_her_first_frame_and_then_every_interval`: eggs laid on frames 1 and 181 of 200, each an
  `Egg` on the roster.
- `test_a_dead_mother_lays_no_more`.

`tests/test_boss_creatures.py`:
- `test_the_catalogue_builds_both_bosses` (radius 30 and 45; 8 and 20 hit points).
- `test_a_boss_killed_by_the_hunter_still_splits`: a real `CollisionHandler` in the world, a `source='hunter'` shot
  on a 1-hit-point boss: six Squidlets on the roster, `scoring.record_enemy_destroyed` not called, one pickup roll.
- `test_the_mothers_shots_glow_and_fly_faster`: her shot's speed is 1.6× a Squiddler's, with glow colour
  `(255, 160, 100)`.

Move `tests/test_spawn_in_open.py`'s boss-children and laid-egg tests onto the traits, and
`tests/test_hunter_combat.py::test_hunter_boss_kill_still_spawns_children` onto the Encounter (reading the child count
from the catalogue).

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite, and watch levels 18 and 48 on the real display**

Expected: all pass. Shoot a boss down in the capture script: it splits into six Squidlets. The Mother lays an egg
about every three seconds.

- [ ] **Step 5: Commit**

### Task 5: Delete the old squid code; the speed gate

**Files:**
- Delete: `entities/replay_enemy_ship.py`, `entities/baby.py`, `entities/split_boss.py`, `entities/mother_boss.py`,
  `tests/test_replay_enemy_visuals.py`
- Modify: `game_handlers/enemy_updater.py` (delete `update_replay_enemies`, `update_split_bosses`,
  `update_mother_bosses`, `update_babies`), `game_handlers/collision_handler.py` (delete the `replay_enemies`,
  `split_bosses`, `mother_bosses` and `babies` parameters and loops, `spawn_into`, and `_spawn_split_boss_children`),
  `game_handlers/spawn_manager.py` (the `replays_player` branch of `make_enemy`), `entities/rotating_thruster_ship.py`
  (delete `avoid_enemy_ships` and `is_enemy_ship`, and their overrides in `ship.py` and `hunter_ship.py`, if a grep
  shows nothing else calls them), `main.py` (warm-up imports), `ARCHITECTURE.md`, `GLOSSARY.md` (no new terms;
  check the squid entries still read true), and every test that still imports a deleted module
- Test: the remaining tests in `tests/test_enemy_death.py`, `tests/test_hunter_targeting.py`,
  `tests/test_anemone_game.py`, `tests/test_enemy_hit_points.py` that call `handle_projectile_enemy_collisions` with
  positional lists

**Interfaces:**
- `CollisionHandler.handle_projectile_enemy_collisions(projectile, flockers, flighthouses, eggs, powerup_crystals,
  anemones=None, jev_beacon_allowed=False, enemy_hunters=None, maze=None) -> bool`.

- [ ] **Step 1: Delete, then run `grep -rn "replay_enemy_ship\|entities.baby\|split_boss import\|mother_boss import\|update_replay_enemies\|update_babies\|update_split_bosses\|update_mother_bosses\|_spawn_split_boss_children" --include=*.py .`**

Expected: no hits outside `docs/`.

- [ ] **Step 2: Move or delete the remaining tests**

A test of behaviour a player would notice is rewritten through the Encounter or a trait. A test of a deleted seam is
deleted. Keep the list (file::test, one line why).

- [ ] **Step 3: Run the full suite**

Expected: all pass, including `tests/test_duel_enemies.py`, `tests/test_splash_scene.py` and
`tests/test_menu_visuals.py`.

- [ ] **Step 4: Speed gate**

Run three times each, take the medians:
`venv/bin/python -m tools.frame_timer --levels 1 8 9 40 18 42 48 --frames 600 --seed 1`.
Expected: levels 1, 8, 9, 40 within 20% of the stage 1 baseline; 18, 42, 48 within 20% of Task 1's. Record the
table in the validation file. Over 20%: stop and report to the user.

- [ ] **Step 5: Update `ARCHITECTURE.md`**

The Creatures section lists the four squid kinds, the `squid` Body, the new traits and `Encounter.spawn`. Remove the
squid classes from the entity list and the "otherwise" branch's mention of them.

- [ ] **Step 6: Commit**

### Task 6: Hand back to the user

- [ ] **Step 1: Report**

- The speed numbers: the squid baseline and the gate.
- What changed in play (the comparisons from Tasks 2–4).
- Every test deleted, with its reason.
- Every experiment test reworked, with the old and new numbers.
- Anything in the spec's later stages this work showed to be wrong.

Ask whether to write the plan for stage 4 (Egg, Anemone, Flocker, Flighthouse).
