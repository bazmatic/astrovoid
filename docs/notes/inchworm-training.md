# Neural inchworm: implemented controller and planned training

## Checkpoint selection after the About-face corrections

As of 4 November 2026, exclude **run210–run222** from future warm starts at the
user's request. Keep their files as historical evidence; this is a selection
decision, not a claim that every checkpoint is irreparably damaged. The trainer
does not enforce this exclusion automatically: pass an explicit source checkpoint.

Use **run209/iter0222.npz** as the next transfer baseline. Run209 predates the
About-face lesson (its curriculum was 1 → 6 → 7 → 2 → 3 → 4 → 5). Runs 210–220
branched from this checkpoint, then run221 continued run220 and run222 continued
run221. Rolling back to run209 avoids inheriting those About-face experiments.
It is not certified under scenario 26: start a new run with fresh optimizer and
critic state and recheck the curriculum gates with automatic front attachment,
the upfront movement allowance and head-based About-face arrival.

Run222 was already recorded as stopped at iteration 121 when this decision was
made. No checkpoints were deleted and no replacement run was launched.

The user subsequently approved the clean restart: **run223** started on
4 November 2026 from **run209/iter0222**, using scenario 26, 10 workers,
120-second episodes and a fresh two-hour budget. It retains the current
80-demonstration rehearsal, turn reward 3 and DAgger weight 1. Policy weights
transfer without initial cloning over them; optimizer, critic and curriculum
validation start fresh. Runs 210–222 supply no weights to run223.

Training started on **3 November 2026** as **run197**, after Flocker run196
finished. The run uses [config/training/inchworm.json](../../config/training/inchworm.json),
with its output directory assigned by the trainer to
`.astrovoid-local/neural/rl/run197`. A trained checkpoint is bundled for gameplay (see "Bundled brain" below).

## Controls and inference

The policy is the existing NumPy-deployable recurrent model: a 32-unit tanh
embedding and 64-unit GRU. The task/schema is `inchworm`, version 1. It reads 83
body-relative features every six game frames (10 decisions/second):

- Five bend angles, joint rates, and actual muscle activations.
- Six link roll postures, velocity, angular velocity, actual grips and loads,
  environmental contact, grasp state, muscle effort, bite charge, and stun time.
- The previous eight applied motor commands.
- Eight wall rays from each end and the nearest surface distance/normal at each end.
- A visible adversary's relative position, velocity and radius, plus a navigation
  goal. Training locomotion goals are visible markers; ordinary gameplay uses the
  visible adversary as its goal. Occluded targets supply no privileged position.

Outputs are five independent Gaussian pre-tanh bend commands, two binary grip
requests, and one binary bite request. Every motor passes through the existing
force/torque limits, actuator lag, contact checks and breakable constraints. Even
an all-zero externally supplied command overrides both policy and scripted control;
the physical contact and twist reflexes still operate.
Each creature owns separate recurrent memory and a random sampling stream; an
encounter shares loaded weights. Gameplay and validation both read the shared
`INFERENCE_ACTION_MODE` setting. They sample the learned action distribution,
as training does; greedy mean/argmax inference had suppressed successful
behaviour. Explicit seeds reproduce actions, and recorded-action replays remain
exact.

Twisting is automatic. The worm curls while the rear is planted, rolls its free
front to put its legs against the surface, plants those feet, then unfolds in the
opposite direction. The twist reflex gradually changes the projected belly
orientation without supplying planar momentum. It is a torsional posture
approximation, not full 3-D rigid-body physics. The policy learns the five bends
and grip timing; there is no twist action or hidden turn-around macro in its
outputs. The scripted demonstration controller does supply an explicit motor
sequence for this maneuver.

`INCHWORM_POLICY=/absolute/path/to/checkpoint.npz START_LEVEL=33 ./run.sh` selects
weights later. With no variable, the game looks for `assets/neural/inchworm.npz`.
An empty variable selects the reflex controller. Invalid selected weights log a
warning and fall back. Loading rejects other tasks, schema changes and nonfinite
normalization. Gameplay inference does not import Torch.

## Longer crawl curriculum (run198)

Scenario version 2 extends crawl goals to 180–300 px (roughly 3–5 body
lengths). Training crawl episodes retain a 25% chance of a short 60–90 px
drill; all held-out crawl cases use the longer distance. The episode limit
is now 120 seconds. The existing 700 px surfaces provide room for these goals.

