# Creatures and Traits, Stage 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Execute inline, with one whole-stage review at the end, following the user's stage 5 preference.

**Goal:** The allied hunter, duel combatants and experimental hunters become Creatures, and piloted creatures share independent propulsion, gun, burst-firing and energy traits instead of following a private HunterShip.

**Architecture:** The Creature becomes the only moving state. `pilot` decides controls; `thrusters` steers and moves; `burstFire` schedules rounds; `gun` creates projectiles; `energy` handles mortal damage. `HunterFlight` remains the small interface for a pilot's lifetime, status, pause and observation listeners, but its ship is a Creature and it no longer runs a second flight model.

**Tech Stack:** Python 3.10, pygame 2.6, pytest; existing neural policy and worker controllers.

**Spec:** `docs/superpowers/specs/2026-10-20-creatures-and-traits-design.md`, stage 6, plus the decomposition deferred by stage 5.

**User clarification (2026-10-21):** burst firing is a separate reusable trait. Do not bury burst state or scheduling inside the pilot, the gun, or a hunter-only motion implementation.

---

## Baseline, constraints and scope

Start from `bc3975a` on `refactor/enemy-catalogue`. Stage 5 report:
`docs/superpowers/validation/2026-10-21-creatures-stage-5-report.md`.

Implementation authorized on 2026-10-22 after the user confirmed ownership of the hunter edits and requested
their commit. Those edits are committed unchanged as `ffc8d91`, the integrated stage 6 baseline. Pushing is not authorized.

The user-owned hunter changes integrated in `ffc8d91` touched:

- `entities/hunter_ship.py`, `hunter/fire_control.py`, `hunter/flight.py`, `hunter/maze_route.py`, `hunter/senses.py`;
- `experiments/rollout.py`, `tools/ppo_neural.py`, `assets/neural/hunter.npz`;
- `tests/test_compass_reward.py`, `tests/test_hunter_flight.py`, `tests/test_senses.py`.

Stage 6 needs to change several of these same files. Before implementation, integrate that session's completed
commits or agree ownership explicitly. Do not edit, stage, revert or copy over its uncommitted changes. A clean
worktree at `bc3975a` is sufficient for planning and baseline measurement, but is not a substitute for integrating
the other session's flight changes before the final migration. Never stage `.codegraph/` or `.playwright-mcp/`.

Preserve neural observations, action ordering, policy dimensions, saved weights, trained physics, firing rules,
worker cancellation and lab output formats. No policy retraining, reward tuning or navigator changes belong here.
Keep stage 5's random enemy starting headings and knock sensing. Allied hunters and duel combatants retain their
current explicit initial headings. Do not add the ally to the enemy roster.

