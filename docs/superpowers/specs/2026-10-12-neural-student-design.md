# Neural student: a basic-controls pilot, taught by the rules pilot

## Goal and context

The Jev-imitating student is replaced by a student that flies the hunter with only the basic controls the
player has: turn left, turn right, thrust or coast, and the trigger. It has none of the special commands
(`track`, `course`, `burn`, `pulse`). It first imitates the rules pilot (`hunter/rules_pilot.py`), which is now
good enough to teach. A later stage drops the teacher and keeps improving the student with the game's own
feedback (kills, collisions, idling); that stage is **out of scope here** and gets its own spec. This spec covers
two stages:

1. A student that can be flown and measured: per-frame environment, cheap senses, a recurrent policy, a
   controller the game can run, and the lab flying and scoring it.
2. Imitation of the rules pilot, including teacher-corrected rounds, until the student meets the gate below.

Stage 3 (reinforcement learning from the lab score's terms) is why some choices below are made now: the policy
outputs probabilities, the lab has a step loop, and episodes stay fast.

## Decisions already made (with the reason)

- **Controls:** per-step `PilotAction(turn in {-1,0,+1}, thrust, fire)` with `track`, `course` and the burn
  fields empty. The trigger is the plain trigger the player has; the ship's own aim gate (a shot leaves only
  while the nose is on target) stays in the ship for every pilot.
- **Inputs:** raw senses plus plain geometry (bearing, distance, relative velocity), and none of the solved
  quantities the rules pilot is handed (lead angles, burn headings, safe speed, stopping distance).
- **Memory:** a recurrent network (one GRU layer). Its per-step input is the senses plus the student's own last
  controls, so its memory only carries what matters over time. The history encoding sits behind an interface so
  running averages or lagged snapshots can be compared if the GRU disappoints.
- **Decision rate:** a setting, `decisionFrames`, default 6 (10 Hz). The rules pilot decides at 4 Hz, the trigger's
  aim gate runs every frame regardless, and a lower rate halves sensing cost and shortens sequences. Coarser
  steps make steering coarser, so stage 2 compares 3, 6 and 1.
- **Teaching:** plain imitation, then teacher-corrected rounds (DAgger). The teacher is free to ask.
- **Gate:** closed-loop, not agreement. See "The gate".
- **Old student:** removed entirely, including the Jev recorder. Jev itself stays as `hunterPilot: "jev"`,
  because the rules pilot is built on `JevPilot` (course and braking helpers).

## Components

**`hunter/senses.py`** builds the input vector for one step directly from the game objects, without the
perception JSON, which costs about 13 ms a call (measured: 13.4 ms for the perception plus 1.4 ms for the
helper calculations, on a busy level) and would make a 10 Hz episode far slower. Target: under 1 ms a call.
Layout (initial; the plan fixes exact counts):
- own motion: velocity along and across the nose, speed share, absolute heading (sin, cos), health share,
  gun cooldown share, burst remaining, upgrade level;
- walls: 16 rays at 22.5 degrees, relative to the nose, as distance over sensor range, from the maze's wall
  spatial grid;
- the nearest 6 visible enemies, nearest 4 enemy bullets, nearest 2 powerups: bearing (sin, cos), distance over
  sensor range, relative velocity along and across the nose, with presence flags;
- the player when visible: the same geometry, with a visible flag;
- a small memory of enemies seen lately but out of sight (the nearest 2: bearing, distance, age), kept in the
  senses object and reset each level, like the perception's 10-second memory;