Run197 used version 1 and its short crawl lesson; its results do not certify
long-distance crawling. Its saved rules are unchanged. Start a new run from
its checkpoint to learn these changed rules, beginning again with the crawl
gate. Do not resume run197 against version 2: strict rule checks will reject it.
Run198 started on 3 November 2026 from run197/iter0368 with 10 workers,
a 120-second horizon, and a new two-hour budget. It skips demonstration
bootstrapping and starts at the crawl gate with the transferred policy; optimizer
and critic state start fresh for the changed curriculum.

The iteration-369 stall was reproduced from recorded actions: adaptive physics
steps left a tiny final remainder, followed by a large timestep jump. Evenly
partitioning the remaining time fixes the recorded failure. A finite substep
budget now raises an explicit error on runaway physics instead of hanging.
All 18 turning rollouts from the blocked batch completed with the fix; a
recorded-action regression and the inchworm tests also pass.

## Original first run

| Setting | Planned value |
| --- | --- |
| Learner | Existing recurrent PPO with mixed continuous/discrete heads |
| Bootstrap | 40 reflex demonstrations, balanced across all five lessons |
| Imitation passes | 4, all eight motor heads |
| Episodes per PPO iteration | 24 |
| Episode time limit | 45 seconds |
| Workers | 4 |
| Learning rate | 0.0001 |
| Discount / GAE lambda | 0.997 / 0.97 |
| Iteration ceiling | 5,000 |
| Initial wall-clock budget | 7,200 seconds, including evaluation |
| Seed | 0 |

This is an initial budget, not a prediction of convergence. The two-hour budget
will normally stop the run before the iteration ceiling. A timeout preserves
completed checkpoints and reports incomplete evaluation; it is not a passing
result. Run197 begins with demonstrations and then PPO training.

The task appears as **Inchworm** in the trainer. Its current fresh defaults
and saved settings use the longer 120-second episode limit. It needs no frozen Hunter opponent: the first curriculum teaches
body control and feeding on physically movable targets, not combat against an
armed ship. The shared trainer skips opponent copying for this task.

The original equivalent standalone CLI recipe is:

```sh
venv/bin/python -m tools.ppo_neural --task inchworm \
  --out .astrovoid-local/neural/inchworm-pilot \
  --seed 0 --workers 4 --episodes 24 --horizon 45 \
  --iterations 5000 --budget-seconds 7200 \
  --bootstrap-episodes 40 --bootstrap-epochs 4 \
  --lr 0.0001 --gamma 0.997 --gae-lambda 0.97
```

The JSON is a settings recipe, not an auto-running job. Run197 was launched
through the trainer with these settings and a trainer-assigned output directory. To continue a run later, use its recorded settings and
`--resume --out RUN`; resume validates schemas, reward settings and physical rules.

## Simplified overhead success (run201)

Run201 started on 4 November 2026 from run200/iter0124 with scenario version 5,
10 workers, and the existing 120-second horizon. It transfers learned policy
weights and starts a fresh optimizer/critic, rechecking crawl before Rear.
Run200 is archived at its last completed checkpoint.

## Consistent action selection (run202)

Run202 starts from run201/iter0080 under scenario version 6 with 10 workers.
Training, gameplay and validation now sample the same policy distribution;
gameplay and evaluation share one inference-mode declaration. Validation seeds,
placements, survival requirement and two-pass gate are unchanged. With checkpoint
run201/iter0050, sampled inference passed 12/12 rearing validation cases, versus
0/12 under greedy inference. Paired cardinal/rotated cases gave effectively
identical outcomes, isolating action selection rather than rotation as the cause.
No checkpoint has been installed into gameplay automatically.

## Curl with a retained starting anchor (run203)

Run203 starts from run202/iter0035 under scenario version 7, retaining 10 workers
and the 120-second horizon. Policy weights transfer; optimizer and critic start
fresh and earlier lesson gates are rechecked. All 12 scripted curl validation
cases reached the marker while retaining their original rear anchor.

## Curriculum and pass criteria

Run200 started from run199/iter0052 with the seven-lesson curriculum, 10 workers,
120-second episodes, no demonstration bootstrap, and a two-hour budget. It
transfers policy weights, starts a fresh optimizer/critic, and rechecks crawl
validation before progressing to Rear and Curl. Run199 is archived.

