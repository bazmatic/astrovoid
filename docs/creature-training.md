# Creature training

The trainer offers **Hunter** and **Wallcrawler team** tasks. Existing hunter commands, value heads, checkpoint formats, observation adapters and recorded replays retain their legacy behaviour. A run without a task is a hunter run. PyTorch is used only by training; deployed recurrent policies use NumPy.

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

## Boundaries

- `learning/policy.py` and `models.py` share recurrent inference and parameter conversion across creatures. Categorical head names and sizes come from `PolicySpec`; no three-control assumption belongs in the optimiser.
- Creature adapters translate permitted local observations and legal intentions. `learning/adapters/wallcrawler.py` contains the crawler schema and scripted imitation labels. The gameplay driver keeps separate memories and random generators for each stable actor ID.
- Scenario adapters construct actual encounters, opponents, rewards, curriculum and evaluation cases. `crawler_scenario.py` controls the real player Ship with the frozen hunter checkpoint, using player propulsion and basic-gun controls. No exit, pickup, passive drain or player-death path runs in this scenario. Normal shield and projectile acceptance rules still apply.
- `Snapshot`/`Transition` in `learning/environment.py` provide seeded reset, joint action stepping, numeric observations, masks, shared reward and termination/truncation. Both real adapters support this interface. The hunter adapter additionally retains its full-episode recorder path for exact compatibility with existing hunter training and reward shaping.
- `training.py`, `ppo.py` and `run.py` own collection, sequence batching, recurrent PPO, horizon bootstrapping and lifecycle. Crawler actor losses exclude dead rows and irrelevant controls. Team value inputs remain training-only; they cannot affect deployed actor logits. Legacy hunter PPO retains its original value model and update behaviour.
- Register an additional task in `learning/tasks.py`, providing its creature/scenario adapter, schema, task defaults/options and task-specific training/evaluation hooks. PPO, rollout workers and run management need no creature-specific branches. The trainer discovers registered tasks.

## Team mechanics

Every six simulation frames all living crawlers are observed before decisions are applied. Six categorical heads control walking (3), aiming (3), trigger (2), detachment (2), landing choice (8) and message (8, including silence). Crawlers share actor weights but have individual recurrent states. They see wall-relative self state, visible player motion and projectile threats, up to five local teammates, and eight masked reachable landing slots. Hidden teammates' private observations and health do not enter the actor.

Radio reaches 300 pixels through rock. Symbols arrive on the following decision tick, with sender bearing and distance. Attached, stunned and returning crawlers can communicate. Messages have no assigned meanings or direct reward. Bootstrap imitates walking, aiming and firing only; message and detachment heads remain available for PPO exploration.

Both controllers use the same wall attachment, walking, collision, aim and gun rules. Aiming turns at 180 degrees/second within the outward hemisphere. Voluntary hops require one second since attachment and a clear landing slot within 300 pixels and 45 degrees of the current heading. Candidates must approach the receiving wall rather than skim along it.

The feet stay planted during a twelve-frame push, supplying both linear and angular impulse. Launch speed and spin account for airtime and the receiving wall's orientation; short hops use less impulse to keep spin within 180 degrees/second. Once released, linear and angular momentum coast without steering or homing. Bumps can spoil the planned arrival and leave a crawler drifting. A destroyed destination releases its reservation without inventing a replacement impulse.

Feet extend as a wall approaches. On actual contact, stronger damped magnetic torque aligns the body and the legs absorb its momentum as a damped spring. Grip locks only after position, speed and angle settle. Damage retains the 0.6-second stunned interval, with the resulting momentum continuing afterward. **No airborne state, including launch and landing, can fire.** Swept body spacing prevents stacking; landing reservations use rotating stable-ID priority. Crawlers initially spawned in open space receive a single initial return impulse; if no site exists yet, they wait and retry twice per second. This initial placement path does not rescue crawlers bumped during flight.

Preliminary training has been stopped at the user's request while movement and rendering are refined. Older preliminary crawler checkpoints are incompatible with observation schema version 2 and the revised physics. Start a fresh run when refinement is complete.

Training rewards the whole team +1 per accepted crawler projectile hit and −0.01 per actual shot. Shooter IDs survive on travelling projectiles after their owners die. Shields, proximity and contact damage do not produce hit rewards. Trials last 60 seconds or until all crawlers die; teams start at two and progress to four and six after successful batches.

## Evaluation and deployment

Held-out curved arenas 15, 20 and 23 use seeds 1000 and 1001, each with two, four and six crawlers. They never supply learning trajectories or checkpoint selection. Fixed validation cases select `best.npz`. Final comparisons use the best actor, the actual scripted controller and the same actor with inboxes muted. Reports include hits/minute, trial hit probability, accuracy, terminal survival and hits/crawler, plus paired hit differences and bootstrap confidence intervals. Nonzero messages alone do not establish useful communication.

Reproduce the held-out comparison, using the run's frozen opponent and arena snapshots:

```sh
venv/bin/python -m learning.evaluate .astrovoid-local/neural/rl/runN --workers 4
```

The trainer's episode list, **Fly again** and **Watch** also support teams. Fly again executes recorded joint actions and checks metrics against the recording. Watch shows the real encounter, each crawler's attachment state, message and health. Replays reject incompatible current physics instead of silently showing a different experiment.

Campaign crawlers remain scripted by default. To explicitly try a compatible team checkpoint in gameplay:

```sh
WALLCRAWLER_POLICY=/absolute/path/to/best.npz ./run.sh
```

Unset the variable for the scripted fallback. An invalid checkpoint logs its failure and retains scripted control. Training does not install a policy or change campaign enemy behaviour automatically.
