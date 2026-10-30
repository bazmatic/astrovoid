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
`budget_seconds`, `bootstrap_episodes` and `seed`. From the command line:

```
python -m tools.ppo_neural --task jelly_team --start '' --out <run dir> --bootstrap-episodes 0 --budget-seconds 3600
```

The command-line default for `--bootstrap-episodes` is 8, so pass `0` explicitly there. Replays work like the
crawler's: `learning.replay` through `learning/adapters/jelly_replay.py`.

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

A checkpoint that fails the gate never becomes `best.npz`. If no checkpoint ever passes, `best.npz` stays the
policy saved when the run started (the bootstrap policy, which is the random initial policy when bootstrap is off).

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
- **The scripted teacher is weak.** On `evaluation_cases(1)` at a 60 s horizon, the teacher
  (`learning.adapters.jelly.teacher`) catches 0.50 per minute, against 4.17 for the scripted `aggressive` Jelly.
  It heads straight for the target and brakes when a wall is in the way, and then waits behind the wall until the
  target comes into line.
- **Imitation bootstrap is not recommended** until the teacher improves. That is why `bootstrap_episodes`
  defaults to 0 for `jelly_team`.
- **The training ship's pilot misreads its health.** It reads its own health against the neural hunter's 10
  points, so on its 3-point hull a fresh ship feels like 30% health. It still hunts and kills, but it may fly
  more cautiously than a full-health hunter would.
- **Validation is small.** Nine episodes with one seed make the gate noisy for any single checkpoint. The final
  evaluation is on separate seeds of the same held-out arenas, so it is independent of the seeds selection saw,
  but not of the arenas.