| Lesson (stage ID) | Physical objective | Held-out success gate |
| --- | --- | --- |
| Crawl (1) | Reach a marker 180–300 px ahead; short practice retained | 80% |
| Rear (6) | Bring the mouth within 12 px of an overhead marker once | 80% |
| Curl (7) | Mouth within 12 px of a marker above/behind the starting rear grip, retaining that grip | 80% |
| Turn (2) | Bring the mouth within 25 px of a target 12–58 px from the worm's first joint (its turning pivot), on an arc from straight behind up to 80° above the surface, weighted toward low targets | 80% |
| About-face (8) | Reach a marker placed 45–200 px behind the initial body centre, weighted toward near targets; head within 14 px while either end has a planted grip | 80% |
| Reach (3) | Maintain actual mouth contact with elevated prey and rear support | 80% |
| Feed (4) | Deliver two health-reducing bites | 75% |
| Recover (5) | Regain support after a shove and deliver two subsequent bites | 65% |

Scenario version 4 adds Rear and Curl before Turn. IDs remain stable for old
recordings; curriculum order is 1 → 6 → 7 → 2 → 8 → 3 → 4 → 5 (About-face, ID 8, follows Turn). Scenario version 5 simplifies Rear: the mouth need only come within 12 px of
its fixed overhead marker for one frame. It has no grip, head-height or hold-time
requirement. Scenario version 7 simplifies Curl to mouth proximity within 12 px once,
while continuously retaining its original rear grip. One ordinary physics frame
plants the rear foot at setup. Releasing, slipping free, or replacing that grip
ends the attempt unsuccessfully; replanting even at the same point cannot pass.
There are no separate head-height, head-direction, or hold-time checks. Positive
progress on the anchor-loss frame earns no reward. The replay marks the starting
anchor and reports whether it was retained; the target ring matches the threshold. Markers do not move or supply physical forces. Rear targets
are 22–28 px forward and 28–36 px outward from the initial tail; Curl targets
are 4–10 px behind and 20–28 px outward. All coordinates rotate with the surface.

Rear and Curl reward signed mouth-to-marker progress without a facing multiplier:
these lessons teach bending while supported, not walking. The head-first rule is
retained for locomotion. The demonstration controller uses bounded joint
setpoints and the same muscles/grips, never pose changes or teleports. All 24
held-out Rear/Curl demonstration cases completed successfully in physical checks.

The environment uses real Creature/Encounter traits and the same articulated
solver as play. No stage teleports feet or prey. Stage 5's target receives small
physical evasive/restoring accelerations and the worm receives a real impulse.
Success is measured from physical pose, contacts and accepted damage.

Training surfaces rotate through four cardinal orientations. Validation uses
four different diagonal orientations and 12 fixed cases per lesson. Promotion
requires two consecutive passing validation blocks, with full survival. Validation
runs every five iterations. Each later training stage retains earlier drills in
one-quarter of its episodes to limit forgetting. Seed sets are separate for
training, validation, bootstrap and final evaluation. These are held-out seeds
and placements within the same drill, not held-out skills. Rotating a body-relative
setup is primarily an invariance check. Passing this gate establishes repeatable
performance on these target variations, not broad generalisation.

Final evaluation uses another four held-out orientations, 12 cases per lesson (84 total),
and paired reflex baselines. A deployment pass requires every lesson's success
gate and a paired 95% bootstrap lower bound of at least -0.05 for success-rate
change versus the reflex controller. An incomplete comparison fails. No result
automatically installs a policy; the report records the evaluated checkpoint hash.
An early-stage best checkpoint is not deployment approval.

## Head-first reward run (run199)

Run199 starts from run198/iter0279 under scenario version 3, with 10 workers
and 120-second episodes. Run198 was paused at a saved boundary and archived.
The policy weights transfer; optimizer and critic start fresh and the crawl
gate is checked again under the new reward. Demonstration bootstrap is disabled.

## Motion rewards (run204)

Run204 starts from run203/iter0024 under scenario version 8 with 10 workers.
All lessons penalise tail-first travel at 0.04 per pixel, measuring the rear
segment along the surface against the pre-frame body facing. Movement about a
continuously retained rear anchor is exempt, as is forced stun motion; facing
within 0.2 of perpendicular to the surface is treated as ambiguous. This avoids
penalising the head swinging back during a supported curl. The dashboard exposes
backward distance. Success gates are unchanged.

## About-face turn reward (run211)

Run210 froze in About-face: it won none of 360 episodes, kept both grips planted
throughout and ended each episode where it started. Facing away from the goal,
head-first progress pays nothing, crawling away is charged in full and nothing
rewards turning, so staying still was the best policy. Scenario version 14 adds
`turn_reward`, a potential-based signed reward for facing the goal (stage 8 only).

## Reward accounting

