# Creatures and Traits, Stage 5 (the enemy hunters) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The four enemy hunters (Terminator `rules_hunter`; Viber `neural_hunter`, Boss Viber `boss_viber`, Vibelet
`vibelet`) become Creatures. `EnemyHunter`, `RulesHunter`, `NeuralHunter`, `BossViber`, `Vibelet` and `VIBERS` are
deleted, and so are the game's special paths for them: `_fly_enemy_hunters`, `CollisionHandler.shoot_into` and
`shoot_enemy_hunters`. After this stage every enemy is a Creature and only the allied hunter is not.

**Architecture:** A new trait, `pilot {"mode": "rules" | "neural"}`, gives a creature a **craft**: a private
`HunterShip` flown by a `HunterFlight`, exactly as today. Each frame the trait does three things:
- it hands the craft anything that pushed the creature since the last frame;
- it flies the craft one frame and places its shots;
- it copies the craft's position, velocity and heading back onto the creature.

So the flight model the neural policy was trained on, and that the allied hunter still uses, stays as it is. A new
Body, `hunterShip`, draws the arrowhead through a puppet `HunterShip` in the kind's colours. Contact with the player
is the `ramsShip` trait and hits are `takesHits`. A new trait hook, `on_close`, lets a pilot stop its thread when
the level ends.

**Tech Stack:** Python 3.10, pygame 2.6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md` (stage 5). Stages 1–4 are done; read
`creatures/` first. Also read `hunter/flight.py` (`HunterFlight`, `WorkerPilot`, `NeuralPilot`),
`hunter/surroundings.py` (`ProtagonistSurroundings`), and `entities/enemy_hunter.py`, the class this stage replaces.

**Deviation from the spec, to confirm with the user:** the spec has the pilot drive separate `thrusters` and `gun`
traits ("Thrusters, Gun, Energy and a pilot trait that wraps `HunterFlight`"). This plan keeps the hunter's own flight
model inside the pilot trait instead, for three reasons:
- `HunterShip.step` holds burst firing, nose tracking and burn budgets, and the neural policy was trained on exactly
  those. Rebuilding them as `thrusters` and `gun` would change how the Vibers fly.
- The allied hunter flies the same `HunterShip` until stage 6.
- Another session is editing `HunterShip.step` and `HunterFlight.fly` right now.

`pilot` still goes on any creature: a neural Jelly is the `jelly` Body with `pilot {"mode": "neural"}`. No `energy`
trait is needed, because enemy hunters are indestructible to walls and their hits are `takesHits`. Breaking the craft
into traits fits stage 6, when the allied hunter and `HunterFlight` move.

## Global Constraints

- Branch `refactor/enemy-catalogue`, starting from the commit that adds this plan. At `743d4d3` the full suite is 2266
  passed, 0 failed.
- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`. After
  every task the whole suite passes.
- **Another session's uncommitted work** sits in the tree and must never be staged, edited or reverted:
  - `entities/hunter_ship.py`, `hunter/fire_control.py`, `hunter/flight.py`, `hunter/maze_route.py`,
    `hunter/senses.py`;
  - `experiments/rollout.py`, `tools/ppo_neural.py`, `assets/neural/hunter.npz`;
  - `tests/test_compass_reward.py`, `tests/test_hunter_flight.py`.

  This plan does not need to change any of them. Never stage `.codegraph/` either. Stage files by name.
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Behaviour must stay the same; numeric drift is allowed. A Terminator or Viber hunts only its protagonist (the player,
  or the lab's hunter), fires `'enemy'` shots in its colour at its shot strength, and takes its catalogue hits. Shots
  from the player and the allied hunter kill it, with the kill credited and no pickup. Touching it costs the player an
  enemy collision. A Viber kind with no neural model is left off the level with a warning.
- **Comparisons and speed runs use clean worktrees**, the previous commit against it plus only this task's changes. The
  other session's edits change how a neural pilot fires, and would show up as a difference.
- Rules-hunter comparisons use the lab's synchronous worker (`experiments.harness.SyncWorker`, through
  `game._rules_worker_factory`), so that both sides are deterministic.
- Kind keys never change. Use the glossary's words; one new term, **Craft** (Task 4).
- **Speed gate (Task 4):** levels 1, 8, 21, 24, 25 and 40, measured as stage 4 did: CPU time, two clean worktrees
  alternating, five rounds, medians, at most 20% slower. Over 20%: stop and report.
- Drawing is checked on the real display (cocoa, `pygame.HIDDEN`, 1352×878, `pixels3d`) against the previous commit,
  for each kind, flying and dying.

