# Neural Jelly

The neural Jelly is an opt-in, trained brain for the 1-HP Jelly. It replaces the scripted `chase`, `drift` and
`keepsApart` traits with one `neuralJelly` trait. A recurrent policy steers the Jelly through the cave, and teams of
Jellies learn to close in on a target from different sides. The scripted Jelly (`aggressive`) is unchanged and stays
the default everywhere. The neural brain only runs on Jellies of the separate `neural_jelly` kind.

Design: `docs/superpowers/specs/2026-10-31-neural-jelly-design.md`. Trainer architecture: `docs/modular-training.md`.

## Pieces

| Piece | Where |
|---|---|
| `neural_jelly` creature kind (same body, size, 1 HP, contact damage and bouncing as `aggressive`) | `config/enemies.json` |
| Team, intent physics, lazy policy driver | `creatures/jelly_team.py` |
| Observation, action mapping, scripted teacher, `load_policy` | `learning/adapters/jelly.py` |
| Training scenario, curriculum, metrics, selection gate | `learning/adapters/jelly_scenario.py` |
| Replay hooks | `learning/adapters/jelly_replay.py` |
| `training_ship` creature kind (stage 3 only) | `config/enemies.json` |

## What a Jelly senses and does

Each Jelly runs the shared policy on its own observation, once every `DECISION_FRAMES` frames.

- **Itself:** speed, facing (sin/cos), velocity forward and sideways, and wall-distance rays all round (the hunter's
  ray count, 550 px reach).
- **Its target:** present flag, bearing relative to its facing (sin/cos), distance, closing speed. The target is
  the nearest living creature of the opposite allegiance (`Encounter.target_entity_for`). In the game that is
  the player ship or an allied hunter.
- **Its four nearest teammates:** present flag, bearing, distance, their facing and speed. Empty slots are
  zero-filled.
- **No messaging.** Jellies coordinate only through what they can see of each other.

There are two continuous action heads. `heading` is the desired direction (tanh mapped onto ±π). `accel` runs from
-1 (brake) to +1 (full thrust). The intent physics bounds both: a maximum turn rate, acceleration rate and top
speed. There is no instant change of heading, and braking slows the Jelly but never pushes it backwards. Walls
use the game's own collision response (`bouncesOffWalls`).

## Training: task `jelly_team`

Jellies train in the real cave arenas (`TRAIN_LEVELS` 11, 13, 14, 16, 17, 19, 21, 27; `HOLDOUT_LEVELS` 15, 20, 23
are never trained on), using the game's Encounter, Jelly body and wall code.

### Curriculum

1. **Stage 1: navigation.** A solo Jelly hunts one plain drifting practice target. Body contact is a catch
   (+10). The target respawns at least 300 px away and the episode runs to the horizon, so the Jelly must catch
   again and again. The Jelly earns a small reward per pixel it closes on the target, and pays a penalty for being
   stuck (pushing for a whole second without moving 10 px).
2. **Stage 2: flanking.** The same scene with teams of 2, 3 and 4 Jellies. The catcher takes the catch reward and
   every teammate takes a quarter of it. Closing in from spread-out bearings earns a small flank reward, and pairs
   bunched closer than 40 px pay a small penalty. One case in four is a stage-1 solo case, so navigation keeps
   being rehearsed.
3. **Stage 3: hunting the ship.** There is no plain target. A `training_ship` hunts the Jellies while they hunt it
   (see below). Each touch that costs the ship a hull point earns +4, killing it earns +10 more, and a Jelly dying
   costs -5, with team shares on all three. The episode ends when the ship dies, every Jelly dies, or at the
   horizon. One case in four is a retention case, alternating between a stage-2 case and a stage-1 case.

Promotion is automatic:
- Stage 1 to 2 needs the training catch rate above the scripted Jelly's held-out rate, and the stuck share below
  it.
- Stage 2 to 3 needs the angular spread and team catch rate above the scripted team on the held-out team scenes.
- Stage 3 is final.

### The training ship

`training_ship` is the allied hunter ship made weaker. Its top speed and thrust are lower, it fires at half the
rate with half-strength shots, and its hull is mortal with three points. The frozen neural hunter
(`assets/neural/hunter.npz`) flies it, using the game's own gun, shots and hit rules. It has friend allegiance, so
every Jelly targets it, and Jelly contact damages it through the game's allied-hunter contact rule. It exists for
training only and no level uses it.

### Starting a run

Use the trainer dashboard / trainer tools with task `jelly_team`. A fresh run defaults to a 60 s horizon, 4
workers, 10000 iterations and **no imitation bootstrap** (`bootstrap_episodes=0`). The options are
`budget_seconds`, `bootstrap_episodes`, `bootstrap_epochs` and `seed`. From the command line:

