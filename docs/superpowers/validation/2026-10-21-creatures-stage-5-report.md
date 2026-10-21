# Creatures stage 5 report

Every enemy is now a Creature. The Terminator and all three Viber sizes use `pilot`, `hunterShip`, `ramsShip` and
`takesHits`; their old classes and collision/flying paths are removed. The allied hunter is unchanged by this stage.

## Verification

Task 3: full suite 2278 passed, one known failure in another session's uncommitted
`tests/test_senses.py::test_each_enemy_in_sight_shows_how_many_hits_it_has_left`.
Final review found and fixed contact with inactive players; the regression failed before the fix, and 63 focused tests passed after it.
The real-display pixel check was skipped at the user's request. Prior session's deterministic comparisons on levels
21, 24 and 25 matched with starting heading forced to zero; default random headings change trajectories.

Final full suite: **2279 passed, 1 failed** in 275.31 seconds. The only failure is the same other-session
`test_senses` test above (`enemy0_hits` is absent from `FEATURE_NAMES`). Final focused verification: 92 passed.


## Stage 5 gate: every enemy is a Creature

Measured on 2026-10-21 in CPU time (`time.process_time`), as stage 4: two clean worktrees alternating, five
rounds, seed 1, 60 warm-up frames and 600 measured frames on levels 1, 8, 21, 24, 25 and 40. Baseline `743d4d3`
against `5f87271` plus Task 4 cleanup and the inactive-player contact guard. Other-session changes were excluded.
The scratch timer is the stage 4 timer with its timestamps changed to `time.process_time`. Values below are
medians of update + draw, in ms/frame. The first two preliminary rounds were excluded because the review fix
was not yet included; five complete alternating rounds followed with the fixed code. Raw samples:
[2026-10-21-stage5-speed.csv](2026-10-21-stage5-speed.csv).

| level | enemies | stage 4 (743d4d3) | stage 5 | change | stage 5 spread |
|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 4.126 | 4.227 | +2.4% | 4.037–4.397 |
| 8 | 33 | 6.380 | 6.260 | -1.9% | 5.658–6.567 |
| 21 | 13 | 9.903 | 10.098 | +2.0% | 9.235–10.532 |
| 24 | 3 | 2.733 | 2.661 | -2.6% | 2.366–2.914 |
| 25 | 1 | 2.141 | 2.173 | +1.5% | 1.883–2.307 |
| 40 | 32 | 12.871 | 13.089 | +1.7% | 12.317–13.356 |

**Passed**: every level is within the 20% limit.


## Changes in play

Hunters keep their trained flight model, colours, shot strengths, hit points and no-pickup deaths. They hunt only
the protagonist. Neural kinds are omitted with a warning if no model is installed. Restarting or closing a level
stops its pilot workers; portraits carry no running pilot.

Creatures start at random headings rather than always facing right. On level 24 the prior session observed travel
change from 0.30 to 0.78 pixels/frame over 30 seconds; forcing heading zero restores identical behavior. Pilots now
sense knocks from ramming, blasts and gates through the craft's `register_hit`.

## Removed or renamed tests

- `tests/test_encounter.py::test_a_shot_that_misses_every_creature_goes_to_the_old_code`: obsolete fallback removed;
  replaced by `test_a_shot_that_misses_every_creature_is_not_consumed`.
- `tests/test_neural_hunter.py::test_it_flies_on_the_neural_pilot_and_returns_shots_for_the_game`: replaced by
  `test_it_flies_on_the_neural_pilot_and_its_shots_join_the_level`, testing Encounter shot placement.
- `tests/test_rules_hunter.py::test_it_flies_without_a_target_and_returns_a_list`: replaced by
  `test_it_flies_without_a_target_and_fires_nothing`, testing Creature frames.
- `tests/test_rules_hunter.py::test_twelve_hits_destroy_it_and_the_twelfth_reports_it`: replaced by
  `test_twelve_hits_destroy_it_and_only_the_twelfth`, testing hits through the Encounter.
- `tests/test_rules_hunter.py::test_its_shots_are_enemy_shots`: renamed to
  `test_its_shots_are_enemy_shots_in_its_colour`, adding colour verification.
- `tests/test_rules_hunter.py::test_a_copy_for_the_death_portrait_carries_no_pilot_worker_or_game`: replaced by
  `test_a_copy_for_the_death_portrait_carries_no_pilot_or_worker`, testing the Creature's live attributes.

Other session's modified tests are excluded from this report.

## Rulings

- Task 1: Ruling: HunterShipBody's puppet takes the craft's thrust_particles and thrusting when the creature has a craft — the plume is the craft's own state, so pixels match the old hunter — cost if wrong: a Body that reads one trait attribute (craft).
- Task 1: Ruling: closing drops flight and pilot_worker (set to None) — that is what makes close happen once — cost if wrong: none seen.
- Task 1: Ruling: craft COLOR falls back to HunterShip.COLOR when the kind's tuning has no color — keeps pilot transferable — cost if wrong: none.
- Task 2: Ruling: the craft starts at the creature's heading (random for a Creature), where the old Terminator always started facing right — keeps pilot transferable and honours a launched creature's heading; level 25 comparison with the start heading forced to 0 is identical (120 shots, 28 near the ship, travel 0.178/frame, hp 12) — cost if wrong: Terminators start facing a random way.
- Task 2: Ruling: Pilot's clock is `from time import monotonic` (module-level name) so tests can patch it — same clock as before.
- Task 2: Ruling: _NullWorker removed in Task 2, not Task 3 — its last use went with the Terminator preview — cost: none.
- Task 2: Ruling: shoot_into offers shots only to non-Creature hunters during the transition — cost: none (gone in Task 4).
- Task 3: Ruling: real-display pixel check skipped at the user's explicit request on 2026-10-21; headless drawing tests remain covered.
- Task 3: Ruling: the level 21 no-model test uses AllCleared to prove all placed enemies can be cleared; its layout has no egg. This does not verify level 21's actual exit configuration.
- Task 4: Ruling: obsolete-name grep retains only Vibelet display names and prose in tests; deleting a supported display name to satisfy a textual grep would be incorrect. No obsolete classes or methods remain.

## Review follow-up

The inactive-player collision regression is fixed. Stale migration descriptions were corrected. Deferred minor:
the no-model level 21 regression substitutes `AllCleared` and proves roster clearance, rather than checking that
level's actual exit policy. No other important findings remain from the review.

## Stage 6

Move the allied hunter, `HunterFlight`, duel and lab onto Creatures, and break the craft into `thrusters`, `gun`
and `energy`. A stage 6 plan has not been written or authorized yet.
