# Neural Flockers

Flockers support a shared recurrent neural brain through the `flocker_team` trainer task. Each bird has its own memory and controls; there is no commander or automatic volley scheduler. No trained Flocker checkpoint is bundled yet. Without weights the normal scripted flocking brain remains active.

## Flight and appearance

Flocker body radius is 6 pixels (50% smaller than the original 12); appearance, collision clearance and mouth placement scale together. Historical recordings reconstruct their recorded body size.

Flockers use top-down aerodynamic flight rather than space-flight momentum. Turning bends their velocity along with the body into an arc. A lateral-acceleration limit makes high-speed turns wider, and steering authority fades at low airspeed so they cannot pivot while stationary. Impact-induced sideways momentum recovers gradually rather than snapping away.

Throttle is continuous from zero to one and supplies forward acceleration against air drag. Zero glides and slows; there is no reverse thrust or active brake. Perched birds remain stationary and accelerate normally when taking off. Existing boolean creature thrust controls remain compatible.

The head pivots independently within 90 degrees either side of the body, at 180 degrees per second. Bullets leave the mouth along the actual head heading, including while preparing a volley. Head rotation never snaps to a target when firing.

Hard wall impacts trigger three rapid wing oscillations over 12 frames, fading into the normal glide. Projectile-hit flash and impact spray remain separate. A gentle wall attachment folds the broad wings along the body, tucks the tail and braces pelvic fins against the wall. The pose follows the wall normal on floors, ceilings and slopes, with subtle breathing. Settling takes 12 frames and unfolding on takeoff takes six; animation does not delay flight or threat response.

## Perching and local sensing

A policy may request perching after one second without a visible adversary or a fresh local target alert. It must approach a static wall within five pixels of body contact, below one quarter maximum speed. The full body must fit without overlapping another Flocker. Moving gates cannot be perched on. Attached birds hold position facing into open space and can aim their heads; they may leave voluntarily to search.

An adversary is visible within 550 pixels with an unobstructed wall/gate line of sight. Personal sight or a teammate's local target-present alert releases a perch on the next six-frame decision. Alerts travel at most 300 pixels, arrive at the next decision, expire after one second and are not relayed. They carry a snapshot of the directly sighted target's position and velocity. The receiving actor observes presence, relative bearing and distance, target velocity and report age. Snapshots expire one second after observation, never track an unseen target live, and do not populate direct-sight target/fire slots. Reports are not relayed. Destroying the supporting wall also releases its occupant.

Each actor sees itself, wall rays, four stable visible-target slots and eight nearest teammates within sight range. Teammate observations include movement, head direction, reload, perch state and the last local message. Eight message symbols are learned; zero is silence. The policy chooses body turn, throttle, head turn, fire, target, message and perch/release. All decisions use the same pre-action scene; the trainer and deployed driver share signal delivery and action mapping.

## Training

The curriculum has six stages, distinguishing the weakened ship from the full-speed neural hunter:

1. Regrouping and cohesive pursuit, teams of 4, 6 or 8: half the drills have no adversary, and a quarter start the group dispersed. Other flocking drills start a compact, nonoverlapping group with 20-pixel spacing and a maximum 120-pixel spread, in clear connected space. Promotion requires both pursuit and cohesion within five percentage points of the scripted baseline. These drills are retained in later stages. First-stage checkpoint selection ranks cohesion with a bounded pursuit contribution, so fast lone pursuit cannot dominate the selection score.
2. Search and rest: targets alternate five seconds absent and five seconds present. Starts include gentle wall approaches.
3. Head aiming against harmless durable targets, starting and respawning in direct sight. Training cycles through target speeds0,1,2,4,6pixels/frame; validation uses1,4,6. Checkpoint selection rewards accuracy times hit rate, balancing precision and throughput.
4. Same-target synchronized volleys, teams of 4, 6 or 8.
5. Combat against the real neural hunter, built with the same settings and frozen policy as gameplay. Only its bullets are weakened: half strength and half damage to Flocker hit points.
6. Combat against the same real neural hunter with full-strength bullets.

One quarter of later-stage training cycles through every earlier stage. Volley promotion also requires at least one synchronized launch group to produce an accepted hit, in addition to its participation and timing checks. Promotion requires two consecutive passing held-out validation blocks; intermediate PPO iterations do not reset that evidence. Validation runs every fifth iteration. Stage and evidence survive pause/resume.