## Review Focus

1. **A level that ends or restarts stops every Terminator's pilot thread.** `start_level` twice, and the game
   quitting, leave no `jev-pilot` thread running from an enemy hunter. Pinned in Task 2
   (`test_restarting_the_level_stops_every_terminator_thread`).
2. **A kill portrait copies no pilot.** The `deepcopy` that `record_kill` takes has no flight, worker or view of the
   game, and plays the expanding ring. Pinned in Task 1 (`test_a_copy_leaves_the_pilot_behind`).
3. **A push reaches the craft.** A blast, a gate or the player ramming it moves an enemy hunter, and its pilot feels
   the hit through `register_hit`. Pinned in Task 1 (`test_a_push_moves_the_craft_and_the_pilot_feels_it`).
4. **No neural model means no Vibers, not a broken level.** The Viber kinds are skipped with a warning, the rest of
   the level spawns, and the exit policy can still be met. Pinned in Task 3
   (`test_without_a_model_no_viber_is_placed_and_the_level_still_plays`).
5. **Only friendly shots hurt it.** An enemy hunter's own shots, and other enemies' shots, never hit an enemy
   hunter. Pinned in Task 2 (`test_its_own_shots_never_hit_it`).

---

## File structure

| File | Role |
|---|---|
| `creatures/traits/piloted.py` (new) | `Pilot`: the craft, its flight, the push hand-over, shots, and closing. |
| `entities/hunter_ship_body.py` (new) | `HunterShipBody`: the arrowhead, engine and plume through a puppet `HunterShip`, the hit-point bar, the ring death. |
| `creatures/trait.py`, `creatures/creature.py`, `creatures/encounter.py` | `Trait.on_close` and `Trait.LIVE`; `Creature.__deepcopy__` leaves out live state; `Encounter.close()`. |
| `config/enemies.json`, `enemy_kinds.py` | The four kinds as Creatures; `hunters()` is the kinds with a `pilot` trait; `HunterStats` and the top-level `pilot` keys go. |
| `game.py` | `rules_worker()` and `enemy_policy()` for the pilot; enemy hunters made by `make_enemy`; `_fly_enemy_hunters` goes; `_close_enemy_hunters` becomes `encounter.close()`. |
| `game_handlers/collision_handler.py` | `shoot_into` and `shoot_enemy_hunters` go (Task 4). |
| `rendering/level_editor.py` | Previews are `creatures.build(kind, …)`. |
| `entities/enemy_hunter.py`, `rules_hunter.py`, `neural_hunter.py` | Deleted. |

---

### Task 1: The `pilot` trait and the `hunterShip` Body

**Files:**
- Create: `creatures/traits/piloted.py`, `entities/hunter_ship_body.py`, `tests/test_pilot_trait.py`
- Modify: `creatures/trait.py`, `creatures/creature.py`, `creatures/encounter.py`, `creatures/registry.py`,
  `tests/creature_parts.py`