- one flag, `enemies_present`: whether any enemy is alive anywhere (the rules pilot's hunt-first rule uses it);
- the student's own last controls (turn one-hot, thrust, fire).
No lead angle, burn heading, safe speed, stopping distance or course appears anywhere.

**`hunter/neural/`**: the policy (embedding layer, one GRU of 128 units, three heads: turn 3-way, thrust 2-way,
fire 2-way), its numpy forward pass (no torch at runtime), `.npz` weight loading and saving, and a check that
the weights match the senses layout. The history encoder interface lives here. The policy can act greedily or
sample; sampling is unused until stage 3.

**`NeuralController`**: the same interface the game already uses for `HunterController` (`tick`, `status`,
`action`, `close`, `invalidate`). It decides every `decisionFrames` frames and holds the controls between,
returns a plain `PilotAction`, and resets its recurrent memory and senses memory at each level start. It calls
no worker and no network.

**Game wiring:** `hunterPilot: "neural"` builds a `NeuralController` in `_summon_hunter`; `_update_hunter` gains
one branch that passes it a senses builder instead of the perception-JSON builder. The ship stepping, fire control
and everything after are unchanged. `hunter_settings_for('neural')` gives the neural pilot its own hunter
settings (turn rate and decision rate are tuned independently of the rules pilot's 2.0). A missing or
mismatched weights file leaves the hunter coasting and unavailable; there is no fallback to another pilot.

**Teaching recorder** (`experiments/teach.py`): runs the rules pilot in the lab and records, per decision step of
N frames, the senses and the controls the ship actually executed over those frames. Labels come from physics, so
the translation of the special commands cannot disagree with what they did:
- turn: left or right by which way the nose rotated more over the step (none if it barely moved);
- thrust: on if the engine fired in at least half the frames;
- fire: on if the trigger was held or a shot left in any frame.

**Teacher relabelling (for the corrected rounds):** a shadow copy of the rules pilot (its own perception, memory
and decisions) watches the game while the student flies. At each student step, its current action is tried on a
clone of the ship for N frames, and the controls the clone executes are the label for the state the student
actually reached. The labels use the same translation as the recorder.

**`tools/train_neural.py`** (torch, training only): trains on windows of 64 consecutive steps, the first 16 as
memory warm-up that is not scored, with cross-entropy summed over the three heads, Adam, gradient clipping, and
episode-level splits (never rows). Exports the `.npz`. Continues from earlier weights for the corrected rounds.

**Lab changes:** `run_episode` can fly the rules pilot (as now) or a neural policy, scored identically (the
score terms, weights and conditions are unchanged). The student plays greedily for evaluation.

## Data

- Teaching set: the rules pilot on the 12 tune levels, 40 seeds each (seeds 100 to 139, disjoint from the
  evaluation seeds 0 to 17), 90 s episodes. At 6 frames a step that is about 650,000 steps of about 110 numbers.
- Held-out levels and the evaluation seeds are never used for training or corrected rounds.
- Raw data lives under `.astrovoid-local/neural/` (not committed). The trained weights are committed under
  `assets/neural/`.

## The gate

Stage 2 is done when the student, flown greedily on the held-out levels (18 seeds, as `lab compare` uses), has:
- a lab score within 20% of the rules pilot's score on the same levels and seeds; and
- wall hits per minute and enemy hits per minute each no more than 1.25 times the rules pilot's.

Per-step agreement with the teacher is reported as a diagnostic only. The corrected rounds run until the gate is
met or five rounds pass; if five rounds do not meet it, that is a finding to report, not a reason to loosen it.

## Experiment order

1. Turn rate: 0.5, 1.0, 2.0 at 6 frames a step.
2. Decision rate: 6 against 3 and 1 frame(s) at the best turn rate.
3. History: the GRU against running averages, only if the GRU falls short of the gate.

Each is a lab comparison on the student, with the notebook entries in `docs/experiments/` as before.

## Removed

The Jev-imitating student: `hunter/student/` (client, network, encoder, recorder), `tools/train_student.py`,
`assets/student/`, `requirements-train.txt` entries only it needed, the `student` and `auto` modes,
`game.recordPilotDecisions`, and their tests and README sections. Autoplay stays without its recording hook;
the rules lab and Jev stay.

## Testing

- Senses: fixed length, finite, respond to the hunter's surroundings, and contain no solved quantity.
- Labels: hand-built action sequences translate as stated (a `course` turn becomes the left or right the ship
  performed; a `burn` becomes thrust only while the engine fired).
- The numpy GRU matches the torch one it was trained as.
- Relabelling by cloning the ship matches reality: when the teacher actually flies, the clone's controls equal
  what the ship did.
- `NeuralController`: holds controls for N frames, resets memory per level, coasts when the weights are bad.
- Determinism: the same student episode twice is identical; the lab's existing determinism tests still pass.
- Training smoke test: a tiny dataset is overfit, and the exported weights load and fly.
- The full existing suite stays green after the removals.

## Out of scope

Reinforcement learning (stage 3); retuning the rules pilot; Jev's behaviour; a moving-player lab scenario (the
rules pilot's follow-the-player branch is still unmeasured); changing the ship's aim gate.

## Risks

- Aiming at coarse steps: the sweep addresses it, and the trigger's per-frame gate softens it.
- The cheap senses may not reach 1 ms; if not, the rate and ray count are the knobs.
- The shadow teacher's memory and timing belong to a path it did not choose when the student is flying. The
  relabelling test checks consistency, and a corrected round that does not improve the score is a signal.
- Sequence training is slower and fiddlier than a plain network.