Full suite command after every task:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider tests
```

Baseline result: 2279 passed, one known unrelated failure in the other session's
`tests/test_senses.py::test_each_enemy_in_sight_shows_how_many_hits_it_has_left`. Re-establish this result after
integrating that work; do not assume that failure remains unrelated if the failure changes.

Stage files by name. Keep commits local. Use the repository's established commit attribution convention from
stage 5. Do not run the real-display pixel check: the user requested skipping it. Use headless surfaces and seeded
pixel comparisons; record the real-display gap in the report.

## Design contracts

### One moving state; two ways to drive it

A piloted Creature has no `craft`. Pilot state remains in `c.flight`, excluded by `Pilot.LIVE` from portraits.
No dynamic bound methods copied from HunterShip onto the Creature, no HunterShip subclass of Creature, and no
method on Creature that merely forwards to a hidden ship.

`HunterFlight.ship` remains a read-only alias to the Creature so read-only lab and rendering consumers need not
rename every local variable. Existing reads of `settings`, `health`, `max_speed`, `thrust_force`,
`current_rotation_speed`, `shots_fired`, `thrust_frames`, `burst_remaining` and immunity stay available as
per-creature trait state. Methods such as `take_damage`, `collect_powerup`, `take_hit`, `step` and
`check_wall_collision` move to their owning traits/functions or Encounter operations; migrate their callers.

Add `Encounter.step_creature(c, dt)` and `Encounter.close_creature(c)`. Extract the existing spawn/active/trait/Body
sequence into `step_creature`; `Encounter.step` retains its roster snapshot and crowd pass. A flight's `step(dt)`
uses `step_creature` for the allied hunter or a duel combatant. Enemy pilots are stepped only by their existing
Encounter. No frame can call both paths on the same Creature.

Replace `HunterFlight.fly(dt) -> shots` with `HunterFlight.step(dt) -> None`: shots enter the encounter world's
projectile sink exactly once. Each duel side supplies its existing separate shot list. The lab supplies its Game.
The enemy Encounter also uses the Game. Keep `pause`, `close`, `status`, `controller` and `on_observed`.
`Pilot.on_frame` calls `flight.decide()`; it must never call `flight.step()` recursively.

### Ordering preserves the trained flight model

The existing HunterFlight senses and chooses BEFORE HunterShip decrements its clocks. HunterShip then steers,
thrusts, fires from the pre-movement muzzle, coasts/caps speed, and resolves walls. Preserve that order:

1. `pilot`: sense, choose, fire-control solution, cancel unsupported burst.
2. `energy`: decrement damage immunity, in seconds (`dt / config.FPS`).
3. `thrusters`: steer/track/course, enforce decision burn budget, apply thrust.
4. `burstFire`: decrement its timer, decide whether one round is due.
5. `gun`: expire gun upgrades, emit that round at the current nose; emit `fired` only for an actual volley.
6. After all ordinary trait hooks: finish propulsion, cap speed, sweep walls and emit collision events.
7. Body animation; crowd hooks remain at the end of Encounter.step.

Add a no-op `Trait.on_after_frame(c, enc, dt)` and call it only on traits which override it (cache that tuple on
Creature). It exists for propulsion's final movement, so neither the pilot nor gun secretly moves the Creature.
Stop processing immediately if a trait kills the Creature, including during the late pass. Existing non-piloted
Thrusters behavior stays in its current ordinary hook; only its hunter steering mode uses the late hook.

`Controls` remains declared in `creatures/creature.py`. Extend it with `track`, `course`, `burn_heading`,
`burn_frames`, `burn_reference`, `decision_token`, `lead_degrees`, `on_target` and `gun_enabled`.
`decision_token` preserves the identity of a held PilotAction; do not reconstruct it each frame, or burn budgets
will restart. Existing `heading`, `aim`, `turn`, `thrust` and `fire` retain their meanings for existing brains.
Do not reduce a pilot action to just turn/thrust/fire: that loses course and tracking behavior.

### Separate responsibilities

| Trait/module | Owns | Does not own |
|---|---|---|
| `pilot` | controller, observer, surroundings, held decision and firing solution | movement, burst timers, ammunition, energy |
| `thrusters` | steering, burn budget, thrust, integration, swept wall contact | choosing a target, projectile creation, damage policy |
| `burstFire` | burst remaining, seconds until next round, burst/interval rules | creating projectiles, target search, movement |
| `gun` | muzzle, volley spread, colour/source/strength, upgrades, actual volley count | queued burst state, piloting |
| `energy` | health, immunity, strongest knock, proportional wall energy | enemy hit-point counting, kill credit, collision geometry |
| `HunterShipBody` | arrowhead, immunity flash, plume particles, death ring, optional hit bar | a moving puppet or flight |
| `HunterFlight` | pilot lifetime, observation listeners, stepping its Creature through Encounter | a private HunterShip |

The public shape of the new burst trait is:

```python
class BurstFire(Trait):
    NAME = 'burstFire'
    REQUIRES = ('gun',)

    def __init__(self, rounds=3, spacing=0.05, interval=0.25):
        self.rounds, self.spacing, self.interval = rounds, spacing, interval