**Interfaces:**
- Produces:
  - `Trait.on_close(c, enc)` is a no-op by default. It runs when the encounter ends, for each creature, alive or dead.
    `Trait.LIVE: Tuple[str, ...] = ()` names the creature attributes the trait keeps that must not be copied.
  - `Encounter.close()` calls every creature's traits' `on_close`. It can be called more than once.
  - `Creature.__deepcopy__` leaves out any Encounter (as now) and sets the attributes its traits name in `LIVE` to
    None on the copy.
  - `pilot` → `creatures.traits.piloted.Pilot(mode: str, shotStrength: float = 1.0)`. `mode` must be `'rules'` or
    `'neural'` (anything else raises `ValueError`). `LIVE = ('flight', 'pilot_worker')`.
    - `on_spawn(c, enc)` builds the craft, `c.craft`:
      - `HunterShip(c.get_pos(), replace(hunter_settings_for(mode), indestructible=True))`;
      - with the creature's `radius` and `angle`;
      - with these instance attributes for its shots: `SHOT_SOURCE` (`'enemy'` for an enemy creature, else
        `'hunter'`), `SHOT_STRENGTH = shotStrength`, and `COLOR` from the kind's `tuning['color']`.

      Then the pilot. Rules: `worker = enc.world.rules_worker()` and `WorkerPilot(worker, time.monotonic)`. Neural:
      `policy = enc.world.enemy_policy()` and `NeuralPilot(policy, config.SETTINGS.game.neuralDecisionFrames)`. A
      neural pilot with no policy gets no flight: `c.flight = None`, and the creature never flies.

      Finally `c.flight = HunterFlight(craft, pilot, ProtagonistSurroundings(enc.world))`, `c.pilot_worker = worker`
      (None for neural), and `c.pilot_thrusting = False`.
    - `on_frame(c, enc, dt)`, when `c.flight` is not None:
      1. **Push hand-over:** if the creature's velocity differs from the craft's, `craft.register_hit(c.vx - craft.vx,
         c.vy - craft.vy)`. Then copy the creature's `x, y, vx, vy` onto the craft.
      2. `shots = c.flight.fly(dt)`; each shot goes to `enc.add_shot`.
      3. Copy the craft's `x, y, vx, vy, angle` and `pilot_thrusting` onto the creature.
    - `on_death` and `on_close` close the flight and the worker (`close()` where it has one), once.
  - Body `hunterShip` → `entities.hunter_ship_body.HunterShipBody(creature)`:
    - `DEATH_DURATION = 48.0`, `DEATH_FRICTION = 0.0`.
    - It keeps a puppet `HunterShip` whose `COLOR`, `FILL`, `NOSE_COLOR`, `COCKPIT_COLOR`, `ENGINE_COLOR` and
      `ENGINE_LIT_COLOR` are instance attributes from `tuning` (`color`, `fill`, `noseColor`, `cockpitColor`,
      `engineColor`, `engineLitColor`).
    - `draw` copies `x, y, vx, vy, angle, radius` and `pilot_thrusting` (False if missing) onto the puppet and calls
      `puppet.draw(screen)`. Then, when `tuning['showsHitPoints']`, it draws `EnemyHunter._draw_hit_points` (moved),
      with the bar `40 * radius / config.SHIP_SIZE` wide.
    - `draw_death` copies the position and `death_timer` and calls `puppet.draw_death(screen)`.
- Consumes: `HunterShip`, `HunterFlight`, `WorkerPilot`, `NeuralPilot`, `hunter_settings_for`,
  `ProtagonistSurroundings`, all unchanged.

- [ ] **Step 1: Write the failing tests** in `tests/test_pilot_trait.py`

Use a creature from `creature_parts.creature([Pilot(...), TakesHits(12)], key='static')` with its Body swapped for a
`HunterShipBody`, and a `world()` stand-in. Add `rules_worker`, `enemy_policy` and `protagonist` to the stand-in.
`tests/test_rules_hunter.py` already has the fake workers (`SilentWorker`, `FakeGame`) to reuse.
- `test_a_pilot_flies_its_creature_and_its_shots_join_the_level`: a neural pilot with a stub policy that always
  thrusts and fires, and a protagonist straight ahead. After 30 frames the creature has moved along its heading, and
  `world.projectiles` holds `'enemy'` shots with the kind's colour.
- `test_the_creature_follows_the_craft`: after a frame, the creature's `x, y, vx, vy, angle` equal the craft's.
- `test_a_push_moves_the_craft_and_the_pilot_feels_it`: set the creature's `vx += 3`, step, and assert
  `craft.take_hit() == pytest.approx((3.0, 0.0))` and the craft moved by the push.
- `test_a_neural_pilot_without_a_model_never_flies`: `enemy_policy()` returns None, 30 frames: it has not moved and
  fired nothing.
- `test_closing_stops_the_pilot_and_its_worker_once`: a rules pilot on a worker whose `close` counts its calls; the
  creature dies and the encounter is closed, and `close` was called exactly once.
- `test_a_copy_leaves_the_pilot_behind`: `deepcopy` of a flying piloted creature has `flight is None` and
  `pilot_worker is None`, and the original still flies.
- `test_an_unknown_mode_is_rejected`: `Pilot.from_params({'mode': 'jev'})` raises `ValueError`.
- `test_the_body_draws_the_arrowhead_in_the_kinds_colours`: the drawn pixels include `tuning['color']`, a
  `showsHitPoints` kind draws a bar above it, and `draw_death` at half its death draws a ring.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite**

- [ ] **Step 5: Commit**

---

### Task 2: The Terminator is a Creature

**Files:**
- Modify: `config/enemies.json` (`rules_hunter`), `enemy_kinds.py`, `game.py`, `game_handlers/spawn_manager.py`,
  `rendering/level_editor.py`, `tests/test_rules_hunter.py`, `tests/test_rules_hunter_game.py`,
  `tests/test_layout_play.py`, `tests/test_enemy_kinds.py`
- Delete: `entities/rules_hunter.py`