Rewards favor accepted projectile hits and kills, bounded closing progress and moving cohesion. Pursuit progress measures the bird’s own distance reduction toward a fixed snapshot of a directly seen target or a fresh local target report, capped at20 pixels per decision. Target movement and waypoint teleportation cannot create progress credit or penalties. The current pursuit-focused run uses progress coefficient0.01 (previously0.002). Cohesion credit does not require an adversary. A separated bird earns signed credit for its own velocity toward its nearest teammate within 550 pixels and a clear line of sight; moving away costs the same amount. Passive convergence earns no progress credit. Inside 100 pixels, cohesion credit is scaled by the mean cosine agreement of actual velocity directions across nearby teammates with clear sight, clamped to 0–1. Parallel travel earns full credit; a 45-degree difference earns about 71%; perpendicular or opposing travel earns zero. Stationary birds earn zero and stationary neighbours contribute zero. Body heading alone earns no credit. Contact still incurs the contact penalty instead. The cohesion weight is 0.02 per decision. Scenario version 11 records faster visible-start aiming drills, dense aiming progress and separate physical-hit and damaging-hit accuracy plus the real neural-hunter opponent, corrected pursuit progress and target-location reports; policy schema version 3 adds seven report inputs (224 total). Older compatible aerodynamic actors transfer existing feature weights and normalization; new inputs begin with zero weights. Actual shots, bunching, deaths and sustained wall pushing cost reward. Each actual hard wall, gate or boundary impact also costs the colliding bird 0.1 reward (`flocker_wall_collision_penalty`); gentle perching costs nothing. Collision counts and cumulative deductions are reported separately. Runs recorded before this setting retain zero wall-impact cost. A gentle perch earns a small bonus at most once per target-free interval; resting itself earns nothing. Teammates may overlap or pass through each other; there is no solid-body separation or bounce. The teammate penalty applies only while bodies touch or overlap: centre distance at most the sum of their radii (12 pixels for two radius-6 birds). It costs each involved bird 0.01 per decision, or 0.1 per second, once per bird regardless of neighbour count. There is no clearance buffer or penalty for close flight with a gap. `flocker_contact_only=1` selects this rule; `flocker_bunch_distance` is ignored. Historical runs retain their original proximity rule (`contact_only=0`) and recorded distance. Reward settings use `flocker_` prefixes and are frozen per run. Synchronization reward must remain below one accepted-hit reward. Run186 tests shot cost0.01 instead of0.05, with the same hit reward1.0, volley bonus0.5 and five-second reload; this is a measured firing-rate experiment, not a required volley hold.

A volley comprises distinct shooters attacking the same target within six frames of the first launch. The window cannot grow by chaining later shots. Participation counts nearby teammates loaded, in range and with clear firing geometry at opening. Ready subgroups can fire without stragglers. A synchronization bonus is paid once only if a multi-shooter volley actually hits. Practice-target generations prevent a respawn from joining an old volley.

Start fresh using the trainer dashboard, or:

```sh
./run-trainer.sh start --from new --set task=flocker_team --set budget_seconds=3600
```

The direct CLI also defaults Flocker imitation to zero:

```sh
venv/bin/python -m tools.ppo_neural --task flocker_team --start '' \
  --out .astrovoid-local/neural/flocker-experiment \
  --horizon 60 --workers 4 --episodes 12 --iterations 10000 --budget-seconds 3600
```

Positive imitation bootstrap is rejected: this task has no demonstration teacher. A fresh run uses random weights. A short smoke run only verifies the pipeline; it does not produce a useful enemy.

## Evaluation, replay and deployment

Training uses the existing training arenas; validation and final evaluation use held-out levels with separate seeds. Final cases cover teams of 2, 4, 6 and 8 and multiple adversaries, split starts and arriving reinforcements. The environment also supports `reinforcements` in reset cases and the collector starts each new bird with fresh recurrent memory and its own trajectory.

The dashboard records actual accuracy and hit rate, survival, useful volleys, participation, launch spread, cohesion, bunching, stuck time, throttle and perching. Reports additionally record hard contacts, wake latency and target reacquisition times.

The final `evaluation.json` compares the trained actor against the bounded-head scripted controller under the new aerodynamic physics, the unchanged legacy space-flight controller and muted communication. `deployment.passed` requires paired confidence intervals showing more useful volleys, no reduction in hit rate, and no material regression in survival, cohesion or reacquisition. Survival/cohesion tolerance is five percentage points; reacquisition tolerance is one second. An inconclusive comparison fails promotion. The report records the evaluated checkpoint's SHA-256.

`selection_gate_passed` concerns checkpoint selection within the current curriculum stage; it is **not** deployment approval. A fallback `best.npz` may be untrained. No checkpoint is automatically installed.

Check recorded actions using the existing watcher:

```sh
venv/bin/python -m tools.watch_episode RUN ITERATION --check
```

After the deployment gate passes, package the exact evaluated checkpoint:

```sh
venv/bin/python -m tools.promote_flocker RUN
```

Promotion verifies the gate, checkpoint hash, policy schema and recorded rules before atomically installing `assets/neural/flocker.npz`. The game loads it for ordinary Flockers, including Flighthouse spawns. An explicit `FLOCKER_POLICY=/path/to/policy.npz` selects other weights; an empty variable selects scripted fallback. Invalid weights log a warning and fall back. Gameplay inference uses NumPy and does not import Torch.

## Implementation boundaries

- `creatures/flocker_team.py` owns decisions, delayed local signals, visibility and attachment mechanics; the flight trait translates intent into shared propulsion and gun controls.
- `learning/adapters/flocker_scenario.py` owns real-game encounters, rewards, measured volleys, curriculum and evaluation.
- `entities/flocker.py` renders head articulation, impact flutter and wall-oriented perch transitions.

