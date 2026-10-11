# Rules lab: an experiment loop for the rules hunter

## Goal

Improve the rules-based hunter pilot (`hunter/rules_pilot.py`) by experiment instead of intuition.
Each candidate change is run headlessly, far faster than real time, on seeded levels, scored
against a baseline, and kept only if it beats the baseline by more than the noise. Every
experiment is written down. The product is a better hunter whose rules each have a measured
reason, plus the lab that produced it.

## Scope

- Scenario: the hunter alone. The player is parked and hidden from the hunter, as in autoplay.
- The pilot under test is the rules pilot. Jev and the student are not touched.
- Out of scope: a scripted moving player (following the player is not scored in this version),
  changes to Jev's questions, and any on-screen label.

## Why this is feasible

Physics, entities and the hunter run on frame counts, not wall time. Only scoring and some UI
timers use the real clock. A quick measurement of the real `Game` run headless with a fake clock
and a synchronous pilot gave 14x to 39x real time per core on levels 13, 18 and 24. `Game` stays
unchanged; the harness injects a synchronous worker (the `PilotWorker` interface: `busy`,
`submit`, `poll`, `cancel`, `close`, `join`) through the existing `hunter_worker` attribute and
replaces the `HunterController` clock.

## Harness — `experiments/harness.py`

An *episode* is one level, one seed, one `RuleParams`.

- Setup: construct `Game` under the dummy SDL drivers at 1352x878 (the real play scale), start the
  level, mark the player moved, summon the hunter beside the start, and hide the player. The
  hunter stays indestructible, as in the game: hits are counted, not suffered.
- Step: `game.update(1.0)` per frame; the fake clock advances 1/60 s per frame.
- End: all enemies dead, or the horizon (90 simulated seconds). The hunter cannot die.
- Determinism: after the level starts, `random.seed(seed)`. A test runs one episode twice and
  requires identical metrics.
- Isolation: one process per episode batch (`multiprocessing`, spawn), each initialising pygame
  once.

### Counters

- `kills`: the live enemy count falling. `enemies_spawned`: the live count rising (spawners, eggs).
- `wall_hits`: rising edges of the hunter's wall collision check (a contact held for many frames
  is one hit).