```

Its per-creature state is `burst_remaining`, `fire_remaining`, and `burst_round_due`. It reads `controls.fire`,
`controls.on_target` and `controls.gun_enabled`. If gun_enabled is false it cancels the queue. A ready, aligned
trigger starts a queue; releasing the trigger retains an aligned queue; releasing it while unaligned drops the
queue. An unaligned held trigger waits. After the Gun emits `fired`, consume one round and reset fire_remaining
to spacing or the effective inter-burst interval. One volley consumes one round regardless of spread.
Single-shot rules/neural profiles use rounds=1. An ordinary creature can combine `burstFire` and `gun` with any
brain; a pilot is not required. Add rejection of rounds<1, spacing<0 and interval<=0.

Extend `Gun` with explicit `cadence='reload'|'burst'` and `aimMode='target'|'nose'` options, preserving all current
defaults. Burst cadence requires `burstFire`; set Gun.REQUIRES on the instance when cadence is burst and use
instance requirements in registry validation so ordinary guns
do not gain that requirement. Burst cadence creates a volley only when burst_round_due; it does not decrement a
second cooldown. Nose mode uses radius+5 muzzle offset, existing upgraded spread/speed/size rules, source derived
from allegiance and shotStrength. Keep current target-aimed guns' ranges and randomized reload behavior unchanged.
A non-pilot burst test sets on_target=True explicitly; target-based brains can obtain it from their aim checks.

`energy.py` exports `damage(c, enc) -> bool`, `register_hit(c, dvx, dvy)` and `take_hit(c)`. `damage` respects
indestructibility and immunity and returns whether this call killed the Creature; it uses `enc.kill` for lifecycle
hooks. Wall loss reads `c.wall_impulse` when `hit_wall` is emitted. Preserve the existing proportional loss formula
and strongest-knock clearing behavior. Enemy pilots still use TakesHits for bullets and indestructible Energy
for wall policy: do not give enemy hunters immunity between their 12/24 hits.

`gun` handles `pickup` events and exposes `collect_powerup(c, enc)` for collision code. This helper emits the
pickup event rather than giving Creature a hunter-only method. `energy.damage` handles friendly hunter damage;
ordinary enemy bullets still use TakesHits through Encounter.shoot.

### Construction and lifetime

Create `hunter/build.py` with a frozen `PilotSetup(settings, pilot, surroundings, owns_worker=False)` and:

```python
def make_hunter(pos, *, world, setup, angle=0.0):
    """Return a HunterFlight whose ship is a fully spawned allied Creature."""
