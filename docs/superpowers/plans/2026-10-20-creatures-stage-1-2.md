# Creatures and Traits, Stages 1–2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that a Creature built from a Body and Traits, run by an Encounter, is fast enough (stage 1), then move
the Urchin, Crab and Jelly onto it and delete `Enemy` and `enemy_strategies.py` (stage 2).

**Architecture:** A new `creatures/` package holds `Creature`, `Controls`, the `Trait` base, the trait and body
registries, `build()`, and the `Encounter`. Kinds whose catalogue entry names a `body` are built as Creatures; every
other kind keeps its class and its old update and hit code until its own stage. The Encounter runs creatures only, and
hands a shot no creature took to the old collision code.

**Tech Stack:** Python 3.10, pygame 2.6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md`. Read it first: it is the model, the
decisions and the later stages.

## Global Constraints

- Branch `refactor/enemy-catalogue`, starting from commit `420b0e2`. At that commit the full suite is 2130 passed, 0
  failed.
- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`. After
  every task the whole suite passes.
- Never stage `.codegraph/` or `assets/neural/hunter.npz`. Stage files by name.
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Units: velocities are px per frame at 60 FPS; `dt` counts frames.
- Numeric drift in movement is allowed; behaviour must stay the same (Urchins sit and are shoved, Crabs patrol and
  shoot, Jellies chase and do not overlap). Bit-identical play is not required.
- **Speed gate:** a frame (update plus draw) on levels 1, 8, 9 and 40 may be at most 20% slower than the baseline from
  Task 1. Over that at Task 2 or Task 6: stop, report the numbers to the user, and do not go on.
- Rendering changes are checked on the real display (fullscreen, 1352×878), not only the dummy driver: the dummy
  driver hides alpha bugs.
- Use the glossary's words (GLOSSARY.md): Creature, Body, Trait, Brain, Propulsion, Encounter, Roster, Enemy Kind.
  Kind keys (`static`, `patrol`, `aggressive`) never change.

## Review Focus

1. **One shot, two overlapping creatures**: only the first in roster order is hit, and the shot is spent. Pinned in
   Task 2 (`test_a_shot_hits_only_the_first_creature_it_reaches`).
2. **A creature killed during the frame** stops acting that frame, and drops at most one pickup. Pinned in Task 2
   (`test_a_creature_killed_this_frame_does_not_act_again`).
3. **The duel**, which has no player ship to target: Crabs and Jellies go after the nearest hunter, and a creature with
   no target holds still without crashing. Pinned in Task 5 (`test_with_no_target_a_crab_and_a_jelly_hold_still`) and
   Task 6 (`tests/test_duel_enemies.py` still passes).
4. **The death portrait**: `deepcopy` of a killed Creature (the level-complete screen draws one) copies the creature
   without its Encounter. Pinned in Task 3 (`test_a_dead_urchin_copies_for_its_portrait`).