Aerodynamic flight uses scenario and policy version 2. New training must start from fresh weights: old space-flight checkpoints are rejected for deployment and continuation, and old training runs cannot resume under new rules. Exact recorded-action replays for scenario 1 still reconstruct their original propulsion and body size. Changes to current aerodynamic tuning invalidate current-run replay/resume rather than silently changing the simulation.

Long training and a passing deployment comparison remain necessary before claiming learned flocking or coordinated combat performance.

Current Flocker gun cooldown is120 frames (two seconds), allowing up to30 shots per minute per bird. Initial cooldown is sampled within the actual gun interval. Run187 continues stage5 from run186/iter0040 with actor,critic,optimizer and RNG preserved, retaining shot cost0.01 and the real neural hunter with half-damage bullets.

Run188 strengthens contact-only cost to0.05 per decision (0.5 per second) to discourage overlap during combat. It continues run187/iter0036 with full learning state and stage5 preserved. Close flight with a gap is free, touching/overlap is charged once per bird regardless of neighbour count, and no physical separation or bounce is enforced. Prior checkpoints remain available for comparing combat performance.

Run189 doubles health-reducing hit reward1→2, preserving run188/iter0192 actor,critic,optimizer,RNG and stage5. Aim accuracy counts physical projectile contacts including immunity-blocked hits; Damage / shot preserves the old accepted-damage ratio. Hunter immunity is unchanged. Non-damaging landed shots earn no hit reward; useful-volley credit still requires actual damage.

Run190 adds signed aiming-progress credit: coefficient0.2 times the reduction in normalized angular error toward a visible target’s constant-velocity intercept. The before/after comparison holds that observed intercept fixed, so target movement alone earns nothing. Wall-blocked, out-of-range or unreachable intercepts are excluded. Turning away costs the same amount; head wiggling against a static target cannot earn net reward. At that point no aim angles were added to actor inputs; no controls are overridden. It preserves run189/iter0175 actor,critic,optimizer,RNG and stage5; all other current reward values are retained.

Run191 revisits stage3 as a focused aiming refresher, keeping run190/iter0275 actor,critic,optimizer,RNG and all reward coefficients. Combat validation showed9.1%→9.5% aim accuracy after250 updates; each tested bird fired fewer than2shots before death. Harmless visible-start fast targets provide sustained practice before automatically progressing through volley and combat gates again. The prior combat model is preserved.

Run191 aiming-refresher acceptance requires at least40% held-out accuracy (or the scripted benchmark if higher), at least the scripted hit rate, and two consecutive passing validation checks. The acceptance override is saved in resume.pt curriculum and aiming-refresher-acceptance.json.

Run192 tests learning rate0.0002 instead of0.0001, continuing run191/iter0218 with Adam moments, actor/critic weights, RNG and the case/iteration counter retained. The saved optimizer parameter-group rate is explicitly updated because loading optimizer state overrides the newly constructed optimizer rate. Stage3 minimum40%accuracy and all reward/drill settings remain unchanged.

Policy version 4 gives every target slot the aim geometry the reward already uses, so the policy can see what it is rewarded for: `aim_sin/aim_cos` (muzzle heading to the target, zero error is 0/1 and the sign says which way to turn), `lead_present` with `lead_sin/lead_cos` (the same error to the constant-velocity intercept point, falling back to the straight-at-it error when no shot can reach), and `body_vx/body_vy` (target velocity in the bird's own frame, like its bearing and own velocity). Runs 190-192 plateaued at about 20% aim accuracy without these inputs. Version 2 and 3 checkpoints transfer by feature name, so the new inputs start with zero weights and behaviour is unchanged until training uses them. Replays recorded under version 3 are no longer accepted.

Combat training (stage 5) diagnosis and changes (scenario version 13, policy schema version 5). Against the full-strength neural hunter the scripted team survived only 14% of held-out trials, and the learned team did no better; run194 sat at a return of about 11 and 37% survival for 400 iterations. The Flockers could not see what was killing them, and the reward could not tell them. Schema 5 adds: each bird's own hit points; the two most urgent incoming hostile shots (bearing, distance, relative velocity, predicted miss distance and frames to closest approach; `learning/flocker_threat.py`); and, per target slot, how far the target's heading is from pointing at the bird, its damage-immunity timer and its health. The critic gains four incoming shots and every bird's hit points, appended after the earlier columns. Earlier policies transfer by feature name with zero weights for the new inputs, so their behaviour is unchanged until training uses them. Two reward settings are new: `flocker_damage_penalty` (2.0 per hit point lost, so a full-strength hunter hit costs 1) and `flocker_threat_penalty` (0.05 per decision spent in the line of fire). Aim-progress credit now stops while the target is immune, since landed shots then do nothing. Training episodes at stage 5 cycle through a weakened hunter (`HUNTER_RAMP`: damage per hit 0.125, 0.25, 0.5 with 4, 7, 10 hit points) so early combat has wins to learn from; held-out validation and evaluation always meet the full-strength hunter. Replays recorded under schema 4 are refused.
