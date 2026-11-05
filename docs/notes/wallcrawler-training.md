# Wallcrawler training

The trainer trains every creature: Hunter, Jelly team, Flocker team, Wallcrawler team and Inchworm (see [Modular training system](../modular-training.md) for all of them). This page covers the **Wallcrawler team** task.

Start a fresh team from the trainer page's task selector and **Fresh weights**, or:

```sh
./run-trainer.sh start --from new --set task=wallcrawler_team \
  --set workers=4 --set episodes=8 --set horizon=60 \
  --set bootstrap_episodes=8 --set budget_seconds=7200 --set lr=0.0003
./run-trainer.sh status
./run-trainer.sh pause
./run-trainer.sh resume
```

One run can be active or paused. Stop retains its checkpoints. Pause saves after the current iteration. Resume restores the actor, team critic, optimiser, random states, curriculum stage and elapsed budget; incompatible rules, schemas or frozen opponents fail explicitly. New runs may initialise fresh weights or continue compatible task checkpoints. Cross-task checkpoint transfer is rejected.

Each run stores an immutable opponent checkpoint, arena definitions, tuning, versioned observation/action schema, scenario seeds, per-agent joint actions, contributions, PPO state, `best.npz` and `evaluation.json`. The final ten minutes of a two-hour budget are reserved for evaluation. Short smoke runs reserve one sixth of their budget. A hard wall-clock deadline terminates rollout workers; an incomplete evaluation is recorded as incomplete. Bootstrap and checkpoint selection count against the same budget.