**Interfaces:**
- Consumes: Task 1's `Pilot`, `HunterShipBody`, `Encounter.close()`.
- Produces:
  - **Catalogue `rules_hunter`:**
    - `tuning`: `{"size": 8, "color": [255,90,90], "fill": [110,25,25], "noseColor": [255,215,200],
      "cockpitColor": [60,10,10], "engineColor": [170,60,20], "engineLitColor": [255,150,80],
      "showsHitPoints": false}`;
    - `allegiance` `enemy`, `body` `hunterShip`;
    - traits in order: `pilot {"mode": "rules"}`, `ramsShip`, `takesHits {"hitPoints": 12}`.

    No `dropsPickup` and no `shovedByShots`: today's Terminator leaves no crystal and shots don't push it.
  - **`enemy_kinds`:**
    - `hunters()` is the kinds whose traits include `pilot`, plus any old-style kind with a top-level `pilot` while
      the Vibers still have one (Task 3 removes that).
    - `EnemyKind.pilot` is the pilot trait's `mode` for a Creature kind.
  - **Game, the pilot's two world methods:** `rules_worker()` is today's `_make_rules_worker()`, renamed and public;
    `_rules_worker_factory` still overrides it for the lab. `enemy_policy()` is today's `_load_enemy_policy()`,
    renamed and public.
  - **Game, spawning:** `_spawn_enemy_hunters_at` makes the rules kind with `make_enemy` and adds it to the roster. The
    Viber kinds keep their classes until Task 3.
  - **Game, flying and closing:**
    - `_fly_enemy_hunters` flies only enemy hunters that are not Creatures; the Encounter flies the rest.
    - `_close_enemy_hunters()` calls `self.encounter.close()` and then `close()` on any enemy hunter that is not a
      Creature. Keep the name: the lab, the editor and the frame timer call it.
  - **`make_enemy`** builds `rules_hunter` (a hunter kind with a Body) and still refuses the old-style ones.
  - **Level editor:** the `rules_hunter` preview is `creatures.build('rules_hunter', centre)`, drawn without spawning.
    The stubs `_NullWorker` and `_NoView` go when Task 3 removes their last use.

- [ ] **Step 1: Write the failing tests**

Move the Terminator's tests onto the Creature, keeping what each checks:
- `tests/test_rules_hunter.py`: protagonist-only view, 12 hits, `'enemy'` shots, closing the pilot and worker on
  death, the portrait copy, drawing red, firing at a protagonist in the open.
- `tests/test_rules_hunter_game.py`: placement, restart and quit stop the workers, kills credited with no crystal,
  the portrait, the exit waiting for it, contact cost, shots in `game.projectiles`.

New tests in `tests/test_rules_hunter_game.py`:
- `test_restarting_the_level_stops_every_terminator_thread`: level 25 with the threaded worker. Run `start_level`,
  `start_level` again, then `_close_enemy_hunters()`. No thread named `jev-pilot` that an enemy hunter started is
  still alive (`threading.enumerate()`, after joining with a 2 s timeout).
- `test_its_own_shots_never_hit_it`: a Terminator, its own `'enemy'` shot placed on it, and a Crab's shot placed on
  it. `encounter.shoot` returns False for both, and its hit points are unchanged.
- `test_a_terminator_is_a_creature`: level 25's `rules_hunter` is a `Creature` with a `HunterShipBody`, and
  `game.enemy_hunters` lists it.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite; compare on level 25 with the lab's synchronous worker; check on the real display**

Compare the clean worktrees over 1800 frames: shots fired, shots that hit the player, the Terminator's travel per
frame, and its hit points at the end. The ship is held still with its shield up and placed 300 px from the Terminator
with a clear line. Pixel-compare it drawn flying (two headings, engine on and off) and at three points of its death.

- [ ] **Step 5: Commit**

---

### Task 3: The Vibers are Creatures

**Files:**
- Modify: `config/enemies.json` (`neural_hunter`, `boss_viber`, `vibelet`), `enemy_kinds.py`, `game.py`,
  `game_handlers/spawn_manager.py`, `rendering/level_editor.py`, `tests/test_neural_hunter.py`,
  `tests/test_viber_sizes.py`, `tests/test_enemy_kinds.py`