```
python -m tools.ppo_neural --task jelly_team --start '' --out <run dir> --bootstrap-episodes 0 --budget-seconds 3600
```

The command-line default for `--bootstrap-episodes` is still 8. The trainer path overrides it to 0, but a
hand-launched `python -m tools.ppo_neural --task jelly_team` run needs `--bootstrap-episodes 0`. Replays work like the
crawler's: `learning.replay` through `learning/adapters/jelly_replay.py`.

`bootstrap_episodes` controls how many teacher encounters are collected; `bootstrap_epochs` controls passes over
those saved demonstrations. Zero epochs means the task default (4 for Jelly; existing other task defaults are
preserved). An experiment with `--set bootstrap_episodes=64 --set bootstrap_epochs=20` makes 1,280 imitation
updates for solo Jelly episodes, versus 32 for 8 episodes and 4 passes. The requested pass count is recorded in
the run config and manifest; changing it on resume is refused. Old runs with no override keep their original
default rather than borrowing another run's experiment. Bootstrap evaluation runs before PPO; a lower
imitation loss alone does not establish better held-out catching. Its results are saved in
`bootstrap-evaluation.json` before the first PPO iteration. The total wall-clock budget includes warm-start.

## Evaluation and the selection gate

`learning.run` keeps the checkpoint with the best `selection_score` on `validation_cases()`. It scores every fifth
iteration (and the bootstrap policy), then writes a final report from `evaluation_cases()`.

- **Real-game cave arenas** means the game's own cave levels held out of training: `HOLDOUT_LEVELS` 15, 20 and
  23, loaded from `levels/<n>.json` as the game builds them.
- **Validation** (checkpoint selection) uses seed 900 and nine episodes covering all three stages. On each
  held-out arena it flies a solo Jelly on the plain target, a team on the plain target, and a team against the
  training ship. The team sizes rotate over the arenas, so each of 2, 3 and 4 appears once per stage.
- **Final evaluation** uses seeds 1000 and 1001 on every held-out arena, with every team size of each stage, all
  three stages: 6 + 18 + 18 = 42 episodes. Selection never sees these seeds. `evaluation_cases(stage)` gives one
  stage's set, and the promotion baselines use it.

**The gate.** `selection_score` returns `-inf` unless the checkpoint beats the scripted Jelly flown on *the same
validation cases* at the run's horizon (`validation_baseline()`, cached per horizon). It must clear both bars:

- a strictly higher plain-target catch rate: catches per minute over the stage 1-2 episodes, since stage 3 has no
  plain target;
- a strictly lower stuck share of Jelly time, over all validation episodes. If both sides are never stuck, that
  counts as not worse.

A checkpoint that fails the gate never becomes `best.npz` by score. But `learning.run` always leaves a `best.npz`.
If no checkpoint ever passes, it is only a fallback: the policy saved when the run started (the bootstrap policy, or
the random initial one when bootstrap is off), or the last iteration's weights if nothing was saved earlier.

`evaluation.json` records which case happened in `selection_gate_passed`:
- `true`: a checkpoint was chosen because its score cleared the gate;
- `false`: `best.npz` is the fallback, and `train.log` and the console also show one
  `selection_gate_passed=False` line.

**Check `selection_gate_passed` before trusting `best.npz`.** When it is `false`, no checkpoint beat the scripted
Jelly, and the scripted Jelly is the better brain.

Checkpoints that pass are ordered by what the rewards value, in catch-equivalents per minute over every
validation episode: catches, plus ship hits ×0.4 and ship kills ×1, minus Jelly deaths ×0.5, all multiplied by the
share of Jelly time not spent stuck. Ship hunting and survival therefore count in the choice between passing
checkpoints.

**Metrics** (`metrics(rows)`, flat numbers in `train.log` and `evaluation.json`):
- `catches_per_minute`
- `time_to_contact`: seconds to the first catch or ship hit; an episode with no contact counts its whole length
- `stuck_fraction` and `stuck_seconds`
- `angular_spread`
- `survival_fraction`
- team catch rate, bunching, ship hits, kills, deaths and time to kill

Each of these is repeated per stage as `stage<n>_<key>`, for example `stage2_angular_spread` or
`stage3_survival_fraction`. `evaluation.json` also holds `versus_scripted`, a bootstrap interval of extra catches
per episode (`mean_extra_catches`, `lower_95`, `upper_95`) together with extra ship hits and Jelly deaths.

## Using trained weights in the game

```
JELLY_POLICY=/path/to/best.npz ./run.sh
```

