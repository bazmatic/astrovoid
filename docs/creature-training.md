# Creature training

For the current architecture, module contracts, run artifacts, operating commands, and extension workflow, see [Modular training system](modular-training.md). The later sections of this document include historical scenario changes.

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

The current repeating schedule mixes stationary precision drills, moving-target tracking drills, and Jellyfish/neural-hunter battles. Aiming drills use two crawlers; battles use four. The current actor is schema 5 with continuous aiming, and scenario 56 adds terminal battle success and a performance-gated battle curriculum to the individual survival, death, and Jelly-kill rewards. See the [current curriculum and reward table](modular-training.md#current-crawler-curriculum) for the active rules. Older scenario descriptions below record the evolution of the system rather than current defaults.

## Boundaries

- `learning/policy.py` and `models.py` share recurrent inference and parameter conversion across creatures. Categorical head names and sizes come from `PolicySpec`; no three-control assumption belongs in the optimiser.
- Creature adapters translate permitted local observations and legal intentions. `learning/adapters/wallcrawler.py` contains the crawler schema and scripted imitation labels. The gameplay driver keeps separate memories and random generators for each stable actor ID.
- Scenario adapters construct actual encounters, opponents, rewards, curriculum and evaluation cases. `crawler_scenario.py` controls the production allied hunter with the frozen hunter checkpoint, using its normal senses, propulsion and gun. No exit, pickup, passive drain or opponent-death path runs in this scenario. Normal hunter projectile collision and damage immunity still apply. Accepted projectile damage restores the hunter’s health after accounting, so immortality does not bypass immunity or create extra rewards.
- `Snapshot`/`Transition` in `learning/environment.py` provide seeded reset, joint action stepping, numeric observations, masks, shared reward and termination/truncation. Both real adapters support this interface. The hunter adapter additionally retains its full-episode recorder path for exact compatibility with existing hunter training and reward shaping.
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

Gameplay uses the explicitly deployed local model at `.astrovoid-local/neural/wallcrawler.npz` when launched through `run.sh`. Without that file, crawlers remain scripted. To select a different compatible team checkpoint:

```sh
WALLCRAWLER_POLICY=/absolute/path/to/best.npz ./run.sh
```

Use `WALLCRAWLER_POLICY= ./run.sh` for the scripted fallback. An invalid checkpoint logs its failure and retains scripted control. Training does not install a policy or change campaign enemy behaviour automatically.

### Accuracy shaping

Each actual crawler projectile receives a one-time predicted aim-quality score at launch. Constant-velocity closest approach measures hull clearance within projectile lifetime, with a smooth Gaussian falloff over one target radius. Only visible, unshielded opponents within 550 pixels qualify; current sight and the predicted projectile path must both be clear of rock and gates. The best of the two opponents supplies the score, never their sum. This is a prediction, not a measured hit.

The shared reward remains +1 per accepted projectile hit and −0.01 per actual shot, with no positive reward for predicted aim quality. The earlier +0.1 accuracy shaping stage has been disabled. `mean_aim_quality` is recorded separately from real hit accuracy. Reward metadata rejects incompatible resumes; compatible actor weights can initialise a new run.

### Runs without limits

For creature-team runs, `budget_seconds=0` removes the wall-clock limit and `iterations=0` removes the iteration limit. Checkpoints, periodic fixed-scenario validation, pause/resume and stop remain available. With both limits disabled, final held-out evaluation is a separate `learning.evaluate` invocation; training continues until paused or stopped. Bounded runs retain their reserved evaluation period.

### Practice bullet damage

Both frozen ships’ bullets deal 0.1 health damage to crawlers in training and matched evaluations. Crawlers retain four health, so approximately forty ship bullet hits are needed to kill one. This scenario opts into fractional damage through the projectile’s `creature_damage`; ordinary gameplay shots default to one health damage. Crawler bullets and their rewards retain their existing tuning. Bullet collision and damage-induced detachment remain active.

The current practice stage disables firing for both frozen opponents. A policy wrapper retains their neural movement and recurrent memory while forcing the trigger off; normal gameplay is unaffected. `ships_fire=false` is recorded in the scenario manifest. The 0.1 damage setting remains available for a later armed practice stage.

Voluntary jumps cost the team 0.1 per actual launch. Rejected detach requests, held airborne detach controls, automatic spawn returns and damage-induced detachment incur no jump penalty. `jumps_per_episode` is tracked separately on the dashboard.

Actual attached walking reversals cost the team 0.02 each. Stops and blocked moves do not incur a cost or erase the last nonzero direction; airborne travel resets that history. This is training-only reward shaping, with no direction locks or gameplay movement changes. `reversals_per_episode` records its frequency.

### Hit-only positive reward

Accuracy guidance is disabled (`predicted_shot_accuracy=0`). Positive points come only from genuine accepted projectile hits; shot, jump and walking-reversal costs remain. Predicted quality remains a diagnostic metric. Each practice target dies on its first hit and immediately stops moving, rendering, appearing in observations or accepting further hits. Trials terminate successfully when all twelve targets are cleared, without replenishment. Target-clear rate is reported separately.

### Focused aiming stage

The current stage keeps crawlers stationary and disables voluntary jumps in practice encounters, through matching action masks and scenario intent enforcement. Normal movement physics are unchanged. The scripted baseline also stays still. Shot cost is 0.05, while genuine hits earn 1 and predicted accuracy earns zero. Bootstrap examples train aim and trigger heads; existing actor weights initialise the new run. Walking and hopping can be restored in a later recorded stage. Targets start within sight and the outward aiming hemisphere of at least one crawler.

### Individual aiming rewards

During focused aiming, each crawler receives only its own accepted-hit rewards and actual-shot costs. Jump/reversal costs and any future accuracy shaping are likewise attributed by stable agent ID. Shared weights remain, but rollout rewards are independent per actor. Focal critic inputs put the evaluated crawler first in the roster, so the training critic predicts that crawler’s return; actor observations are unaffected. Other tasks retain shared rewards by omitting the optional per-agent reward map. Dashboard training return is averaged across actor trajectories. Team hit metrics remain encounter aggregates.

Focused aiming uses a fixed 30-frame (0.5-second) reload instead of the campaign’s 100–140 frames. This override is applied to newly constructed training crawlers’ own gun traits, before spawning, and is recorded as `practice_fire_interval_frames`. Shot cost remains 0.05 per actual shot and hit credit remains individual. Other scenarios and gameplay retain their original cadence.

Wallcrawler targeting/sight range is 1,100 pixels. Its bullets retain their original speed but live twice as long (240 frames), for 1,920 pixels of nominal travel before expiry, with walls and arena boundaries still limiting travel. The observation distance unit remains 550 pixels to preserve existing checkpoint feature semantics. Other creatures’ and ships’ bullet lifetimes are unchanged.

Walking is now enabled during aiming practice. Left, stop and right are available to the actor; voluntary jumping remains disabled. Individual rewards, 0.05 shot cost, 0.02 reversal cost and the half-second practice reload remain active. `practice_walking=true` records this curriculum change.

Practice targets now fire aimed bullets at the nearest visible crawler within 550 pixels. Bullet speed is 2 pixels/frame, cadence 180 frames, lifetime 240 frames, and damage 0.1. Initial cooldowns are seeded independently from 90–180 frames. Destroyed targets stop firing immediately; their existing projectiles remain in flight. Target shots are visible as normal hostile projectile threats to crawlers and use ordinary collision and damage-induced detachment rules. They do not earn rewards or count as crawler shots.

Bullet knockback now transfers momentum by projectile-to-crawler mass ratio and
bullet damage strength, for both linear and angular motion. Breaking an attached grip adds a separate 0.9 px/frame outward release kick,
independent of bullet strength, to carry it clear of the wall. That kick is never
reapplied in midair. Airborne crawlers retain their momentum between impacts;
explosions keep their existing 2.8 px/frame knockback. Scenario version 23 records
this physics change.

Practice training now enables voluntary jumping alongside walking (scenario 24).
The actor chooses detach and a legal landing candidate after attachment cooldown;
launch and landing use the shared physical rules, and airborne firing is masked.
Each actual voluntary launch costs only its actor 0.1 reward. Damage-induced
release does not incur this jump cost. Imitation still supervises only aim/fire,
leaving detachment, landing selection and messages available for exploration.

Gameplay Wallcrawlers now use the same fixed 30-frame reload as practice training
(two shots per second at 60 FPS). Other creature gun cadences are unchanged.

### Dodge and reposition curriculum (scenario 25)

Start with two crawlers and keep that team size until a paired evaluation supports
progression. Each batch mixes 75% dodge encounters and 25% the existing shooting
encounters. Dodge encounters retain variable target speeds and target size, use
six one-hit targets, and prefer starts with legal forward landing routes. Up to
one target per crawler starts behind rock or outside its firing hemisphere but
is exposed from a reachable landing site. The generated count is logged rather
than assuming every arena supplies such a target.

Dodge targets fire three slow bullets, 12 frames apart, with their direction
locked when the burst starts. They wait 180 frames after a burst and start after
a seeded delay of 60–120 frames. Jump cost is temporarily 0.02 for dodge trials;
shooting trials retain 0.1. Hits, shots, received bullet hits and direction changes
retain their existing individual accounting. No reward is paid for jumping.

The dashboard labels replay stages and plots time airborne. Replays preserve the
stage and its reward coefficients. Reproduce the held-out jump ablation with:

```sh
venv/bin/python -m learning.evaluate .astrovoid-local/neural/rl/runN --suite dodge --workers 4
```

It compares the greedy policy against itself with voluntary jumping disabled,
using identical arena seeds, starting positions and target firing schedules.
Reports include incoming hits, shooting performance, airborne time and survival.
`supports_progression` requires a positive lower 95% bootstrap bound on avoided
bullet hits, at least 90% of the no-jump shooting hit count, and no survival drop.
This is a diagnostic gate, not an automatic team-size increase. A short smoke
run or a rise in jump frequency alone does not establish useful defence.

### Allied Jellyfish pursuit (scenario 26)

Pursuit trials now replace the burst-firing dodge targets in 75% of batches; the
remaining 25% retain shooting practice. Two crawlers face four actual catalogue
Jellyfish (`aggressive`) with per-instance allied allegiance and speed 0.9.
Their production Chase, Drift, wall bounce, crowd spacing and Jellyfish body are
reused. They pursue the nearest living crawler, have their normal one-hit health,
and do not fire. Campaign Jellyfish allegiance and tuning remain unchanged.

The Jellyfish share an encounter separate from the crawler agent roster. Crawler
bullets use their normal damage pipeline and award +1 only on an accepted hit.
Contact applies 0.25 damage, normal collision impulses and dislodgement, and an
individual 0.1 penalty. A 30-frame cooldown per crawler is shared across all
Jellyfish, preventing overlapping pursuers from stacking damage every frame.
Contact never earns a projectile-hit reward or counts as a received bullet.
Voluntary jumps cost 0.02 in pursuit trials and 0.1 in shooting trials.

The dashboard labels Jellyfish pursuit episodes and plots contact hits separately
from bullet hits. The paired jump evaluation now counts both damaging contacts
and bullet hits, and retains its shooting and survival checks:

```sh
venv/bin/python -m learning.evaluate .astrovoid-local/neural/rl/runN --suite pursuit --workers 4
```

Evaluation takes an immutable weight snapshot, so an active trainer updating
`best.npz` cannot change the actor between paired scenarios.

Scenario 27 increases allied Jellyfish contact damage to 4 HP: a single contact
kills a full-health crawler. Lethal contacts skip dislodgement, so contact cannot
provide a free escape. The individual 0.1 contact penalty and 0.02 pursuit jump
cost remain unchanged. Campaign Jellyfish damage is unaffected.

Scenario 28 gives allied training Jellyfish 4 HP, requiring four normal crawler
hits to kill. Each accepted damaging projectile still earns its shooter +1;
there is no additional kill reward. Lethal 4 HP contact damage is unchanged.
Campaign Jellyfish retain their original one-hit health.

### Pre-contact jump demonstrations (scenario 29)

New runs can bootstrap from a defensive jump teacher before PPO. The teacher
uses visible allied Jellyfish position/velocity and legal landing candidates. It
requests a jump when predicted contact is within 45 frames and the launch
trajectory provides at least 3 pixels of clearance and improves on continuing
the current walk. It respects attachment cooldown, reservations and the real
12-frame launch ramp. These are predictive examples, not guaranteed escapes.

Behaviour cloning supervises aim, fire, detach and landing, with class balancing
for rare examples. It does not label messages or install a scripted jump rule in
gameplay. After bootstrap, normal PPO samples the policy and retains the existing
individual rewards. Demonstrations are saved in `episodes/bootstrap.json`; exact
action replay is available as `learning.replay.fly(run_path, "bootstrap")`.
The shared trainer records demonstrations without inspecting creature objects.

### Retaining demonstrated jumps (scenario 30)

The earlier imitation procedure balanced classes separately per trajectory, then
PPO largely erased the rare jump examples. Crawler bootstrap now uses a globally
class-balanced loss with one accumulated update per epoch, for 64 epochs. No-jump
trajectories cannot overwhelm rare positive demonstrations merely by outnumbering
them. Other task adapters retain the legacy imitation path unless they opt in.

During PPO, a 0.1-weight auxiliary jump/landing loss rehearses a demonstration
containing a jump alongside an ordinary trajectory. Rollout actions still come
from the neural policy; there is no forced jump during PPO or gameplay. Saved
`demonstrations.pt` data are restored on resume, and incompatible/missing resume
data are rejected explicitly. The dashboard plots the auxiliary loss. Its decline
is not proof of safe escapes; matched held-out survival/contact comparisons remain
the criterion for progression.

The initial escape scaffold now uses one Jellyfish per crawler (two total),
starting at least 120 pixels from every crawler and preferring an oblique
approach. This prevents contact before the initial jump cooldown in the tested
stationary start. It preserves four-hit Jellyfish health and lethal contacts.
The teacher anticipates pursuit steering, acts within a 75-frame threat window,
and checks 90 frames of escape clearance. Increasing pursuer count waits for a
successful paired evaluation; it is not justified by jump frequency alone.

Scenario 31 restores four allied Jellyfish per pursuit trial (two per crawler),
retaining separated oblique starts, four-hit health, lethal contact damage and
escape demonstration rehearsal.

Scenario 32 increases allied pursuit Jellyfish speed from 0.9 to 1.2 pixels
per simulation frame. Four-hit health, lethal contact, start clearance,
demonstrations and rehearsal remain unchanged; campaign Jellyfish are unaffected.

### Escape teacher validation, 29 October 2026

Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m
learning.validate_crawler_teacher --out /tmp/crawler-teacher.json` from the
repository root (join the command onto one line). Exit status 1 means the teacher
failed validation, not that the audit crashed.

The validator uses levels 15, 20 and 23 with seeds 1000 and 1001, two crawlers and
the current four-Jelly physics. For each proposed jump it replays the identical
action prefix twice, changing only the focal crawler's detach decision. Both
branches then use scripted walking/aiming/firing without further jumps for two
seconds. It records accepted contacts, survival, displacement and reattachment.
This tests the launch itself; it does not claim long-term survival or neural
policy performance. The report also records the complete teacher encounter.

Baseline: 12 crawlers, zero encounter survivors, one proposed jump, zero safe
jumps, zero successful reattachments. The proposed jump was at frame 60 on level
20/seed 1000; it died in flight at frame 121. The no-jump branch also died.
Increasing the prediction lead from 75 to 120 frames alone produced identical
results. An isolated diagnostic with the initial attachment cooldown removed
produced ten jumps, four contact-free two-second escapes and five reattachments,
but still zero encounter survivors. This identifies the initial reaction window
as a substantial restriction, while also showing that removing it does not make
the teacher reliable. These diagnostic changes are not applied to training.

Run 122 is paused at iteration 1565. No replacement training run or gameplay
deployment is warranted by this failed validation. Initial approach timing,
unsafe route predictions and survival after landing need separate fixes and
another physical validation before collecting new demonstrations.

### Physics-based teacher revision (scenario 33)

The teacher now rolls out an isolated copy of the crawler through the production
wall movement code rather than approximating a straight flight that stops at the
destination. This includes leg acceleration, angular momentum, magnetic capture
and walking after landing. It considers 240 frames, requires an actual landing,
and checks another 60 frames of clearance after that landing. Visible pursuers
are conservatively assigned the fastest observed pursuer velocity, preventing a
temporary bounce slowdown from being mistaken for a permanently slower enemy.
It never reads hidden pursuer positions or private movement tuning.

Pursuit trials now start with established wall occupants whose initial cooldown
has elapsed. All subsequent landings retain their normal 60-frame cooldown.
The threat lead is 120 frames. No rewards, Jelly count, health, speed or campaign
mechanics changed. These rules require a new training run; run 122 stays paused.

The validator now follows a jump through reattachment and its 60-frame cooldown,
up to a six-second cap, and matches the no-jump branch to the same endpoint.
Counterfactual branches preserve the parent encounter's global random state.
The original two-second cutoff was insufficient to establish a full landing for
long hops; earlier two-second safety figures should not be read as landing tests.

Revised result on the same six diagnostic encounters: five proposed jumps, all
five reattached and survived their cooldown without contact. Their matched
no-jump branches all received lethal contact. One encounter produced no jump;
all twelve crawlers still eventually died during the complete teacher encounters.
Validation therefore remains failed for encounter coverage and sustained
avoidance. These fixed cases have now been used for development and are no
longer untouched evaluation evidence. Independent seeds are required before
claiming generalisation or resuming training in earnest.

A subsequent independent check used seeds 1100 and 1101 on the same three
arenas (`--seeds 1100 1101`). All three proposed jumps landed and survived the
cooldown without contact; their no-jump counterparts died. Only one of twelve
crawlers survived the full 12-second encounters, and four encounters had no jump.
Together the two sets contain eight successful matched escapes out of eight
proposed jumps, but inadequate opportunity coverage and sustained survival.
The stricter validator still returns failure. Focused creature-learning and
wallcrawler tests: 105 passed.

### Preparing escape routes, 30 October 2026 (scenario 34)

When no currently legal hop is safe, the teacher can stop and turn its gun to
bring another reachable landing into the forward cone. It forecasts the time
needed to aim and wait out any remaining cooldown before accepting that plan.
Preparation can happen during attachment cooldown, but never bypasses the actual
detach mask. Messages remain sampled; no communication labels are imposed.
Bootstrap now includes movement labels, and rehearsal includes movement and aim
alongside detach and landing so the necessary preparation is not discarded.

The motion forecast also follows the six-frame scripted decision schedule.
Airborne decisions set walking to stop; when a crawler lands between decisions,
walking resumes only on the following tick. Previously the forecast walked
immediately after landing, causing measured position errors up to 3.25 pixels,
larger than the three-pixel safety margin. The physical regression test fails
with this decision scheduling disabled and passes with it enabled. No launch,
aiming, gun or campaign physics were changed.

On development seeds 1200/1201 across the three diagnostic arenas, the revision
produced eleven proposed jumps: ten survived landing and cooldown, nine avoided
contacts present in their matched no-jump branches. Two of twelve crawlers
survived the complete encounters. A subsequent check on fresh seeds 1300/1301
produced nine jumps, eight safe landings, six matched contact avoidances and one
full-encounter survivor out of twelve. The remaining fresh-seed failure involved
a Jellyfish occluded at takeoff, as recorded by the validator's contact context.
The teacher does not receive hidden enemy positions to eliminate that risk.

The validator now confirms actual launches rather than treating a requested
detach as proof of takeoff. It records preparation ticks and whether targets
near a later collision were visible at launch. Full validation still fails:
route coverage and sustained survival remain insufficient. Run 122 remains
paused; these changes have not trained or deployed a replacement model. Focused
creature-learning and wallcrawler tests: 106 passed.

### Jump proximity reward (scenario 35)

Pursuit trials now award the jumping crawler `max(0, 1 - clearance / 150)`
points per actual voluntary launch, using the body-to-body clearance to the
nearest living, visible allied Jellyfish at takeoff. The reward is zero at or
beyond 150 pixels and reaches +1 at contact. Multiple enemies do not stack it.
Rejected requests, damage-induced detachment and repeated airborne requests earn
nothing. The pursuit jump cost is zero; shooting/dodge trial costs are unchanged.
Other personal hit rewards and costs remain in effect. Events, exact replay,
checkpoint selection and the dashboard reward card include the new bonus.

Run 123 continues from run122/iter1565 with twelve workers and no
bootstrap demonstrations or imitation rehearsal. It tests learning directly from
the requested reward rather than depending on the escape teacher. A new run is
required because the reward manifest differs from run122.

Scenario 36 increases the minimum Jellyfish spawn distance from 120 to 300
pixels, measured centre-to-centre from every crawler. The sampler must satisfy
that distance and never falls back to a closer start. All 36 checked combinations
of the twelve training/diagnostic arenas and three seeds supplied valid starts;
the closest was 300.1 pixels. Jelly count, speed, damage and the proximity reward
are unchanged. The continuation retains run123/iter0109 actor weights, twelve
workers and no teacher imitation. Close-approach regression tests explicitly
retain their original fixture spacing rather than depending on curriculum tuning.

Scenario 37 adds +1 to the landing crawler for each completed voluntary hop.
Credit is pending only after an actual launch and is consumed once the living
crawler reaches the attached state after collision processing. Death or a
damage-induced stun cancels pending credit; automatic recovery from dislodgement
does not earn it. Remaining attached cannot repeat the reward. The proximity
takeoff bonus remains separate. Landing counts appear in events, exact replay,
personal returns, checkpoint selection and the dashboard reward card. The
continuation, run125, starts from run124/iter0060 with the existing twelve-worker setup.

### Spacious wall starts (scenario 38)

Practice starts now require clear, visible space across a 120-pixel frontage and
180 pixels outward from the wall, checked at multiple depths and lateral offsets
with crawler body clearance. The dodge/pursuit repositioning search applies the
same requirement after attachment and preserves crawler separation. It can no
longer trade the starting space for a concealed target in a cramped corner.
Level 22 has no qualifying starts in the placement audit and is excluded from
this training stage. Campaign arenas and creature physics are unchanged.

The continuation retains run125's learned actor weights, twelve workers, rewards
and absence of teacher imitation. A new run records the changed scenario rather
than resuming a checkpoint under a different spawn manifest.

Validation: 122 focused learning/wallcrawler tests passed. A placement audit
covered 66 two-crawler encounters (three seeds, shooting and pursuit, all eight
training and three held-out arenas) plus 22 six-crawler encounters: all 264
crawler starts met the clearance check. This verifies starting geometry, not
improved learned survival or policy quality.

Run126 continues from run125/iter0174 with scenario 38 and twelve workers;
its first PPO iteration completed successfully.

### Faster training Jellyfish (scenario 39)

Training pursuit Jellyfish now move at 1.5 pixels per simulation frame, up from
1.2 (25% faster). Campaign Jellyfish retain their catalogue speed. Spacious
starts, four pursuers, health, contact damage, rewards and the twelve-worker
training configuration are unchanged. The continuation starts from
run126/iter2368 with no bootstrap or imitation rehearsal.

### Individual random Jellyfish speeds (scenario 40)

Each training pursuit Jellyfish now receives an independent uniform speed in
[0.5, 2.5] pixels per simulation frame at spawn. Its sampled speed remains fixed
for the trial and is applied through the existing production `drift` trait.
A separate local RNG seeded with scenario seed + 43000 makes sampling repeatable
without coupling it to the placement search or changing global randomness.
The manifest records the bounds, distribution, sampling lifetime and seed offset.
Campaign creatures and the other training rules are unchanged. The continuation
retains run127/iter0645 actor weights and the existing twelve-worker setup.

Run128 continues this configuration from run127/iter0645. Validation: all 85
creature-learning tests passed, including per-creature variation, range bounds,
seed repeatability and speed persistence. The historical escape-physics fixture
explicitly retains its original fixed 1.2 speed and 120-pixel starting clearance.

### Neural hunter alongside Jellies (scenario 41)

Training, validation and held-out comparison now enable `neural_hunter=True`
for practice encounters. One frozen neural hunter uses the run's immutable
opponent checkpoint and normal movement, senses and firing policy. Its bullets
use the existing scenario-only 0.1 creature damage. Four pursuit Jellies retain
their independent 0.5–2.5 speeds, and shooting trials retain their practice
targets alongside the hunter. Crawler start/reposition sites stay at least 180
pixels from the hunter as well as meeting the spacious-start requirement.

The existing observation schema already exposes hunter motion and projectile
threats. No new actor weights or bootstrap are needed. Accepted crawler hits on
the hunter earn the normal individual hit reward; the hunter retains normal hit
immunity and has health restored after collisions. Clearing the additional
targets no longer ends a trial while the hunter remains. Trials end at the
horizon or when the crawler team dies. Other rewards and campaign rules remain
unchanged. The continuation uses run128/iter0231 and twelve workers.

Run129 is training with this configuration. Validation: 87 creature-learning
and 26 trainer tests passed. The real frozen hunter fired weak bullets in a
repeatable encounter alongside four Jellies; clearing the Jellies retained the
hunter encounter. Placement audits covered all eleven training/held-out arenas
with both two- and six-crawler teams (176 qualifying crawler starts).
Exact replay of run129/iter0000 matched all recorded events across 12 episodes.

### Large Jelly contact penalty (scenario 42)

Each accepted Jellyfish contact now costs the struck crawler 5 reward points,
up from 0.1. That equals 100 shots at the existing 0.05 shot cost, or 50 weak
bullet hits at 0.1 each. The shared contact cooldown and individual attribution
remain intact, including lethal contacts. Checkpoint selection now uses the
separate contact cost rather than reusing the weak-bullet penalty, so it also
strongly penalises Jelly collisions. Replay and dashboard values come from the
recorded reward manifest. Physical damage, hunter bullets, random Jelly speeds
and other rewards remain unchanged. Continue from run129/iter0256 with twelve
workers and no teacher imitation.
Run130 is the active continuation. Four focused checks passed for individual
contact penalties, lethal contact, checkpoint selection and the weak-bullet
neural hunter integration.

### Larger bullet-hit penalty (scenario 43)

Each accepted damaging bullet hit now costs the struck crawler 1 reward point,
up from 0.1: equivalent to 20 shots at the unchanged 0.05 shot cost. Jellyfish
contact remains -5. Individual returns, shared diagnostics, checkpoint selection,
replay and the dashboard all use the recorded bullet penalty. Lethal hits count;
zero-damage impacts and duplicate hit callbacks do not. Hunter bullets still do
0.1 physical damage. Continue from run130/iter0022 with twelve workers.
Run131 is the continuation. Five focused tests passed for accepted and lethal
bullet hits, duplicate/zero-damage handling, checkpoint selection, lethal Jelly
contact and the neural hunter encounter.

### Four-crawler teams with radio (scenario 44)

The next training stage starts at four crawlers, up from two; validation matches
four, while held-out comparisons retain two/four/six teams. Automatic promotion
continues to hold the requested size. The continuation retains run131/iter0381
actor weights, twelve workers, four random-speed Jellies, the weak-bullet neural
hunter, -1 per accepted bullet hit and -5 per accepted Jelly contact.

Messaging was already enabled in sampled PPO training. All eight symbols
(including silence) are legal; messages arrive at the next decision tick within
300 pixels through rock. The message head receives PPO gradients and receiver
observations include sender-relative geometry and symbols. The manifest now
explicitly records those radio settings. Muting remains an evaluation ablation;
no message imitation labels or direct message rewards are added. These mechanics
do not establish that the current policy has learned useful communication.
Run132 is the four-crawler continuation. Fifteen focused curriculum, radio,
observation and message-gradient checks passed. All 88 crawler starts in the
22-encounter, four-crawler placement audit met the spacious-start requirement.

### Faster crawler firing (scenario 45)

Crawler gun cooldown is now 15 simulation frames instead of 30, allowing up to
four shots per second at 60 FPS when attached and continuously requesting fire.
Both the campaign crawler gun catalogue and practice override use the same
cadence. Neural trigger decisions, aiming rules and the airborne firing ban
remain intact. The per-shot reward cost stays -0.05. Four-crawler teams, radio,
the neural hunter, random-speed Jellies and received-hit penalties are retained.
The continuation starts from run132/iter0189 with twelve workers. An already
running campaign process picks up the new catalogue on its next launch.
Run133 is the active continuation. Thirty-five focused firing, airborne,
bullet-damage and checkpoint checks passed, including four shots over 60 frames
and matching 15-frame cooldowns for training and campaign crawlers.

### Bounded shot-quality shaping (scenario 46)

Enable the existing predicted interception-quality reward with weight 0.02 per
actual shot, using the existing smooth score in [0, 1]. Predictions use visible
geometry, target velocity, bullet travel/lifetime and wall/gate checks. Each
crawler projectile is scored once for its owning crawler; multiple targets do
not stack the bonus. Actual accepted hits retain their separate +1 reward.

The shot cost remains -0.05, so even a maximum-quality shot has net launch reward
-0.03 before any accepted hit. Predicted near misses cannot generate positive
return by themselves. Physical aiming, firing rate, curriculum, checkpoint
selection and received-hit penalties remain unchanged. Continue from
run133/iter0121 with four crawlers, messaging and twelve workers. This experiment
changes only the accuracy shaping weight; improvement must be assessed using
actual hits/shots and hits per minute, not predicted quality alone.
Run134 is the active continuation. Twenty-nine focused geometry, motion-leading,
reward-bound, individual-credit, duplicate-scoring, projectile and selection
checks passed.

### Continuous gun actuator (scenario 47, action schema 5)

Neural aiming now uses a signed continuous strength instead of three categorical
choices. The actor emits a Gaussian mean and log standard deviation; a sampled
activation is transformed with tanh into [-1, 1]. Gun rotation remains strength
x 180 degrees/second within the existing outward hemisphere. At the unchanged
six-frame decision interval, strength 1/12 turns 1.5 degrees and full strength
approaches 18 degrees. Trigger, walking, jumping, landing and radio remain
categorical. Airborne aim is neutral and airborne firing remains forbidden.

Trajectories and exact replays retain the fractional pre-squash activation.
PPO scores its Gaussian density (the transform Jacobian cancels in probability
ratios), and uses 16-point Gaussian quadrature for bounded-action entropy.
Log standard deviation is clamped to [-5, 1]. Mixed-action batches retain floating
point values; only categorical likelihoods convert their own columns to integer
indices. Demonstrations regress continuous actuator strength rather than treating
it as a class label.

Fresh continuations can explicitly migrate schema-4 actors: retain every
backbone, normalisation and non-aim parameter; initialise the new aim mean from
half the old right-minus-left output weights and biases, and initialise standard
deviation to 0.35. This preserves learned representations and other controls,
not exact old aiming decisions. Existing schema-4 campaign actors retain their
original categorical driver; new actors use the continuous actuator in campaign
and training alike. Old training resumes/replays remain schema-checked.

The continuation source is run134/iter0025. Four crawlers, twelve workers, radio,
random-speed Jellies, the weak-bullet neural hunter and all reward weights remain
unchanged, including the bounded +0.02 shot-quality bonus. A pre-change benchmark
is saved at `.astrovoid-local/neural/continuous-aim-baseline.json`: six fixed
20-second shooting trials on levels 13/17, seeds 2400–2402, four crawlers without
the hunter. Greedy accuracy was 19.11% at 69.87 hits/minute; sampled accuracy was
12.84% at 44.70 hits/minute. These isolated shooting cases differ from the mixed
training curriculum. They provide a fixed baseline, not evidence of improvement.

Run135 is the active continuous-actuator continuation. Validation: 172 focused
learning, actuator, projectile, movement and trainer tests passed, plus the
legacy campaign-driver compatibility check. Its first PPO iteration recorded
3,533 fractional aiming activations among 8,219 joint-agent actions; exact
replay matched all events in all twelve episodes.

The initial migrated actor benchmark is saved separately at
`.astrovoid-local/neural/continuous-aim-initial.json`. On the same six shooting
cases it measured 15.53% greedy accuracy at 51.50 hits/minute and 10.61% sampled
accuracy at 43.85 hits/minute, below the pre-migration baseline. This small
initial comparison is evidence of a migration cost, not an accuracy improvement;
the new aiming head needs learning and later matched evaluation.

### Aiming-focused curriculum (scenario 48)

Three quarters of each twelve-trial batch now isolate the continuous aiming
actuator. For the first fifty iterations, six precision trials use stationary
targets, three tracking trials use moving targets and three pursuit trials retain
the random-speed Jellies and armed neural hunter. From iteration fifty onward,
precision/tracking counts swap to three/six; pursuit remains three. Four-crawler
teams, radio, twelve workers, gun cadence and all reward weights are retained.
The continuation uses run135/iter0025 without replacing the continuous actor.

In precision/tracking drills crawlers remain planted: movement and voluntary
jumps are masked and ignored, while the policy still chooses aiming strength,
firing and messages. Targets cannot fire, and no hunter is present. Target
placement samples outward depths of 120–300 pixels with lateral variation;
precision target velocities are zero and tracking speeds remain 0.5–1.5 pixels
per frame. Original shooting/dodge/pursuit scenario behaviour remains available.

Fixed validation cases now contain equal numbers of precision/tracking trials.
Checkpoint selection on those trials uses measured accuracy multiplied by actual
hits per minute: staying silent scores zero, and jumping/landing bonuses cannot
improve this score. General combat summaries retain their previous selection
formula. Held-out evaluation includes precision, tracking and pursuit cases.
Training reports and the dashboard separate stationary-target, moving-target
and combat accuracy so a changing mixture is not mistaken for learning progress.

Drill reset also resolves rare concave-pocket starts onto another clear planted
surface before targets are placed. A placement audit passed 66 four-crawler
encounters across all training/held-out arenas and three seeds, plus 24 held-out
two/six-crawler encounters. All ninety encounters supplied twelve harmless
targets and fully attached crawlers.

Run136 is training this curriculum from run135/iter0025. Validation: 139 focused
curriculum, actuator, reward, observation, replay-compatibility and dashboard tests
passed. The first recorded batch contains six precision, three tracking and
three pursuit trials. Per-stage accuracy/hit-rate metrics are present in the
training log. Early aggregate rates reflect the new task mixture and should not
be compared directly with the prior combat-heavy run.
Exact replay of run136/iter0000 matched all recorded events across twelve trials.

### Mobile aiming drills (scenario 49)

Precision and tracking drills now permit policy-controlled walking and voluntary
jumps. They still begin with attached crawlers, retain harmless targets and no
hunter, and use the same 75% aiming / 25% combat schedule. Normal jump cooldown,
landing legality and airborne firing restrictions apply. Existing rewards and
aiming-based checkpoint selection are unchanged; landing rewards do not enter
the aiming validation score. Dashboard descriptions now distinguish target
motion without describing the crawlers as planted. Continue from
run136/iter0019 with four crawlers and twelve workers.
Run137 is the continuation. Thirty-seven focused drill, continuous-actuator and
dashboard checks passed, including actual walking and legal launches in both
aiming drill types while confirming harmless targets and airborne fire masks.

### Two-crawler aiming drills (scenario 50)

Precision and tracking training/validation trials now use two crawlers; pursuit
training retains four. The stationary warmup completed in run137, so this
continuation keeps the moving-target emphasis immediately: three precision,
six tracking and three pursuit trials per twelve-trial batch. Walking, jumping,
radio, twelve harmless drill targets, rewards and twelve workers are retained.
Held-out two/four/six-team comparisons remain available. Continue from
run137/iter0051 with the existing continuous actor.
Run138 is the active continuation. Twenty focused curriculum, validation,
movement/jump and radio-configuration tests passed, including a real two-crawler
precision reset and the two-drill/four-combat case split.

### Two-hit training Jellies (scenario 51)

Allied pursuit Jellies now have two hit points instead of four: two ordinary
crawler projectile hits kill one, while each accepted hit is still credited
once. Campaign Jelly health, lethal Jelly contact damage, random speeds and all
other training settings are unchanged. Continue from run138/iter0458, retaining
two-crawler aiming drills, four-crawler combat and twelve workers.
Run139 is the continuation. Six focused checks passed for two-hit death, hit
credit, ordinary campaign health, contact behaviour and the historical escape
physics fixture (which explicitly retains its original four-hit Jellies).

### Crawler collision momentum (scenario 52)

Swept crawler-body contacts now use the shared mass-based circle collision
impulse and configured restitution instead of setting flight velocities to zero.
Two free crawlers exchange momentum; glancing impacts preserve tangential motion,
and co-moving/separating bodies do not receive spurious blocking impulses.
Body spacing still prevents tunnelling and stacking. Planted crawlers retain
their wall support; an incoming airborne crawler rebounds off that support.
Moving planted contacts account for the timestep when calculating their velocity.

A body collision cancels a free crawler's old launch/capture plan and landing
reservation, preserving its new ballistic momentum and spin rather than letting
a stale launch ramp or magnetic spring overwrite the bounce. Actual subsequent
wall contact still uses normal magnetic landing mechanics. Campaign and training
share this response. Continue from run139/iter1225 under the new physics manifest.
Run140 is the active continuation. All 135 focused crawler/learning/movement
checks passed, including momentum and restitution with unequal masses,
tangential preservation, high-speed separation, co-moving/separating peers,
planted support and timestep-consistent moving-support impulses. A live campaign
process needs restarting to load the corrected collision code.
Exact replay of run140/iter0000 matched all recorded events in twelve episodes.


### Completion-driven relearning and airborne fire (scenario 53)

Aiming drills now give zero reward for successful landings while retaining legal
walking and jumping. Counts remain recorded for analysis. Clearing all aiming
targets while at least one crawler is alive awards +10 to the team once, divided
equally among living crawlers (+5 each when both survive). Timeout, team death,
ordinary shooting/dodge trials and immortal-hunter combat do not earn the bonus.
Shared transition rewards, individual returns, replay and dashboard metadata use
the same stage-specific landing coefficient and recorded completion credit.

Launch, flight and landing now allow aiming and firing in campaign and training.
The airborne gun holds its world heading at zero actuator strength and rotates
proportionally at up to 180 degrees/second; it is unconstrained by the former
wall hemisphere until attached. Chassis momentum and spin remain ballistic.
Stun still disables aiming and firing. The actor masks, PPO enabled controls,
scripted controller and neural driver follow those same rules.

The continuation uses run140/iter0184 with one-time `--actor-scale 0.5`.
Only action-head weights/biases are halved: perception/embedding, recurrent
memory and observation normalisation are retained. The continuous aim mean is
halved; its log-standard-deviation output is reset to a constant log(0.35).
The fresh run creates a new optimiser. Initial weights and initialization
metadata are saved in the run. The scale flag is deliberately excluded from
inherited settings; resuming or ordinary future continuations do not repeat it.
Source checkpoints remain unchanged.

Run141 is the active relearning continuation. Validation covered 256 focused
reward, completion-sharing, damping, airborne control, movement, trainer and
replay-related checks. Its saved initial arrays exactly match one-time 0.5
output-head damping of run140/iter0184, including the preserved backbone and
reset aim exploration. Training iterations are completing with the new rules.
Exact replay matched all twelve first-batch episodes, including zero aiming
landing coefficients and one-time completion bonuses on successful clears.


### Emergent recoil steering (scenario 54)

The crawler gun now opts into the generic `gun.recoil` capability. Actual emitted
bullets inherit the free body's launch velocity and, for an offset rigid mount,
its tangential velocity. The body receives opposite muzzle-relative momentum,
using the existing radius-squared mass proxy scaled by projectile strength.
A firing line away from the centre produces angular impulse; the current centred
crawler gun therefore produces translation without extra spin. Volleys sum their
projectile impulses using one pre-volley launch velocity/spin.

Wall support absorbs recoil for attached crawlers. No impulse occurs from aiming,
a held trigger during reload, or an otherwise rejected shot. A real firing
impulse establishes ballistic flight even when initial placement had no wall;
it cannot be erased by that placement path on the next frame. Recoil pulling a
crawler away from a capture surface releases its landing plan and reservation.
Other landing and collision mechanics remain in effect.

The standard bullet (radius 3, relative speed 8) and crawler (radius 10) yield
0.72 pixels/frame of recoil per ordinary shot. There is no separate steering
controller or reward: direction and timing are policy choices with the existing
shot cost. Other creature guns retain their prior behaviour unless recoil is
explicitly enabled. Campaign and training share this mechanic. Continue from
run141/iter0041 without applying output damping again.

Run142 is training the recoil physics. All actor arrays in its saved initial
checkpoint exactly match run141/iter0041; the one-time damping setting was not
inherited. Validation covered 193 focused recoil, projectile, wall, movement,
reward, creature and combat checks. Tests include relative linear/angular
momentum, mass/strength scaling, rotating mounts, volleys, reload gating,
supported absorption, no-wall impulse persistence, capture release and actual
body clearance against real rock and steel.


### Battle incentives (scenario 55)

Battle drills reward survival and removing threats. Each crawler earns +0.1 per
living second, +20 if alive at the time limit, and −40 once on death. Destroying
a Jelly awards +5 to its final shooter, in addition to +1 per accepted hit
(a two-hit kill earns +7 before shot costs). Landings earn zero in battle and
aiming drills. The proximity launch bonus, incoming damage costs, recoil, and
movement controls remain as before. The hunter remains invulnerable; battle
success means surviving to the time limit. These rewards are individual, and
replay records each component. Continuation retains the learned actor weights.


### Terminal success and staged battles (scenario 56)

Battle success now terminates the episode rather than truncating it, so the critic
does not bootstrap beyond the +20 success bonus. Success means reaching the
horizon alive, or clearing all Jellies when no hunter is present. Only living
crawlers receive this once-per-trial bonus. Other reward magnitudes are unchanged.
The new continuation uses gamma 0.997 and GAE lambda 0.97 for longer credit assignment.

Training starts with one Jelly and no hunter, then progresses through two Jellies,
four Jellies, and four plus an armed hunter. Promotion requires at least 100 battle
trials with at least 50% crawler survival and 60% trial success. Evidence resets
after each evaluated block; failed blocks retain difficulty. Resume preserves
the stage and accumulated evidence. Full encounters remain in held-out evaluation.
The aiming schedule, actor schema, learning rate, physical controls, and reward
magnitudes remain unchanged.