| Signal | Coefficient / units |
| --- | --- |
| Head-first reduction in goal or mouth-to-target distance | +0.04 per pixel × positive facing alignment; increases in distance subtract the full 0.04 per pixel |
| Actual bite damage | +2 per accepted bite |
| Lesson success | +4 once, then terminate |
| Death | -5 once, then terminate |
| Tail-first travel of the body centre | −0.04 per pixel beyond 30 px of forward credit, excluding anchored bends and stun |
| About-face turning | +3 × change in (facing the goal, clamped at 0) × (head-to-tail distance ÷ straight length); stage 8 only, potential-based, so swinging back and forth nets zero |
| Mean muscle effort | -0.03 per second at full effort |
| No planted grip | -0.08 per second, excluding forced stun |
| Elapsed time | -0.002 per second |
| Motor-command change | -0.01 times mean squared change per decision |

Scenario version 3 gates positive progress each physics frame by the clamped
dot product of the tail-to-head direction and the direction to the target,
measured before movement. Direct head-first approach earns full progress reward;
sideways or backward approach earns none. Moving away always pays the full
penalty. Turning in place earns no progress reward. Because positive progress
is at most the distance gained and retreat is charged in full, a closed
distance cycle cannot earn positive progress reward. Regripping does not reset it. Holding alone earns nothing; feeding rewards require real
health loss. Lessons terminate on success/death and truncate at the horizon;
truncations preserve the final critic observation for value bootstrapping.

## Replay and inspection

Each run records its policy schema, Pymunk version, physical implementation hashes,
creature tuning, arena definitions and reward coefficients. Incompatible replays
and resumes fail explicitly. The watcher replays recorded actions, not freshly
sampled decisions:

```sh
venv/bin/python -m tools.watch_episode RUN ITERATION --check
```

The dashboard exposes success, goal distance, bites, effort, detached time,
recovery and survival. No communication ablation is performed for this single
agent. The actor and critic use the same local observation; the critic does not
receive hidden target locations.

The initial lessons use long flat surfaces at varied orientations. Cave routing,
complex corners, moving gates and armed-opponent combat need subsequent lessons
and playtests before deployment should be considered general-purpose.

## Spine coupling (run212)

Each bend muscle is a damped spring toward its commanded angle, but nothing
tied neighbouring joints together, so five unrelated commands produced kinks.
Scenario version 15 adds a weak coupling spring (`SPINE_COUPLING = 0.2` of the
muscle spring's stiffness) pulling each joint toward the mean of its
neighbours, so a bend spreads into an arc. The scripted gait slows (Crawl takes
about 60 s rather than 48 s) and fails at 1.5, so the strength stays low.

## Demonstration rehearsal (run213)

Runs 210 and 212 froze in About-face with both grips planted and won none of
about 1,000 episodes, although the scripted controller wins every one. The
40 scripted demonstrations cloned at the start were forgotten by the time the
curriculum reached About-face. Scenario version 16 doubles them to 80 (ten per
lesson) and rehearses them during PPO with weight 0.2, so the policy keeps
seeing the turn and the grip release it needs.

Run215 still froze after rehearsal, so scenario version 17 samples About-face
goals 45–200 px behind, weighted toward the near end (distance = 45 + 155·u²,
half under about 84 px). A near goal can be won by an early partial turn, which
gives the policy a success to learn from before the far goals matter.

## Rolled worm mirrors its bends (run217)

After a turn the twist reflex rolls the links to π and the worm walks belly-down
in the new direction. A rolled worm arches with the opposite bend sign (the
scripted controller negates its commands by roll). The policy had never acted
in that state, because Turn ends when the head arrives, before the body has
flipped. Scenario version 18 mirrors the five bends by the sign of the cosine
of each joint's mean roll, both in what the policy observes (angles, rates,
activations, previous command) and in what it commands. With the body
unflipped every sign is +1, so existing checkpoints behave identically; a
turned-around worm looks like one that has not turned, and the crawl it knows
carries over. The side-related inputs (side velocity, goal side, rays) are not
mirrored.

## About-face turn needs the body unfolded (run218)

Run217's policy swung its head over the goal (facing it, links rolled to π),
then unfolded back the way it came and froze at its starting distance in all
12 traced episodes. The facing-only turn reward paid the full amount for the
folded swing, which is only half a turn. Scenario version 19 multiplies the
facing term by the body's extension (head-to-tail distance over its straight
length) and raises `turn_reward` to 3, so the reward is complete only once the
worm has unfolded facing the goal.