- `hits_taken`: damage calls from enemy contact or bullets, counted at the damage path and
  limited to one per 0.5 s (the game's damage-immunity window), so a contact held for many frames
  is a few hits and one bullet is one hit.
- `idle_fraction`: share of the episode with no kill in the last 20 seconds (zero while under 20 s
  have passed).
- `elapsed`: simulated seconds until the episode ended, floored at 45 s for rates (a very quick
  clear would otherwise give an extreme rate).

### Score — `experiments/score.py`

Per episode: `kill_pct_per_min − w_wall·wall_hits_per_min − w_hit·hits_taken_per_min −
w_idle·idle_fraction`, where `kill_pct_per_min` is the percentage of all enemies that existed
(those at the start plus those that spawned) killed per minute. Using the total that includes
spawns means a level with a spawner cannot be farmed for a bigger number. (An earlier version also had a death term, with damage switched on. It was
removed: the real hunter cannot die, deaths ended 61% of episodes early, and the cliff made scores
lumpy. See `docs/experiments/001-baseline.md`.) Every term is also reported on its own, so a gain in one
cannot hide a loss in another. The weights are fixed once, from a baseline run, so each term has
a comparable scale, and then not changed during a comparison. They are a deliberate human choice;
the baseline report shows the spread of each term to support it.

## Level sets and seeds

Tune set: levels 13, 14, 15, 17, 19, 20, 22, 25, 26, 27 plus boss levels 18 and 30.
Held-out set: levels 16, 21, 23, 28, 29 plus boss level 24.
Seeds 0 to 5 per level (72 tune and 36 held-out episodes; two seeds were too few to see small
effects, see `docs/experiments/002-round1-numeric-search.md`). Both sets mix boss and normal levels. The held-out set is scored once per
round, reported, and never used to choose a candidate. Levels 4 to 12 are not included yet; they
can be added to either set later.

## Tunable rules — `hunter/rule_params.py`

`RuleParams` is a frozen dataclass whose defaults equal today's values. It is threaded through
`decide`, `pilot_state` and the hunter settings; module constants it replaces keep their names as
the defaults. A regression test checks that default parameters give identical decisions to the
current code on recorded states, and that the existing hunter tests still pass.

Initial numeric parameters (all existing values):

| parameter | now | where |
|---|---|---|
| `steer_band_degrees` | 20 | rules pilot |
| `engage_standoff_cells` | 1.5 | `pilot_sensors` |
| `too_close_ratio` | 0.6 | `pilot_sensors` |
| `far_ratio` | 1.15 | `pilot_sensors` |
| `harmless_speed` (m/s) | 15 | `pilot_sensors` |
| `wall_follow_cruise` | 0.6 | `pilot_sensors` |
| `course_approach_fraction` | 0.7 | `pilot_sensors` |
| `cruising_speed_fraction` | 0.5 | `pilot_sensors` |
| `pulse_frames` | 6 | `model` |
| `request_interval` (s) | 0.25 | `HunterSettings` |

Structural variants are switches on `RuleParams` that default off (for example `burn_when_slow`,
the Jev tendency measured on the logged data), so an A/B comparison runs on identical seeds.

## The loop

**Round 1, automated numeric search.** Random search over bounded ranges using short, cheap
evaluations, promoting only the best candidates to full-length ones (successive halving), then
one-parameter-at-a-time hill-climbing around the winner. A change counts as an improvement only
if the paired difference against the baseline on the tune set is positive with a 95% paired
bootstrap interval that excludes zero. The result is scored once on the held-out set.

**Round 2 onward, hypothesis-driven.** Claude reads the failure data (where the hunter idles, why
it misses kills, what hits it), states a hypothesis with a prediction, adds the change behind a
switch, runs the paired experiment, and keeps or reverts it. Structural changes are promoted to
the default only after they pass the same tune and held-out checks.

## Lab notebook

`docs/experiments/NNN-title.md`, one per experiment: hypothesis, prediction, change (parameters or
switch), tune and held-out results with intervals and all component terms, decision (kept or
reverted), and what was learned. `docs/experiments/README.md` indexes them and records the current
baseline. Raw per-episode results go to `.astrovoid-local/experiments/` (gitignored).

## Entry point

`venv/bin/python -m experiments.run` with options for the parameter file or switches, the level
set (`tune`, `heldout`), the number of seeds, the horizon and the worker count. It prints a
per-term summary and writes the raw results.

## Testing

1. Harness: one episode ends for each reason (cleared, hunter dead, horizon); determinism (same
   seed twice gives identical metrics); the fake clock is what the controller sees.
2. Counters: wall hits count rising edges only; damage counts with indestructible on and off; kills
   do not count enemies spawning.
3. Score: components combine as stated; the 45 s floor on `elapsed`; a hunter that never moves
   scores worse than the baseline.
4. Params: defaults reproduce current decisions on recorded states; each parameter reaches the
   code that uses it (a changed value changes a decision).
5. Search: the paired-bootstrap rule accepts a planted improvement and rejects noise, using a
   synthetic scorer.

## Risks

- A hunter tuned alone may follow the player worse. The existing hunter tests guard the structure,
  and the scripted-player scenario is the later guard.
- Penalty weights can be gamed. Idle time is in the score for that reason, and the per-term
  reports are checked, not just the total.
- Kill farming. Lighthouses and egg-laying bosses spawn more enemies (the baseline credited 125 and
  183 raw kills on two levels that start with about 26). The score therefore uses the percentage of
  all enemies that existed, which removes the effect; raw kills per minute is still reported.
- Tuning to the tune levels. The held-out set, scored once per round, exists to catch it.
- Episode noise from game randomness. Seeding and paired comparisons are the answer, and the
  baseline run reports the spread.