5. **The level editor preview** draws a Creature that has never been stepped. Pinned in Task 3
   (`test_a_fresh_urchin_draws`) and by `tests/test_level_editor.py::test_every_screen_and_palette_item_draws`.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/frame_timer.py` | Time update and draw per frame on chosen levels with fixed seeds. |
| `docs/superpowers/validation/2026-10-20-frame-times.md` | The baseline and each gate's numbers. |
| `creatures/__init__.py` | `build(kind, pos, level, recorder) -> Creature`. |
| `creatures/creature.py` | `Creature` and `Controls`. |
| `creatures/trait.py` | `Trait` base class: the hooks, `REQUIRES`, `from_params`. |
| `creatures/registry.py` | `TRAITS` and `BODIES` by catalogue name; `validate(catalogue)`. |
| `creatures/encounter.py` | `Encounter`: `step`, `shoot`, `target_for`, `kill`, `drop_pickup`. |
| `creatures/traits/combat.py` | `TakesHits`, `ShovedByShots`, `RamsShip`, `DropsPickup`, `BouncesOffWalls`, `Gun`. |
| `creatures/traits/brains.py` | `Still`, `Patrol`, `Chase`. |
| `creatures/traits/propulsion.py` | `Coasts`, `Drift`. |
| `creatures/traits/crowd.py` | `KeepsApart`. |
| `entities/urchin.py`, `patrol_crab.py`, `jellyfish.py` | The three Bodies (read `creature`, not `enemy.strategy`). |
| `enemy_kinds.py`, `config/enemies.json` | `allegiance`, `body`, `traits` fields. |
| `game.py`, `hunter/duel_enemies.py`, `game_handlers/spawn_manager.py` | Hold and step an Encounter; build Creatures. |

---

### Task 1: Frame timer and baseline

**Files:**
- Create: `tools/frame_timer.py`
- Create: `docs/superpowers/validation/2026-10-20-frame-times.md`

**Interfaces:**
- Produces: `venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1`, printing one row per level:
  `level  enemies  update_ms_mean  update_ms_p95  draw_ms_mean`.

- [ ] **Step 1: Write `tools/frame_timer.py`**

Build a real `Game` on a 1352×878 surface with the dummy video and audio drivers and `config.SETTINGS.game.hunterPilot
= 'rules'`. For each level: `random.seed(seed)`, `numpy.random.seed(seed)`, `game.level = level`, `game.start_level()`,
`game.player_has_moved = True`, run 60 warm-up frames, then time `game.update(1.0)` and `game.draw_game()` separately
with `time.perf_counter()` over `--frames` frames. Close the enemy hunters at the end (`game._close_enemy_hunters()`).

- [ ] **Step 2: Run it three times at `420b0e2` and record the median of each number**

Run: `venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1`
Expected: four rows. Write them into `docs/superpowers/validation/2026-10-20-frame-times.md` under "Baseline
(420b0e2)", with the machine and the date.

- [ ] **Step 3: Commit**

```bash
git add tools/frame_timer.py docs/superpowers/validation/2026-10-20-frame-times.md
git commit -m "tools: time a frame on chosen levels, and the baseline before Creatures"
```

### Task 2: Creature, Trait, Encounter skeleton and the dispatch gate

**Files:**
- Create: `creatures/__init__.py`, `creatures/creature.py`, `creatures/trait.py`, `creatures/registry.py`,
  `creatures/encounter.py`
- Modify: `enemy_kinds.py` (`EnemyKind.allegiance: str = 'enemy'`, `body: Optional[str] = None`,
  `traits: Tuple[Tuple[str, Mapping], ...] = ()`; the three keys are optional in the file during migration, and
  `allegiance` must be `friend` or `enemy`)
- Modify: `game_handlers/collision_handler.py` (rename `_record_projectile_kill` to `record_kill` and `_drop_pickup` to
  `drop_pickup`)
- Modify: `game.py` (rename `_jev_beacon_drop_allowed` to `jev_beacon_allowed`; hold `self.encounter`)
- Test: `tests/test_creatures.py`, `tests/test_encounter.py`

**Interfaces:**
- Produces:
  - `Controls` (dataclass): `turn: float = 0.0` (−1 to 1), `thrust: bool = False`, `fire: bool = False`,
    `heading: Optional[float] = None` (degrees), `aim: Optional[Tuple[float, float]] = None`.
  - `Creature(kind: EnemyKind, pos, body, traits: Sequence[Trait], level: int = 1, recorder=None)`, a `GameEntity`
    with `type`, `x`, `y`, `vx`, `vy`, `radius` (from `kind.tuning['size']`), `angle`, `speed`, `hit_points`,
    `max_hit_points`, `allegiance`, `level`, `recorder`, `body`, `traits`, `controls`, `has_spawned: bool`.
    Methods: `emit(name: str, encounter)` (calls `body.on_event(self, name)` and every trait's `on_event`),
    `draw(screen)` (skips when off screen by more than 100 px, as `Enemy.draw` does), `update(dt)` (required by `GameEntity`;
    it does nothing, because the Encounter drives creatures), `DEATH_DURATION` (the body's), `update_death(dt)` (friction from `body.DEATH_FRICTION`, then the body),
    `draw_death(screen)`, `check_circle_collision(other_pos, other_radius, other_entity=None)` (as `Enemy`'s), and
    `__deepcopy__` that copies everything but leaves out any reference to an Encounter.
  - `Trait`: hooks `on_spawn(c, enc)`, `on_frame(c, enc, dt)`, `on_shot(c, shot, enc)`, `on_death(c, enc)`,
    `on_event(c, name, enc)`, and `on_crowd(creatures, enc, dt)`, all no-ops; class attributes `NAME: str` and
    `REQUIRES: Tuple[str, ...] = ()`, plus `CROWD: bool = False`; `from_params(params: Mapping) -> Trait` (classmethod;
    an unknown parameter raises `ValueError`).
  - `registry.TRAITS: Dict[str, Type[Trait]]`, `registry.BODIES: Dict[str, type]`, and
    `registry.validate(catalogue: Mapping[str, EnemyKind]) -> None`. `validate` raises `ValueError` naming the kind for:
    an unknown body or trait, bad parameters, or a missing `REQUIRES`.
  - `creatures.build(kind_key, pos, level, recorder) -> Creature`, with the traits in catalogue order.
  - `Encounter(roster, world)`. `world` is read live on every call; `Game` satisfies it as-is, and `DuelEnemies`
    supplies an adapter. Its attributes are `ship`, `hunter`, `maze`, `scoring`, `sound_manager`, `command_recorder`,
    `collision_handler`, `projectiles`, `powerup_crystals` and `jev_beacon_allowed()`.
  - `Encounter` methods:
    - `step(dt)`: `on_spawn` for any creature not yet spawned, then `on_frame` for each live creature in roster
      order, then `on_crowd` once per kind for each crowd trait.
    - `shoot(projectile) -> bool`: friendly shots only. Offers the shot to live creatures in roster order (circle
      overlap); the first one hit gets `on_shot` from each of its traits, the shot is spent, and it returns True.
      Otherwise it returns `world.collision_handler.shoot_into(projectile, roster, world.powerup_crystals,
      jev_beacon_allowed=world.jev_beacon_allowed(), maze=world.maze)`.
    - `target_for(c) -> Optional[Tuple[float, float]]`: `combat_targets.nearest_friendly_pos(c, world.ship,
      world.hunter)`.
    - `kill(c, shot=None)`: `c.die()`, then `sound_manager.play_enemy_destroy()`, then
      `collision_handler.record_kill(shot, c)` when there is a shot, then each trait's `on_death`.
    - `drop_pickup(pos)`: `collision_handler.drop_pickup(pos, world.powerup_crystals, world.jev_beacon_allowed())`.
    - `add_shot(projectile)`: appends to `world.projectiles`.
  - After a creature's `on_frame` hooks, `step` animates its Body: `c.body.update(c, dt, encounter.target_for(c))`.
    (The existing Bodies take the target as `player_pos`.)
  - Until Task 6 deletes them, the old code skips any enemy that is a `Creature`. That covers every
    `EnemyUpdater.update_X` loop (including `_keep_apart`), `CollisionHandler.handle_projectile_enemy_collisions`
    and `shoot_into`.
  - `Game.update` calls `self.encounter.step(dt)` before the old `update_X` calls. The projectile loop calls
    `self.encounter.shoot(projectile)` instead of `collision_handler.shoot_into`. `Game.__init__` builds
    `self.encounter = Encounter(self.roster, self)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_encounter.py`, use a stub world (a `SimpleNamespace` with a Mock `collision_handler` and
`sound_manager`) and test-only traits registered for the test:
- `test_traits_run_in_catalogue_order_every_frame`: two traits that append their name to a list; after
  `step(1.0)`, the list is `['first', 'second']`.
- `test_on_spawn_runs_once_before_the_first_frame`.
- `test_a_shot_hits_only_the_first_creature_it_reaches`: two creatures on one spot. After
  `shoot(friendly_projectile)` returns True, only the first creature's `on_shot` ran, and
  `collision_handler.shoot_into` was not called.
- `test_a_shot_that_misses_every_creature_goes_to_the_old_code`: `shoot_into` was called once.
- `test_enemy_shots_are_not_offered_to_creatures`.
- `test_a_creature_killed_this_frame_does_not_act_again`: a trait kills it in `on_frame`; the next trait's
  `on_frame` does not run, and `on_death` ran once.
- `test_crowd_traits_run_once_per_kind_with_the_live_creatures_of_that_kind`.

In `tests/test_creatures.py`:
- `test_the_catalogue_rejects_an_unknown_trait_a_bad_parameter_and_a_missing_requirement`: three cases, each raising
  `ValueError` that names the kind.
- `test_build_gives_the_kinds_size_and_traits_in_order`.

- [ ] **Step 2: Run them to make sure they fail**

Run: `… pytest tests/test_encounter.py tests/test_creatures.py`
Expected: FAIL, because `creatures` cannot be imported.

- [ ] **Step 3: Implement the interfaces above**

`registry.validate(enemy_kinds._CATALOGUE)` runs when `creatures` is imported. `enemy_kinds` itself must not import
`creatures` (it has no pygame dependency). The step loop reads `creature.active` before each hook, so a creature
killed partway through a frame stops at once.

- [ ] **Step 4: Run the new tests and the full suite**

Expected: all pass. No kind has a `body` yet, so the game plays as before.

- [ ] **Step 5: The dispatch gate**

Add `--creatures N` to `tools/frame_timer.py`. It puts N test Creatures, each with six traits whose hooks do one
attribute write, into level 9's roster, and times the frame. Run it with N = 33 and N = 0 on level 9, and record the
difference per frame in the validation file. **Gate:** if 33 creatures add more than 20% of level 8's baseline update
time, stop and report to the user with the numbers. Otherwise go on.

- [ ] **Step 6: Commit**

```bash
git add creatures tests/test_encounter.py tests/test_creatures.py enemy_kinds.py game.py \
  game_handlers/collision_handler.py tools/frame_timer.py docs/superpowers/validation/2026-10-20-frame-times.md