```

`world` satisfies the existing Encounter world interface. Build a private one-Creature roster/Encounter for the
flight; do not add it to `Game.roster`. Add an optional `pilot_setup=None` argument to `creatures.build`, assigned
to the Creature before spawn hooks. Mark pilot_setup live so portraits do not copy its worker or surroundings.
The factory resolves settings into trait parameters before spawning (using dataclasses.replace on the kind),
sets the initial angle before ready(), and returns c.flight. Runtime setup is not catalogue tuning.

Enemy Pilot.on_spawn derives its setup from the existing world.rules_worker/world.enemy_policy and protagonist
surroundings. Enemy rules workers are owned; Game's reused allied worker and duel-supplied workers are borrowed.
Flight.close first marks itself closing, then runs close_creature; Pilot.on_close releases the controller, owned
worker and listeners through a private shutdown method which does not call Flight.close again. Repeated close
is a no-op. Owned workers close exactly once and live references are released.
Game/duel/lab retain responsibility for borrowed worker shutdown. Pause invalidates pending decisions, cuts the
engine and cancels a burst without decrementing energy/gun timers or moving the Creature. No callback or thread
may retain an ended level through a portrait.

### Catalogue and allegiance

Add `allied_hunter` to `config/enemies.json` with allegiance=friend, body=hunterShip, current green tuning and ordered
traits `pilot`, `energy`, `thrusters`, `burstFire`, `gun`. Default pilot mode is `jev`; runtime rules/neural selection
resolves immutable trait overrides without mutating the shared catalogue.

Keep `enemy_kinds.kind` able to look up any catalogue key. Add `all_kinds()` for every entry; make existing
`kinds()`, `anchored()` and `hunters()` explicitly select allegiance=enemy, preserving enemy ordering and names.
Registry validates the complete catalogue. Ensure make_enemy rejects friendly entries even if directly requested.
Do not rename enemy_kinds or introduce a second catalogue in this stage.

Player and allied projectiles must never hit friend Creatures through Encounter.shoot. Allied projectiles keep
source='hunter', with existing kill credit and pickup rules. Duel shots keep per-side ownership and their current
is_enemy threat flag override: two friend-allegiance combatants are opponents because of duel surroundings and
explicit victim routing, not because the normal Game treats allies as enemies.

## Files and responsibilities

| Path | Change |
|---|---|
| `creatures/creature.py`, `creatures/trait.py`, `creatures/encounter.py` | controls, late movement hook, single-creature stepping/closing |
| `creatures/traits/piloted.py` | decisions only, three modes, runtime setup, worker ownership |
| `creatures/traits/propulsion.py` | hunter steering and late integration, existing generic mode preserved |
| `creatures/traits/burst_fire.py` (new) | reusable burst scheduling |
| `creatures/traits/energy.py` (new) | damage, immunity and knock sensing |
| `creatures/traits/combat.py` | gun cadence, nose volleys, upgrades |
| `creatures/registry.py` | new traits and conditional requirements |
| `hunter/build.py` (new), `hunter/flight.py` | factory and Creature-backed pilot lifetime |
| `entities/hunter_ship_body.py` | standalone arrowhead/plume rendering |
| `entities/hunter_ship.py` | delete after last simulation and rendering reader migrates |
| `config/enemies.json`, `enemy_kinds.py`, `game_handlers/spawn_manager.py` | ally entry and enemy-only enumeration |
| `game.py`, `game_handlers/collision_handler.py` | summon/update/pause/damage/pickup/close through Creature traits |
| `hunter/duel.py`, `hunter/duel_enemies.py` | Creature combatants, per-side worlds and damage |
| `hunter/perception.py`, `hunter/senses.py` | read the same Creature state, energy knock helper |
| `experiments/harness.py`, `experiments/rollout.py` | Creature construction and events instead of ship monkeypatches |
| `tests/test_hunter_*.py`, `tests/test_duel_*.py`, `tests/test_experiment_*.py` | preserve behavioral checks through new interface |
| `ARCHITECTURE.md`, `GLOSSARY.md`, stage 6 validation report | final model, comparisons, test cull and rulings |

Do not modify `entities/ship.py` or player controls. Shared physics remains in `physics/thrust.py`; only extract
plume code from RotatingThrusterShip if needed to share drawing without copying player behavior.

## Execution tasks

### Task 1: Freeze behavior and resolve shared-file ownership

**Files:** Create `tests/test_hunter_creature_contract.py`; create
`docs/superpowers/validation/2026-10-21-creatures-stage-6.md`.

- [x] Record integrated base SHA, protected-file ownership, full-suite baseline and test failures before editing shared files.
- [x] Capture deterministic traces from the old implementation with a fake monotonic clock and SyncWorker. Record
  x/y/vx/vy/angle, health, immunity, thrust_frames, burst_remaining, fire_remaining, shots and observation vectors.
  Fixtures cover all ACTIONS, held/replaced decisions, worked burns, absent targets, tracking, wall sweeps, mortal
  and indestructible settings, upgrades and dt=0.5/1/2. Compare against the same trace after migration.
- [x] Preserve these existing assertions as the minimum firing contract:

```python
# Tests use existing ACTIONS and settings; retain equivalent assertions when replacing HunterShip setup.
spacing = round(settings.burst_spacing * config.FPS)
assert shot_frames == [1, 1 + spacing, 1 + 2 * spacing]
assert volley_sources == ['hunter']
assert enemy_shot_strengths == [1.0, 1.0, 0.1]  # Viber, Boss Viber, Vibelet
```

- [x] Run `tests/test_hunter_ship.py`, `tests/test_hunter_course.py`, `tests/test_hunter_powerups.py`,
  `tests/test_hunter_wall_energy.py`, `tests/test_hunter_flight.py` and the full suite. Commit the baseline tests
  and measurements by name; do not commit another session's work as part of this task.

### Task 2: Reusable burst firing, then gun emission

**Files:** Create `creatures/traits/burst_fire.py`, `tests/test_burst_fire_trait.py`; modify
`creatures/traits/combat.py`, `creatures/registry.py`, `tests/test_traits_combat.py`.

- [x] Write failing tests against a real Creature/Encounter using tests.creature_parts. Give it a non-pilot test
  brain that sets fire/on_target/gun_enabled, BurstFire(rounds=3, spacing=0.05, interval=0.25), and nose Gun with
  cadence='burst'. Test frame numbers above, release while aligned, release while unaligned, held unaligned,
  disabled gun cancellation, cooldown, single-round profile, spread as one round and independent state of two
  creatures sharing one trait. Parameterize dt and invalid constructor arguments.
- [x] Run the new file with the standard SDL command; expect missing BurstFire/Gun parameters to fail.
- [x] Implement the public BurstFire contract above; consume a round in on_event('fired'), after Gun succeeds.
  Implement the two Gun options without changing default Gun reload behavior. Reject missing conditional
  requirements and invalid cadence/aimMode values through registry validation.
- [x] Verify bursts on a non-pilot Creature and regression-test the existing crab/squid guns. Run the full suite.
- [x] Commit only this trait, gun extension and their tests.

A minimal non-pilot firing regression for this task:

```python
from creatures.traits.burst_fire import BurstFire
from creatures.traits.combat import Gun
from tests.creature_parts import creature, encounter