- The game loads the file once at start (`learning.adapters.jelly.load_policy`) and exposes it as
  `world.jelly_policy`. Only Jellies of kind `neural_jelly` use it. Place them in a level layout as
  `{"type": "neural_jelly", "cell": [c, r]}` (or in the level editor). Neural and scripted Jellies can share a level.
- **Fallback:** if the file is missing, damaged, or was trained for another observation/action spec, the game logs
  one warning (`Jelly policy unavailable: ...`) and starts normally. The `neural_jelly` Jellies then chase exactly
  like scripted ones. Without `JELLY_POLICY` at all, they also chase like scripted ones.
- Inference is the NumPy path in `learning/policy.py`, so the game does not need Torch.
- The scripted `aggressive` Jelly is untouched, and no level uses `neural_jelly` until you put it there.

## Known limitations

- **An untrained policy mostly sits still.** A random initial policy steered greedily outputs small accelerations,
  so it barely moves. On the held-out stage-1 cases it caught nothing in 60 s.
- **The teacher uses privileged maze routes.** `learning.adapters.jelly.teacher` follows the existing `MazeRoutes`
  cell search, takes the furthest waypoint with body clearance, and brakes for turns and stopping distance. Moving
  gates are checked live by the route finder. It returns towards the current cell centre for tight corners and can
  escape a gate overlapping its spawn; an unreachable quarry makes it brake. The student's observations are unchanged.
- **Route finding improves the teacher, but imitation remains unproven.** On the same six `evaluation_cases(1)`
  episodes at a 60 s horizon, the routed teacher catches 2.83 per minute, versus the old teacher's 0.50 and the
  scripted `aggressive` Jelly's 4.17. The cell graph can still report no route in gated or disconnected areas.
  These are teacher scores, not a cloned student's performance. `bootstrap_episodes` stays 0 for `jelly_team`
  until a separate imitation experiment demonstrates a useful student.
- **The training ship's pilot misreads its health.** It reads its own health against the neural hunter's 10
  points, so on its 3-point hull a fresh ship feels like 30% health. It still hunts and kills, but it may fly
  more cautiously than a full-health hunter would.
- **`best.npz` can be a fallback.** Check `selection_gate_passed` in `evaluation.json` first (see above).
- **The gate is noisy.** It runs on only 9 validation episodes, 3 per stage, and the catch comparison uses only the
  6 stage-1/2 ones. Both comparisons are strict (`>` and `<`), so one lucky or unlucky catch can flip it. If the gate
  flips on luck, raise the episode count in `validation_cases()`.
- **The stuck half of the gate is weaker than it looks.** The scripted Jelly always counts as accelerating, so
  every slow second can count as stuck. A policy counts only above 0.1 accel, because it may legitimately wait for
  its flankers. Beating the scripted stuck share is therefore easy, which is why the catch rate must also beat the
  scripted Jelly. Also, `stuck_fraction` includes the stage-3 episodes, while the catch rate uses stages 1-2 only.
- **Validation and the final evaluation share arenas.** Both use held-out levels 15, 20 and 23 and differ only by
  seed (900 vs 1000/1001). The final report is independent of the episodes selection saw, but not of the arenas.
- **The bootstrap CLI default is still 8.** `tools/ppo_neural`'s `--bootstrap-episodes` defaults to 8, so a
  hand-launched `python -m tools.ppo_neural --task jelly_team` run needs `--bootstrap-episodes 0`. The trainer path
  sets 0.
- **The first selection is slow.** The first `selection_score` call in a run flies the 9 scripted validation
  episodes synchronously in the trainer process to build the baseline. That is a one-off stall of about 15 s at a
  60 s horizon. Later calls use the cached baseline.

### Per-run reward settings

The Next run form offers Jelly rewards, team shares, flank range and bunch distance under Rewards. CLI names use
`jelly_` prefixes, for example `--set jelly_catch_reward=12` and `--set jelly_death_penalty=7`. A new run may change
them; resuming the same run requires the recorded values. Defaults reproduce the original rules. Rollout workers
and episode replay use the run's recorded rules, including for old runs whose rewards predate these settings.

Checkpoint selection keeps its original fixed reward weights as a comparable evaluation benchmark. Changing training
rewards changes what PPO learns, while catches, ship hits, kills and deaths retain the same selection weights. This
also allows a zero catch reward without changing score normalization.

The spread and bunching charts, and scripted promotion baselines, retain their original benchmark geometry
(200 px flank range and 40 px bunch distance). Configured distances govern paid shaping; keeping measurement
geometry fixed makes training progress comparable across reward experiments.