git commit -m "feat: Creature, Trait and Encounter, run alongside the old enemy code"
```

### Task 3: The Urchin as a Creature

**Files:**
- Create: `creatures/traits/combat.py`, `creatures/traits/brains.py`, `creatures/traits/propulsion.py`
- Modify: `entities/urchin.py` (it is the `urchin` Body; it reads `creature` attributes only)
- Modify: `config/enemies.json` (`static`: `allegiance`, `body: "urchin"`, `traits`), `game_handlers/spawn_manager.py`
  (`make_enemy` calls `creatures.build` when the kind has a `body`)
- Test: `tests/test_traits_combat.py`, `tests/test_urchin_creature.py`

**Interfaces:**
- Consumes: Task 2's `Trait`, `Creature`, `Encounter`, `registry`.
- Produces these traits (catalogue name → class):
  - `still` → `Still`: sets no controls.
  - `coasts` → `Coasts`: moves by its velocity, applies `config.FRICTION_COEFFICIENT`, and zeroes each component
    under `config.MIN_VELOCITY_THRESHOLD`.
  - `bouncesOffWalls` → `BouncesOffWalls`: only while moving. It is the bounce from `Enemy.check_wall_collision`
    (restitution `config.COLLISION_RESTITUTION`, pushed out by radius + 1), and it emits `hit_wall`.
  - `ramsShip` → `RamsShip`: when the ship's shield is down and `ship.check_circle_collision(pos, radius, creature)`
    is true, calls `scoring.record_enemy_collision()` and emits `rammed`.
  - `takesHits` → `TakesHits(hitPoints: int)`: `on_spawn` sets `hit_points = max_hit_points`. `on_shot` subtracts 1,
    emits `hit`, and calls `encounter.kill(c, shot)` at 0.
  - `shovedByShots` → `ShovedByShots(transfer: float = config.MOMENTUM_TRANSFER_FACTOR)`: `on_shot` adds
    `shot.v * transfer` to the creature's velocity, before `takesHits` runs.
  - `dropsPickup` → `DropsPickup`: `on_death` calls `encounter.drop_pickup(c.get_pos())`.
- Catalogue order for `static`: `still`, `coasts`, `bouncesOffWalls`, `ramsShip`, `shovedByShots`,
  `takesHits {"hitPoints": 3}`, `dropsPickup`. Its `tuning` keeps `size` only. `config.STATIC_ENEMY_HIT_POINTS` goes
  once nothing reads it; `tests/test_hunter_fire_control.py:205` reads it, so make that test read
  `enemy_kinds.kind('static').traits`.

- [ ] **Step 1: Write the failing tests**

- `tests/test_traits_combat.py`:
  - `test_takes_hits_kills_on_the_last_hit_and_not_before`
  - `test_a_shove_moves_a_still_creature_and_friction_stops_it`
  - `test_bounces_only_while_moving`
  - `test_ramming_costs_the_player_only_without_a_shield`
  - `test_a_kill_drops_one_pickup_roll`
- `tests/test_urchin_creature.py`:
  - `test_an_urchin_in_a_real_level_takes_three_shots`: level 1 through `Game`.
  - `test_a_fresh_urchin_draws`: build it, then `draw` onto a surface without stepping; some pixels are lit.
  - `test_a_dead_urchin_copies_for_its_portrait`: `copy.deepcopy` after `kill`; the copy draws its death, and the copy
    has no Encounter reference.

- [ ] **Step 2: Run them to make sure they fail**

Expected: FAIL, because the traits do not exist.

- [ ] **Step 3: Implement the traits, the `urchin` Body and the catalogue entry**

Move the urchin's tests that construct `Enemy(pos, 'static')` onto `creatures.build('static', …)`. Delete the ones that
only test `Enemy`'s plumbing, and note each deletion for the hand-off list (Task 7).

- [ ] **Step 4: Run the full suite, and watch level 1 on the real display for a minute**

Expected: all pass. Urchins look and roll as before when shot.

- [ ] **Step 5: Commit**

### Task 4: The Crab as a Creature

**Files:**
- Modify: `creatures/traits/brains.py` (`Patrol`), `creatures/traits/propulsion.py` (`Drift`),
  `creatures/traits/combat.py` (`Gun`), `entities/patrol_crab.py` (the `crab` Body), `config/enemies.json` (`patrol`)
- Test: `tests/test_traits_brains.py`, `tests/test_crab_creature.py`

**Interfaces:**
- Produces:
  - `patrol` → `Patrol`: walks straight for a random 50–150 px, then turns around. It also turns at once when the next
    step would touch a wall (an active wall, as `PatrolEnemyStrategy` checks). It sets `controls.heading`, and sets
    `controls.fire` and `controls.aim` when the target is within `fire_range`.
  - `drift` → `Drift(speed: str | float)`: a string is a field of `level_rules.get_enemy_strength(c.level)`
    (`"patrol_speed"`, `"aggressive_speed"`), read in `on_spawn` into `c.speed`. It steers velocity toward
    `controls.heading` with the collision-preserving blend of `EnemyStrategy._apply_velocity_based_movement`; a
    simpler blend is acceptable if Crabs and Jellies still bounce off walls and each other visibly. Then it applies
    `config.FRICTION_COEFFICIENT`.
  - `gun` → `Gun(intervalMin: int | None = None, intervalMax: int | None = None, range: float | None = None)`: an
    omitted value comes from the creature's level strength (`fire_interval_min`, `fire_interval_max`, `fire_range`).
    It counts down a cooldown, which `on_spawn` sets to a random interval. When `controls.fire` and the cooldown is
    done, it calls `encounter.add_shot(Projectile(pos, angle_to(aim), is_enemy=c.allegiance == 'enemy'))`, emits
    `fired` and resets. It keeps `c.gun_charge` (0 to 1: how far through the cooldown) for Bodies to read.
- The `crab` Body reads `c.gun_charge` where it read `enemy.strategy.fire_cooldown`/`next_fire_interval`, and raises
  its claw on the `fired` event where `Enemy.get_fired_projectile` called `crab.on_fire()`.
- Catalogue order for `patrol`: `patrol`, `drift {"speed": "patrol_speed"}`, `gun`, `bouncesOffWalls`, `ramsShip`,
  `takesHits {"hitPoints": 1}`, `dropsPickup`.

- [ ] **Step 1: Write the failing tests**

- `test_a_patrolling_creature_turns_around_at_its_distance_and_at_a_wall`
- `test_the_gun_fires_only_when_ready_and_the_target_is_in_range`: one shot, then none until the cooldown passes.
- `test_gun_charge_rises_from_zero_to_one_across_the_cooldown`
- `test_one_hit_kills_a_crab`
- `test_with_no_target_a_crab_and_a_jelly_hold_still` (the jelly half is added in Task 5)

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement, and move the crab tests that construct `Enemy(…, 'patrol')`**

- [ ] **Step 4: Run the full suite, and watch level 2 on the real display**

Expected: all pass. Crabs scuttle back and forth, raise the claw and fire.

- [ ] **Step 5: Commit**

### Task 5: The Jelly as a Creature

**Files:**
- Modify: `creatures/traits/brains.py` (`Chase`), `creatures/traits/crowd.py` (`KeepsApart`), `entities/jellyfish.py`
  (the `jelly` Body), `config/enemies.json` (`aggressive`)
- Test: `tests/test_traits_brains.py`, `tests/test_jelly_creature.py`, and `tests/test_jelly_crowding.py` (move it onto
  the Encounter)

**Interfaces:**
- Produces:
  - `chase` → `Chase`: heads for the target and sets `c.is_alert`. When it has moved less than
    `config.ENEMY_STUCK_DETECTION_THRESHOLD` in a frame, it escapes for a random `ENEMY_SHIFT_DURATION_MIN`–`MAX`
    frames, heading away from the target ±45°, and sets `c.backing_off` while it does. With no target it clears both.
  - `keepsApart` → `KeepsApart` (`CROWD = True`): `on_crowd` is `enemy_updater._keep_apart`, moved here. That is up to
    20 passes, each overlap pushed half each way.
- The `jelly` Body reads `c.backing_off` where it read `enemy.strategy.mode == MODE_ESCAPE_OBSTACLE`.
- Catalogue order for `aggressive`: `chase`, `drift {"speed": "aggressive_speed"}`, `bouncesOffWalls`, `ramsShip`,
  `takesHits {"hitPoints": 1}`, `dropsPickup`, `keepsApart`.

- [ ] **Step 1: Write the failing tests**

- `test_a_chasing_creature_closes_on_its_target`
- `test_a_stuck_chaser_backs_off_then_chases_again`
- `test_jellies_on_one_spot_end_up_only_touching` (from `test_jelly_crowding`, through `Encounter.step`)
- the jelly half of `test_with_no_target_a_crab_and_a_jelly_hold_still`

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite, and watch level 9 (20 Jellies) on the real display**

- [ ] **Step 5: Commit**

### Task 6: Delete the old Urchin/Crab/Jelly code; the duel; the second speed gate

**Files:**
- Delete: `entities/enemy.py`, `entities/enemy_strategies.py`
- Modify: `game_handlers/enemy_updater.py` (delete `update_enemies`, `_keep_apart` and
  `handle_enemy_to_enemy_avoidance`), `game_handlers/collision_handler.py` (delete the `enemies` parameter and its
  loop), `game.py` (delete the `update_enemies` call), `hunter/duel_enemies.py` (hold an `Encounter` with a duel
  world adapter whose `ship` is `_Target(first)` and whose `hunter` is the second hunter; `shot_hits` calls
  `encounter.shoot`), `rendering/level_editor.py` (drop the special `draw(screen, None)` for the three kinds),
  `main.py` (warm-up imports), `ARCHITECTURE.md`, `GLOSSARY.md`
- Test: every test that still imports `entities.enemy` or `entities.enemy_strategies`

**Interfaces:**
- Consumes: Tasks 2–5.

- [ ] **Step 1: Delete the code, then run `grep -rn "entities.enemy\b\|enemy_strategies\|update_enemies" --include=*.py .`**

Expected: no hits outside `docs/`.

- [ ] **Step 2: Move or delete the remaining tests**

Rule: a test that checks behaviour a player would notice is rewritten through `Encounter` or a single trait. A test
that only exercises a deleted seam is deleted. Keep a list (file::test, one line why) for Task 7.

- [ ] **Step 3: Run the full suite**

Expected: all pass, including `tests/test_duel_enemies.py`.

- [ ] **Step 4: Second speed gate**

Run: `venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1`, three times, and take the
medians.
Expected: each level's update + draw within 20% of the baseline. Record the numbers in the validation file. Over 20%:
stop and report to the user.

- [ ] **Step 5: Update the docs**

- `ARCHITECTURE.md`: replace the `Enemy`/`enemy_strategies.py` entries and the Strategy Pattern section with
  `creatures/`. Rewrite "Adding New Enemy Types" (a kind with a `body` needs only a catalogue entry when its traits
  exist).
- `GLOSSARY.md`: add Creature, Body, Trait, Brain, Propulsion and Encounter, each with a one-line definition and an
  _Avoid_ line in the file's style.

- [ ] **Step 6: Commit**

### Task 7: Hand back to the user

- [ ] **Step 1: Report**

- The speed numbers: baseline, the dispatch gate, the second gate.
- What changed in play.
- Every test deleted, with its reason.
- Anything in the spec's later stages this work showed to be wrong.

Ask whether to write the plan for stage 3 (the squids).