def test_a_non_pilot_creature_fires_one_three_round_burst():
    c = creature([BurstFire(rounds=3, spacing=0.05, interval=0.25),
                  Gun(cadence='burst', aimMode='nose')])
    enc = encounter(c)
    c.controls.on_target = c.controls.gun_enabled = True
    frames = []
    for frame in range(1, 13):
        c.controls.fire = frame == 1
        before = len(enc.world.projectiles)
        enc.step(1.0)
        if len(enc.world.projectiles) > before:
            frames.append(frame)
    assert frames == [1, 4, 7]
```

### Task 3: Direct Creature steering, energy and visual state

**Files:** Modify `creatures/creature.py`, `creatures/trait.py`, `creatures/encounter.py`,
`creatures/traits/propulsion.py`, `entities/hunter_ship_body.py`; create `creatures/traits/energy.py`,
`tests/test_energy_trait.py`, `tests/test_piloted_propulsion.py`; register Energy.

- [x] Write failing tests for direct Creature steering under every action, identity-sensitive burn accounting,
  clock ordering, pre-movement muzzle position, no tunnelling, speed caps, strongest knock read/clear,
  proportional fractional wall energy, immunity and indestructibility. Enemy TakesHits remains independent.
- [x] Add the Controls fields and late hook exactly as described. Extract step_creature and close_creature;
  retain spawn-once behavior and crowd ordering. Test that death skips later normal and late hooks.
- [x] Move HunterShip.step's steering/burn blocks to Thrusters' hunter mode and its integration to the late hook,
  using thrust.apply_thrust/coast/cap_speed/sweep_walls. Do not call HunterShip.step or create a craft. Preserve
  current generic Thrusters default behavior and source-of-settings resolution.
- [x] Implement Energy helpers and event handling. A wall sweep sets wall_impulse before hit_wall; Energy then
  records the knock and applies wall cost. Emit death through Encounter so pilot closure happens on wall death.
- [x] Move arrowhead geometry and death drawing into HunterShipBody. Keep particle state in the Body/Creature,
  preserve RNG order and immunity flash. Headless seeded surfaces cover headings, engine states, immunity,
  bar full/half and three death frames. Remove the rendering puppet's dependency on HunterShip; temporarily
  read the old craft's particle state until Task 4 migrates the pilot. Remove that fallback in Task 4.
- [x] Run baseline motion/energy/appearance tests and the full suite. Commit the new traits and hooks.

### Task 4: Pilot and HunterFlight use the Creature; migrate enemy pilots

**Files:** Modify `creatures/traits/piloted.py`, `hunter/flight.py`, `creatures/__init__.py`,
`creatures/registry.py`, `config/enemies.json`, `enemy_kinds.py`, `game_handlers/spawn_manager.py`,
`hunter/perception.py`, `hunter/senses.py`;
create `hunter/build.py`; modify `tests/test_pilot_trait.py`, `tests/test_rules_hunter.py`,
`tests/test_neural_hunter.py`, `tests/test_viber_sizes.py`, `tests/test_hunter_creature_contract.py`.

- [x] Write failing tests for a Creature with no craft, decisions populating Controls without moving it, exactly
  one step per frame, worker ownership, pause, death, restart, listeners and portrait copies. Assert pilot
  requirements reject missing thrusters/gun and that different Bodies can use the same pilot/burst traits.
- [x] Add the allied catalogue entry and enemy-only enumeration before using it in make_hunter; test that
  make_enemy rejects allies and enemy palette/count order is unchanged. This keeps this task independently safe.
- [x] Add PilotSetup and make_hunter, extend build with optional setup, and change Flight into the lifetime/step
  interface above. Enemy spawn derives setup; explicit factory setup is used for the ally/duel/lab. Support
  jev/rules/neural without inventing a catalogue-configured worker service.
- [x] Move existing HunterFlight observer/controller/fire-control logic to decide. It reads the actual Creature;
  replace ship.cancel_burst with burst-state cancellation. Pilot copies all decision fields into Controls;
  retain neural no-solution trigger behavior and listeners' observation order.
- [x] Resolve enemy profile settings into Energy/Thrusters/BurstFire/Gun parameters, preserving colours, strength,
  size, HP, random headings, protagonist-only surroundings and no-model omission. Remove craft copying and
  pilot_thrusting hand-over from Pilot; Body now reads direct Creature state.
- [x] Migrate perception/senses knock reading to energy.take_hit without changing observation shape, field order
  or policy weights. Compare Task 1 traces, including exact shot frames and observation arrays before accepting
  numerical motion drift. Run all enemy hunter and pilot tests, then the full suite. Commit.

### Task 5: Allied catalogue entry and Game integration

**Files:** Modify `config/enemies.json`, `enemy_kinds.py`, `game_handlers/spawn_manager.py`, `game.py`,
`game_handlers/collision_handler.py`, `tests/test_enemy_kinds.py`, `tests/test_hunter_integration.py`,
`tests/test_hunter_combat.py`, `tests/test_hunter_hotkey.py`, `tests/test_hunter_energy_gauge.py`,
`tests/test_hunter_powerups.py`, `tests/test_layout_play.py`.

- [x] Write failing summon tests for jev/rules/neural: isinstance(game.hunter, Creature), correct settings/green
  body, no ally in enemy counts/palette/exit/par, no friendly fire, hunter-source scoring, no double update,
  powerup upgrades, fractional energy gauge, pause/TTL cancellation, death animation and resummoning.
- [x] Re-run Task 4's ally enumeration/validation tests and verify all existing level/editor counts before
  changing Game. The catalogue entry and filtering already exist; do not add a second ally entry.
- [x] Summon through make_hunter with Game world and GameSurroundings; retain current worker reuse/ownership.
  _update_hunter calls flight.step (shots already enter Game.projectiles), advances death once and respects all
  existing freeze/player-not-moved conditions. _close_hunter closes the Creature's traits before discarding it.
- [x] Change hunter damage sites in collision_handler (projectiles, contacts, blasts) to energy.damage(hunter,
  encounter); change knock sites to register_hit; change crystal collection to collect_powerup(hunter,
  encounter). Update Game call sites to supply the hunter flight's encounter. Preserve projectile spending,
  explosion count, sound and kill credit. Do not offer the ally through enemy Encounter.shoot.
- [x] Keep the allied flight outside the enemy roster; draw and gate paths visit it once. Check restart/quit and
  hotkey replacement with outstanding decisions. Run all hunter Game tests and full suite. Commit.

### Task 6: Duel and lab migrate to the same Creature path

**Files:** Modify `hunter/duel.py`, `hunter/duel_enemies.py`, `experiments/harness.py`, `experiments/rollout.py`,
`tests/test_duel_arena.py`, `tests/test_duel_enemies.py`, `tests/test_duel_safety.py`,
`tests/test_experiment_harness.py`, `tests/test_experiment_rollout.py`, `tests/test_experiment_run.py`.

- [x] Write failing tests: both combatants are Creatures, independent settings and colours, separate sinks,
  explicit opponent routing, no self-hits, wall immunity in duel, timeout/draw/death and borrowed worker cleanup.
  Lab tests pin fake-clock decision rate, stochastic neural RNG, initial heading, shot/thrust counters,
  observation callback order and existing output keys.
- [x] Add one Encounter world per duel side whose projectile sink is arena.shots[side.name] and surroundings
  are DuelSurroundings. Replace _fly with flight.step and preserve is_enemy override for new shots. Damage
  opponents through Energy; preserve optional DuelEnemies update and shot ordering. Close all flights safely.
- [x] Build lab flights through make_hunter with existing settings/clock/pilot/RNG. Replace monkeypatches of
  check_wall_collision, take_damage, collect_powerup and step with existing trait events and a frame callback
  on HunterFlight: on_frame(listener), called after a completed step with Creature, dt, held action and emitted
  volley count. Wall/damage/pickup counters subscribe to explicit events with the same attempted-versus-applied
  meaning as the old counters. Listener collections are cleared on close and are never copied into portraits.
- [x] Keep recorder.begin/before_frame/after_frame, rollout fields, trained weights and output schemas unchanged.
  Run the experiment, duel, shadow and student tests; compare baseline deterministic episode traces. Run full
  suite and commit. Do not alter PPO algorithm or reward definitions to make the refactor's tests pass.

### Task 7: Delete the old ship, validate and document

**Files:** Delete `entities/hunter_ship.py`; migrate remaining behavioral tests in `tests/test_hunter_ship.py`,
`tests/test_hunter_appearance.py`, `tests/test_hunter_course.py`, `tests/test_hunter_flight.py`; modify
`ARCHITECTURE.md`, `GLOSSARY.md`, `docs/superpowers/validation/2026-10-21-creatures-stage-6.md`.

- [x] Find remaining callers before deletion:

```sh
rg -n 'HunterShip|entities\.hunter_ship\b|\.craft\b|hunter\.step\(|hunter\.take_damage\(|hunter\.collect_powerup\(' --glob '*.py' --glob '!venv/**' .
```

  Migrate real behavior tests to make_hunter/Encounter/traits. Delete only tests of obsolete construction seams;
  list file::test and its reason. HunterShipBody is a valid remaining class; do not rename it to clean a grep.
  Remove old imports once no simulation, appearance, tool or test consumer needs the class.
- [x] Run full suite and deterministic enemy/ally/duel/lab trace comparisons. Run headless seeded pixel checks;
  retain the user's real-display skip. Smoke the seeded 40-level progression, beacon summon, paused/resumed
  hunter, neural mortal wall death, duel with/without enemies and one rules/neural lab episode. Pin commands
  and observed output in the validation report rather than claiming unobserved visual play.
- [x] CPU speed gate: two clean worktrees at integrated baseline and candidate, exclude unrelated work, alternate
  five rounds; 60 warm-up + 600 frames, seed 1, time.process_time. Measure levels 1/8/21/24/25/40 without an ally
  and with a rules or greedy neural ally. Include a duel and lab episode throughput comparison. For the ally
  use fixed spawn/heading and fake clock/SyncWorker; normal worker roundtrip timing is not a refactor metric.
  Record medians, spread and raw CSV. Stop and report any >20% regression before committing completion.
- [x] Update architecture with trait ordering, burstFire ownership, Creature-backed HunterFlight, single state,
  enemy-only catalogue enumeration, worker ownership and lab hooks. Update glossary Craft to explain that
  the former private craft was removed; Burst is a queued group of rounds, Volley is projectiles emitted at once.
- [x] Request one whole-stage code review against the integrated baseline, focused on trained behavior, burst
  reuse, allies leaking into enemy systems, double stepping, death/portrait lifecycle and lab observability.
  Fix important findings, re-run affected checks and record deferred minor issues.
- [x] Commit verified files by name. Hand back the speed table, gameplay differences, deleted tests, every
  ruling, review findings and remaining limitations. Keep the branch local until pushing is authorized.

## Self-review checklist

- [x] Spec stage 6: allied entry, Jev/rules/neural, HunterFlight, duel and experiments all have explicit tasks.
- [x] Stage 5 deferred work: craft removed; propulsion, gun, energy and independent burstFire covered.
- [x] Burst test demonstrates a non-pilot user; gun never owns a queued burst.
- [x] Pre-movement shooting, before-clock sensing, identity-sensitive burns and worker ownership specified.
- [x] Ally excluded from enemy counts, editor, par, exits and friendly-shot collision offers.
- [x] Active other-session work is integrated before shared files are edited.
- [x] Complete suite, deterministic comparisons, headless drawing, speed gate and one final review included.