## About-face learns from the scripted turn in the states it visits (run219)

Run218's reward changes left About-face at about 1% (7 successes in ~970
episodes): the policy swings its head over the goal, unfolds back and freezes,
and never tries the release-rear-and-unfold half. Scenario version 20 turns on
the trainer's DAgger loss for About-face. While the policy flies its own
episodes the scripted controller (`label_action`, stage 8 only) is asked what it
would do in every state reached, and the policy is pulled toward those answers
with weight `dagger_weight` (1.0): mean-squared error on the five bend means,
cross-entropy on the two grips and the bite. The loss previously treated every
head as continuous; discrete heads now use cross-entropy, masked to legal
actions. The scripted controller is a phase machine driven by its own timer and
the worm's grips, so its answer follows the script's schedule, not the policy's
posture exactly.

## About-face labels come from the posture, not a timer (run220)

Run219's labels were wrong for a stalled learner: `teacher_action` advances the
scripted controller's timer by six frames per decision whether or not the
learner did the previous step, so after ten idle seconds it was already
crawling away facing the wrong direction (see `docs/about-face-diagnosis.md`).
Scenario version 21 labels About-face with `posture_expert`, which decides from
the state alone: plant the rear; curl with the front free; land the head; once
the head is planted facing the goal, release the rear and unfold; once
stretched out facing the goal, crawl. It wins 12/12 from a fresh start, and
12/12 after sitting idle 10 s or 25 s; the timed controller fails the stalled
cases. Letting go of both grips for 3 s mid-turn flings the worm away and wins
6/12 (the rest drift off). The timed controller still makes the demonstration
episodes and the scripted baseline.

## Backward walking is net travel, not gait swing (run221)

The backward penalty summed every physics frame in which the rear link moved
against the facing direction. A normal stride swings the tail back each step, so
the scripted expert, which walks forward, was charged 7–9 reward units for
183–228 px of "backward" walking in About-face and netted only about +3. The
metric also broke the learned flipped-posture gait. Scenario version 23 measures
the body centre's travel per decision, and forward travel earns up to 30 px of
credit against later retreat (`BACKWARD_SLACK`), so the swing-back inside an
advancing gait is free and walking tail-first still pays after the credit is
used. The expert's About-face charge drops from 209 px (−8.35) to 12 px (−0.48).
The anchored-rear and stun exemptions are unchanged.

## Initial gait allowance (scenario version 24)

Episodes now start with the full 30 px backward-motion allowance instead of
requiring forward travel to earn it first. This protects the initial contractions
after an about-face. Forward travel replenishes credit up to the same 30 px cap;
turning and regripping do not reset it. Sustained tail-first travel beyond the
allowance still pays the existing penalty. The manifest records both the initial
credit and its cap, and correctly names the body-centre measurement.

The reproduced scripted about-face previously accumulated 19.17 px of backward
charges, including 8.62 px during its first two crawl strides. It now succeeds
without backward charges. Regression tests also verify that 48 px of sustained
retreat pays for 18 px in either facing direction, and that forward travel
replenishes spent credit. All 63 inchworm learning tests pass.

This changes training rules: use a new run with transferred policy weights for
version 24, rather than resuming a version 23 run. The existing running job was
not restarted by this change.

Run222 subsequently started from run221/iter0144 on 4 November 2026 at the user's
request. Run221 was already paused and is now stopped with its checkpoints
preserved. Run222 uses scenario version 24, 10 workers, 120-second episodes and
a fresh two-hour budget, retaining the other run221 settings. Policy weights
transfer; optimizer/critic state and curriculum gates start fresh.

## Automatic front attachment (scenario version 25)

After the head moves clear, returning within valid surface-grip or prey-grab
reach automatically attaches the front without a policy grip request. The
existing orientation checks, breakable forces, cooldowns, and prey eligibility
still apply. Contact holds until deliberately released or physically broken.
The rear grip remains request-controlled.

The policy releases the front by switching its front-grip request from on to
off. A continuously off request no longer prevents a new landing from gripping
or releases a reflex grip immediately afterward. To release such a grip, request
on and then off. A deliberate release inhibits automatic attachment until the
head moves clear again; an explicit on request can still reattach sooner.
The reflex starts unarmed so a worm spawned resting beside a surface can lift
its head for Rear/Curl, and is disabled during stun. No geometry or reach limits
were loosened. The eight-output checkpoint schema is retained, but these changed
motor semantics require a new versioned training run and revalidation.