- Delete: `entities/neural_hunter.py`, `entities/enemy_hunter.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces:
  - **Catalogue:** the three entries share the Viber's colours: `color [255,90,230]`, `fill [100,20,95]`,
    `noseColor [255,210,245]`, `cockpitColor [55,10,50]`, `engineColor [170,50,140]`, `engineLitColor [255,140,230]`.
    Each has `allegiance` `enemy` and `body` `hunterShip`. Traits in order: `pilot {"mode": "neural"…}`,
    `ramsShip`, `takesHits`.

    | key | size | showsHitPoints | hitPoints | shotStrength |
    |---|---|---|---|---|
    | `neural_hunter` | 8 | false | 12 | 1.0 |
    | `boss_viber` | 16 | true | 24 | 1.0 |
    | `vibelet` | 4 | false | 1 | 0.1 |

    `shotStrength` is the `pilot` parameter.
  - **`enemy_kinds`:** the old hunter form goes: `HunterStats`, `EnemyKind.hunter`, `_HUNTER` and the top-level
    `pilot` key. `hunters()` is the kinds with a `pilot` trait.
  - **Game:** `_spawn_enemy_hunters_at` makes every hunter kind with `make_enemy`. A kind whose pilot is `'neural'` is
    skipped, with today's warning, when `enemy_policy()` is None. `_fly_enemy_hunters` is deleted;
    `_close_enemy_hunters()` is `self.encounter.close()`.
  - **Level editor:** previews are `creatures.build(kind, centre)`; `_NullWorker` and `_NoView` go.

- [ ] **Step 1: Write the failing tests**

Move `tests/test_neural_hunter.py` and `tests/test_viber_sizes.py` onto Creatures:
- colour, flying and shooting, 12 hits;
- drawn but never flown with no policy;
- the portrait copy, layout placement, hunting only the player, flying and drawing in a level;
- sizes, hit points and shot strength from the catalogue, bullet-strength scoring;
- the exit counting by kind, the hit-point bar only on `boss_viber`.

New test:
- `test_without_a_model_no_viber_is_placed_and_the_level_still_plays`: level 21 with `enemy_policy` returning None.
  No Viber kinds are on the roster, a warning was logged, the other enemies are, and after killing them all the exit
  policy is met.

- [ ] **Step 2: Run them to make sure they fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite; compare on levels 21 (Boss Viber and Vibelets) and 24 (three Vibers); check on the real display**

As Task 2, with the neural pilot, which is deterministic (greedy). Pixel-compare each size flying and dying, and the
Boss Viber's bar at full and half hit points.

- [ ] **Step 5: Commit**

---

### Task 4: Every enemy is a Creature; the speed gate; docs

**Files:**
- Modify: `game_handlers/collision_handler.py` (`shoot_into` and `shoot_enemy_hunters` go), `creatures/encounter.py`
  (`shoot` returns False when no creature takes the shot; the docstring loses the hunters), `game.py` (`_step_gates`
  no longer adds `enemy_hunters` on its own; they are in the roster), `tests/test_encounter.py`,
  `tests/creature_parts.py`, `tests/test_rules_hunter_game.py`, `tests/test_neural_hunter.py`, `ARCHITECTURE.md`,
  `GLOSSARY.md`, `docs/superpowers/validation/2026-10-20-frame-times.md`

- [ ] **Step 1: Delete, then grep**

Run `grep -rn "EnemyHunter\|RulesHunter\|NeuralHunter\|BossViber\|Vibelet\b\|VIBERS\|shoot_into\|shoot_enemy_hunters\|_fly_enemy_hunters\|HunterStats\|RULES_HUNTER_HIT_POINTS" --include=*.py .`.
Expected: no hits outside `docs/`. A test that only asserted the fall-through to `shoot_into` is deleted and listed.

- [ ] **Step 2: Run the full suite**

- [ ] **Step 3: Speed gate**, as the Global Constraints say. Add the table to the validation file.

- [ ] **Step 4: Docs**
  - `ARCHITECTURE.md`:
    - every enemy is a Creature;
    - `pilot` and the craft;
    - `HunterShipBody`;
    - `on_close` and `Encounter.close`;
    - "Adding New Enemy Types": a piloted kind is a `pilot` trait.
  - `GLOSSARY.md`:
    - the Creatures line becomes "every enemy";
    - Pilot: it also flies the Terminator and the Vibers, and any creature given the `pilot` trait;
    - new term **Craft**: the hunter ship a pilot flies inside a creature, which the creature follows.
      _Avoid_: vessel, inner ship.

- [ ] **Step 5: Commit**

---

### Task 5: Hand back

Report:
- the speed table;
- what changes in play;
- the deleted tests (file::test, one line why);
- the rulings;
- what stage 6 has left: the allied hunter, `HunterFlight`, the duel and the lab onto Creatures, and breaking the
  craft into `thrusters`, `gun` and `energy`.

Then ask whether to write the stage 6 plan.