The current repeating schedule mixes stationary precision drills, moving-target tracking drills, and Jellyfish/neural-hunter battles. Aiming drills use two crawlers; battles use four. The current actor is schema 5 with continuous aiming, and scenario 56 adds terminal battle success and a performance-gated battle curriculum to the individual survival, death, and Jelly-kill rewards. See the [current curriculum and reward table](#current-crawler-curriculum) for the active rules.

## Boundaries

- `learning/policy.py` and `models.py` share recurrent inference and parameter conversion across creatures. Categorical head names and sizes come from `PolicySpec`; no three-control assumption belongs in the optimiser.
- Creature adapters translate permitted local observations and legal intentions. `learning/adapters/wallcrawler.py` contains the crawler schema and scripted imitation labels. The gameplay driver keeps separate memories and random generators for each stable actor ID.
- Scenario adapters construct actual encounters, opponents, rewards, curriculum and evaluation cases. `crawler_scenario.py` controls the production allied hunter with the frozen hunter checkpoint, using its normal senses, propulsion and gun. No exit, pickup, passive drain or opponent-death path runs in this scenario. Normal hunter projectile collision and damage immunity still apply. Accepted projectile damage restores the hunter’s health after accounting, so immortality does not bypass immunity or create extra rewards.
- `Snapshot`/`Transition` in `learning/environment.py` provide seeded reset, joint action stepping, numeric observations, masks, shared reward and termination/truncation. Every task's adapter supports this interface. The hunter adapter additionally retains its full-episode recorder path for exact compatibility with existing hunter training and reward shaping.
- `training.py`, `ppo.py` and `run.py` own collection, sequence batching, recurrent PPO, horizon bootstrapping and lifecycle. Crawler actor losses exclude dead rows and irrelevant controls. Team value inputs remain training-only; they cannot affect deployed actor logits. Legacy hunter PPO retains its original value model and update behaviour.
- Register an additional task in `learning/tasks.py`, providing its creature/scenario adapter, schema, task defaults/options and task-specific training/evaluation hooks. PPO, rollout workers and run management need no creature-specific branches. The trainer discovers registered tasks.

## Team mechanics

Every six simulation frames all living crawlers are observed before decisions are applied. Five categorical heads control walking (3), trigger (2), detachment (2), landing choice (8) and message (8, including silence); a tanh-Gaussian actuator controls continuous aiming strength. Crawlers share actor weights but have individual recurrent states. They see wall-relative self state, separate visible player and allied-hunter motion (presence, wall-relative position, distance and relative velocity for each) and projectile threats, up to five local teammates, and eight masked reachable landing slots. Hidden teammates' private observations and health do not enter the actor.

Radio reaches 300 pixels through rock. Symbols arrive on the following decision tick, with sender bearing and distance. Attached, stunned and returning crawlers can communicate. Messages have no assigned meanings or direct reward. Bootstrap imitates walking, aiming and firing only; message and detachment heads remain available for PPO exploration.

Both controllers use the same wall attachment, walking, collision, aim and gun rules. Aiming turns at 180 degrees/second within the outward hemisphere. Voluntary hops require one second since attachment and a clear landing slot within 300 pixels and 45 degrees of the current heading. Candidates must approach the receiving wall rather than skim along it.

The feet stay planted during a twelve-frame push, supplying both linear and angular impulse. Launch speed and spin account for airtime and the receiving wall's orientation; short hops use less impulse to keep spin within 180 degrees/second. Once released, linear and angular momentum coast without steering or homing. Bumps can spoil the planned arrival and leave a crawler drifting. A destroyed destination releases its reservation without inventing a replacement impulse.

Feet extend as a wall approaches. On actual contact, stronger damped magnetic torque aligns the body and the legs absorb its momentum as a damped spring. Grip locks only after position, speed and angle settle. Damage retains the 0.6-second stunned interval, with the resulting momentum continuing afterward. **Airborne crawlers can aim and fire during launch, flight and landing; stunned crawlers cannot shoot.** The airborne gun is stabilised in world space; aiming alone does not steer the chassis, while actual shots apply recoil. Swept body spacing prevents stacking; landing reservations use rotating stable-ID priority. Crawlers initially spawned in open space receive a single initial return impulse; if no site exists yet, they wait and retry twice per second. This initial placement path does not rescue crawlers bumped during flight.

The movement and rendering refinements are complete. Earlier checkpoints remain available, but incompatible observation schemas require a fresh run.

Training credits the shooter +1 per accepted projectile hit, charges −0.05 per actual shot and adds at most +0.02 for predicted shot quality. Aiming drills give no landing reward and award a one-time +10 team bonus for clearing every target, split between living crawlers. Battle drills give no landing bonus: they reward time alive (+0.1 per crawler per second), surviving the horizon (+20), and destroying a Jelly (+5 extra), with a personal −40 death penalty in addition to received-hit penalties. Shooter IDs survive on travelling projectiles after their owners die. Current drills use two crawlers, combat uses four, and trials last at most 60 seconds.

## Evaluation and deployment

Held-out curved arenas 15, 20 and 23 use seeds 1000 and 1001, each with two, four and six crawlers. They never supply learning trajectories or checkpoint selection. Fixed validation cases select `best.npz`. Final comparisons use the best actor, the actual scripted controller and the same actor with inboxes muted. Reports include hits/minute, trial hit probability, accuracy, terminal survival and hits/crawler, plus paired hit differences and bootstrap confidence intervals. Nonzero messages alone do not establish useful communication.

Reproduce the held-out comparison, using the run's frozen opponent and arena snapshots:

```sh
venv/bin/python -m learning.evaluate .astrovoid-local/neural/rl/runN --workers 4
```

The trainer's episode list, **Fly again** and **Watch** also support teams. Fly again executes recorded joint actions and checks metrics against the recording. Watch shows the real encounter, each crawler's attachment state, message and health. Replays reject incompatible current physics instead of silently showing a different experiment.

Gameplay uses the bundled brain at `assets/neural/wallcrawler.npz`. `WALLCRAWLER_POLICY=` (empty) gives the scripted crawler. To select a different compatible team checkpoint:

```sh
WALLCRAWLER_POLICY=/absolute/path/to/best.npz ./run.sh
```

Use `WALLCRAWLER_POLICY= ./run.sh` for the scripted fallback. An invalid checkpoint logs its failure and retains scripted control. Training does not install a policy or change campaign enemy behaviour automatically.

## Current crawler curriculum

The repeating twelve-case schedule contains three stationary precision drills, six moving-target tracking drills, and three pursuit battles. Aiming uses two crawlers and twelve harmless targets; battles use four crawlers and progress from one Jelly to two, four, and finally four plus the frozen armed neural hunter. Walking, jumping, airborne firing, recoil, and radio remain available. The hunter accepts normal hits and immunity accounting but has its health restored, so it cannot be killed in this scenario.

| Reward component | Aiming drills | Pursuit battles |
| --- | --- | --- |
| Accepted crawler projectile hit | +1 to shooter | +1 to shooter |
| Actual shot | −0.05 | −0.05 |
| Predicted shot quality | Up to +0.02 per shot | Up to +0.02 per shot |
| Voluntary jump | −0.1 | 0 |
| Landing | 0 | 0 |
| Walking reversal | −0.02 | −0.02 |
| Clear all targets | +10 split among living crawlers, once | No clear bonus |
| Visible-Jelly proximity launch | 0 | Up to +1 to jumper |
| Damaging bullet impact received | −1 | −1 |
| Jelly contact received | −5 if applicable | −5 |
| Time alive | 0 | +0.1 per living crawler per second |
| Battle success | 0 | +20 per surviving crawler, once |
| Crawler death | 0 additional | −40 to dead crawler, once |
| Destroy a Jelly | 0 extra | +5 to final shooter, in addition to hit rewards |

A Jelly takes two crawler hits, so a kill earns +7 total before shot costs. Contact damage is lethal to a full-health crawler; hunter bullets are weak physical hits but still incur their reward cost. Battle success means reaching the time limit alive or clearing all Jellies in a hunter-free stage. Both are terminal outcomes with no critic bootstrap; an uncleared aiming horizon remains truncated. The shaping bonus for a proximity launch is still present; completed landings cannot generate extra battle reward.

New runs start at the one-Jelly stage. Each non-overlapping block of at least 100 completed training battle trials must achieve at least 50% crawler survival and 60% successful trials before promotion. Failed blocks reset the evidence without increasing difficulty. Curriculum state and evidence counters are saved in `resume.pt`; a new checkpoint continuation starts a new curriculum, while resuming retains progress. Held-out battles always use the full encounter. Scenario 56 continuation uses gamma 0.997 and GAE lambda 0.97, recorded in its run arguments; these are not changes to legacy hunter defaults.

Validation uses harmless aiming cases and selects by accuracy × hits per minute. Pure battle selection uses mean battle return. Held-out cases span two-, four-, and six-crawler teams. Inspect stage-specific accuracy, survival, and return: aggregate survival mixes safe aiming with lethal battle cases, and higher return after changing reward coefficients does not establish improved behaviour. Logged `mean_return` averages per-agent trajectory returns, whereas stage return metrics sum the event-level team returns before averaging trials.

## Measuring recoil as a manoeuvring tool

`learning.recoil_evaluation` compares a frozen crawler actor on matched held-out
battle cases, using greedy closed-loop control. One condition keeps normal
physics; the other removes body linear/angular firing impulses and their recoil
events while retaining the bullet's inherited muzzle velocity and spin. Training
runs in separate processes and keeps its normal recoil rules.

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m learning.recoil_evaluation \
  .astrovoid-local/neural/rl/run145 --checkpoint iter0950.npz --workers 4 --seeds 10 \
  --out .astrovoid-local/neural/rl/run145/recoil-ablation-0950.json
```

The evaluator freezes checkpoint bytes by hash, runs both four-Jelly encounters
and four-Jelly-plus-hunter encounters, and reports paired differences in survival,
trial success, Jelly kills, and mean crawler lifetime. Confidence intervals resample
matched cases. It also attributes projectile hits to attachment state at launch,
including hits that arrive after their shooter dies. Attached and airborne shot
counts and accuracies appear in the evaluation report; this instrumentation does
not change active training events or invalidate its recorded episodes.

An advantage with recoil establishes a benefit under this intervention and case
set, not proof that each missed shot was an intentional manoeuvre. Removing recoil
also changes reachable trajectories. Generalisation beyond the tested arenas and
the greedy policy requires further evaluation.

Unplaceable starts are recorded and excluded only when the same case fails in
both conditions. A one-sided failure rejects the comparison. Progress is written
to a sibling `.partial.jsonl` file so completed trial outcomes survive a later
error. Partial results are not treated as the final matched comparison.