Validation: all 99 inchworm physics, creature, learning and level tests pass
(the game-loop test uses SDL's dummy video/audio drivers). All 12 scripted
held-out about-face cases still succeed with zero backward-motion charges.
The current training process has not been restarted with version 25.

## Head arrival for About-face (scenario version 26)

About-face now measures both distance progress and arrival from the head to the
marker. Success requires head distance strictly less than 14 px and an actual
planted front or rear grip in the same physics frame. No hold duration, facing
threshold or full-extension requirement is added. The success bonus remains +4;
goal placements and the other lessons are unchanged. Head-first progress alignment
also uses the direction from the head to the goal. Turn shaping still measures
body facing and extension.

The replay draws a 14 px target ring and explicitly reports the head-distance
requirement and whether a grip is planted. Old runs retain their recorded rules;
using these changed rules requires a new training run. The running trainer has
not been restarted as part of this change.

## The surface stays on the belly side after the turn (scenario version 27)

Run221 turned around (facing the goal, links rolled to π, body extended) and
then dithered in place. The body frame the policy sees is a rotation by the
heading, so after the turn the surface appeared on the opposite side to every
crawl it had learned: surface normal, side velocity, angular velocity, goal
side, and the ray sensors all swapped. Scenario version 27 mirrors those inputs
by the same roll sign as the bends. Run223 started before this change and so
trains on the unmirrored inputs. With the run221/iter0144 policy and no
training under the new inputs, success on fresh About-face goals went from 0%
to 83% (50–100 px), 11% to 25% (100–150 px) and 0% to 50% (150–200 px), over 48
episodes.

## Phase-balanced teacher loss; no near About-face goals (scenario version 28)

Run224's teacher loss was a plain average over every decision and over all eight
outputs. In the state that matters (head planted, still curled, rear still
gripped) the rear-grip loss was 4.1, but those states are under 1% of decisions,
so the average rear-grip loss was 0.16 and the release was barely taught. The
expert now labels each decision with its phase (plant, curl, land, release,
crawl) as a ninth label value, and the update weights every phase present
equally. Labels without a phase (Jelly, Wallcrawler) are one phase, so they keep
the plain mean.

About-face goals are now 90–200 px behind the centre, uniformly. Measured with
the scripted turn, the head gets within the 14 px arrival radius of a goal up to
about 65 px behind the centre by curling back alone (60 px: 9 px; 70 px: 17 px),
so closer goals never needed the rear released. From 90 px the best a curl
reaches is about 36 px short. This replaces the 45–200 px near-weighted
distribution of scenario version 17.

## Longer Crawl practice (scenario version 30)

Run229 left Crawl after 26 iterations at 80% success with 9% of its time airborne: the gate only measured arrival, so a lurching gait passed. Crawl now passes at 95% success with at most 3% airborne, for 5 consecutive held-out blocks instead of 2 (`PASSES_REQUIRED`, `CRAWL_MAX_AIRBORNE`). Later gates are unchanged.

## Fast Crawl (scenario version 31)

Crawl now also pays for speed. On arrival it adds `speed_bonus` (4.0) × the fraction of the time limit still left, so a crawl that arrives in a quarter of the time earns about 3 extra instead of about 1. The Crawl gate additionally needs a mean time to the goal of at most 80 s over the held-out goals (`CRAWL_MAX_SECONDS`); the scripted crawl averages 72.5 s (max 93 s) on them. Validation summaries now carry mean `seconds`.

## Crawl time penalty (scenario version 32)

The base `time_cost` (0.002/s) was negligible next to the 4.0 success reward, so dawdling was nearly free. Crawl now also pays `crawl_time_cost` (0.05/s) every second it takes: about 3.6 over a 72 s crawl and 6 over the full 120 s limit, so a slow or stalled crawl ends well below a quick one. Other lessons keep only the base cost.

## Why Crawl did not pass, grip snap, and a looser airborne cap (scenario version 33)

Run232 (warm start from run231/iter0185 with the 0.05/s Crawl time penalty) never passed the Crawl gate (23 validation passes in 243 blocks, never 5 in a row). Speed was not the reason: on the 12 held-out Crawl goals, mean time to the goal was 15.5 s at run231/iter0185, 6.6 s at run232/iter0600 and 4.7 s at iter1200, against an 80 s limit, all at 100% success. Detached time was: 1.6% → 5.7% → 10% → 25%. The penalty for slowness taught the policy to leap rather than walk, and the 3% airborne cap blocked the gate.

Changes: a foot asking to grip (rear or front grip request; the front reflex alone does not pull) is pulled toward a surface up to 2.5 reaches away, peak 0.2 × mass, falling off linearly with distance (`SNAP_RANGE`, `SNAP_PULL` in `physics/inchworm.py`); the grip itself still needs reach and posture. The Crawl airborne cap is relaxed significantly (`CRAWL_MAX_AIRBORNE`).

## Leaping allowed (scenario version 36)

Run235 (uneven ground, snap pull, 0.05/s Crawl time penalty) stayed at 25–32% airborne and at ~3 s per held-out crawl for 757 iterations and never passed the 8% cap. Leaping is now accepted: the Crawl airborne cap is 50% (`CRAWL_MAX_AIRBORNE`), which only rejects a crawl that is mostly in the air.

## About-face time penalty (scenario version 37)

About-face only had the negligible base `time_cost` (0.002/s). It now also pays `about_face_time_cost` (0.05/s, the same as Crawl), so a stalled or dawdling turn loses reward every second instead of only failing at the time limit.

## Scripted turn no longer idles after unfolding

The timed controller held its unfold phase for a fixed 240 frames (4 s) before it began walking, even once the body was straight. It now moves on as soon as every joint is within 0.35 rad of straight (and at least 20 frames have passed; 240 stays as the fallback). In scripted About-face the time from "turned" (facing the goal, stretched out, rear free) to the first 10 px of progress fell from 58 to 22 decisions. The posture expert that labels About-face during training never had this hold: its 49 decisions are two ordinary crawl strides (about 8 px each, so the 10 px mark falls in the second), which is the gait's speed (`stride_frames`=160), not idling.

## The expert stops teaching once the worm has flipped (scenario version 38)

During About-face training the posture expert used to label every state, including the crawl after the turn, and its gait is slow (about 4 px/s: a 160-frame stride advancing about 8 px). Those labels pulled the policy toward that slow walk even though it learns a much faster one in the Crawl lesson. `label_action` now returns no label in the `crawl` phase, i.e. once the worm faces the goal stretched out; only plant, curl, land and release are taught. The policy's own reward (progress, speed bonus, About-face time penalty) shapes the walk.

## Only the rear foot is taught after the flip (scenario version 39)

With no label after the flip, the release label ("front planted, facing the goal: rear foot off") was the only one left in that region, and run240 generalised it: in the first 150 decisions after the flip its rear-grip request averaged 0.06 (0.32 in run237/iter0055, which was taught the walk) and it moved at 0.5 px/s (12 px/s). Now, once the worm faces the goal stretched out, the expert labels only `rear_grip = on`, and only until the rear foot has landed once after having been let go. Every other head, and every later decision, is untaught, so the walk is the policy's own. A label may hold NaN for a head it does not teach (`update_team` skips those heads).

## An inchworm stride, deeper joints (scenario version 41)

The timed scripted stride (held phases, a gentle arch that never brought the feet together, a wobbling rear foot) is replaced by the five steps of an inchworm, each triggered by the worm's posture instead of a timer: (1) straight with the front planted; (2) release the rear and arch (`contract`, until stretch ≤ `FOLDED`); (3) plant the rear beside the front, arch held (`plant_rear`); (4) release the front and straighten on the planted rear, pushing the head on (`extend`, until stretch ≥ `STRAIGHT`); (5) the front plants (`plant_front`), then the rear is released again. A missed rear landing retries in the same direction (it used to reverse). "Straight" holds a slight upward bend (`STRAIGHT_POSE`), because zero left the middle drooping (mean middle joint −0.15 of its range).

`MAX_BEND` is 1.8 rad (was 1.4; the hard joint stop follows it at +0.2, was ±1.6). With 1.4 and flat feet the closest the feet could get was about 2.8 link lengths; the deeper arch `(-1, .5, 1, .5, -1)` of the new range folds to stretch ≈ 0.44 (feet ≈ 2.6 links apart). Its end bends cancel, so the tail and head links lie roughly along the ground: over a flat crawl the tail link is a median 7° off parallel (mean 11°, 90th percentile 29°) and the head link a median 0° (mean 10°, 90th percentile 38°; it dips while the front lets go). The fixed postures (`ARCH`, the turn loop `TURN_LOOP`) keep their old angles through `POSTURE_BEND` = 1.4. Scripted crawl: 3.9 → 63 px/s on flat ground, 12/12 held-out Crawl goals in about 10 s (they took about 73 s), scripted About-face 12/12 in 6–10 s. Because commands scale by `MAX_BEND` and joint observations are divided by it, every earlier checkpoint now acts and sees differently.

The posture expert latches "flipped": once it has called the worm crawling, a stride's deep arch (stretch under 0.6) no longer reads as an unfinished turn.

## Head and tail stay parallel to the ground (scenario version 42)

While walking (Crawl, and About-face once the worm faces the goal) the tail and head links are charged `end_pitch_cost` (0.3/s at the worst) for tilt off parallel to the nearest ground beyond 15° (`PITCH_SLACK`), scaled up to a right angle and averaged over the two ends. The scripted stride costs about 0.013/s on average (mean excess 0.04); a head or tail pointing straight up or down costs the full 0.3/s. Other lessons are not charged: Reach, Feed and Curl need a raised head.


## More Crawl practice (scenario version 43)

From the second lesson on, a quarter of every training batch is Crawl (before, Crawl came up only in the rotation through the earlier lessons, about one episode in thirty at the last lesson). Another quarter still rotates through the earlier lessons, Crawl included, and the current lesson keeps half.


## In the game: inchworms eat everything but inchworms

In the campaign an inchworm now hunts the nearest reachable creature of any kind except another inchworm (`Inchworms._prey`: in range, no wall between), the player ship and hunters included. Before, it chased only the ship, the hunter and friend-allegiance creatures, so it ignored its own side. Other enemies are unchanged: they still ignore it, since it is on their side, and the ship's shots still hit it. A bite costs one hit point and kills at zero, so a creature with many hit points takes a long time; a kill by a bite scores nothing for the player. Two inchworms were added to levels 13, 16, 19, 22, 26 and 29 as minority predators, in open rooms: a worm put in a narrow dead end jammed its arch and blew up the physics solver. `Inchworms.on_frame` now resets a worm whose solver fails, and lets it die after three resets rather than crash the game.

## Gap lesson: stepping from one island to another (scenario version 44)

A ninth lesson, `gap` (stage 9), comes after About-face: (1, 6, 7, 2, 8, **9**, 3, 4, 5). The floor is two separate islands, each a solid block 43 px thick (a game cell) with a top, an underside and an end face either side, as in the game, so a worm can grip an edge face as well as a top (scenario version 45; version 44 drew them as bare lines). The first ends 25–60 px ahead of the arena origin (the worm starts 40–70 px behind that), a gap of 14–42 px follows (a front foot reaches about 50 px), and the second island sits 12 px lower to 12 px higher. The marker is on the far island, 55–110 px past its edge, so the worm has to bridge the gap with its front foot, bring the rear across and walk on. The course comes from the seed (`InchwormEnvironment.gap_course`), so validation and evaluation cases carry gaps too. Success is the Crawl rule (within 14 px of the marker, grounded); the reward is Crawl's, including `crawl_time_cost` and the arrival speed bonus. The gate is 70% on the held-out cases, 2 passes in a row.

There is no demonstration for it: the scripted stride cannot plan a crossing, and it crosses by luck only (8 of 40 held-out-style gaps with blocks: 4 of 12 under 24 px, 2 of 13 at 24–34, 2 of 15 over 34). `DEMONSTRATED` leaves it out of the bootstrap, and the About-face teacher is silent here. A worm that never crosses the lesson still has a path to the marker: walking off the end drifts it away, which costs the airborne penalty.


## Bundled brain

`assets/neural/inchworm.npz` is run248's iteration 282 (scenario version 45; trained from run246/iter1092 after run246 learned About-face with no teacher). On the 12 held-out cases of each lesson, greedy actions, it scored: Crawl 100% (5.5 s), Rear 100%, Curl 100%, Turn 100%, About-face 100% (6.4 s), Gap 83% (25 s), Reach 83%, Feed 100%, Recover 100%. Gap was still being learned when this was picked (the gate had been passed on 2 checks, and a later check scored 58%); the Reach figure sits just above its 80% gate. In campaign levels 16 and 22 the bundled brain drove every inchworm, which ate patrol crabs, babies and neural jellies, with no physics resets. The test suite sets `INCHWORM_POLICY=""` (the scripted stride) so it stays deterministic; gameplay samples actions from a fresh random stream per worm.

## Death: it rolls up into a spiral

A dying inchworm no longer just goes limp. For the 90-frame death it lets go of everything and bends its joints toward a tightening spiral (`SPIRAL` in `entities/inchworm.py`, tail joint 70% of the full bend up to the head joint at 105%), forming over 35 frames and then holding while it fades: about 360° of turning, head tucked in at the centre.
