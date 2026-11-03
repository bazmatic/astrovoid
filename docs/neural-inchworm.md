# Neural inchworm: implemented controller and planned training

Training has **not been started**. No inchworm checkpoint is installed. The
configuration is saved in [config/training/inchworm.json](../config/training/inchworm.json)
for use after the Flocker work finishes. Validation uses inference fixtures,
short physical simulations, and recorded-action replay, without optimizer steps.

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
an all-zero externally supplied command overrides both policy and reflex control.
Each creature owns separate recurrent memory; an encounter shares loaded weights.

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

## Proposed first run

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
result. The demonstration and PPO code is prepared but has not run.

The task appears as **Inchworm** in the trainer. Its fresh defaults match the
saved settings. It needs no frozen Hunter opponent: the first curriculum teaches
body control and feeding on physically movable targets, not combat against an
armed ship. The shared trainer skips opponent copying for this task.

After authorization to start, the equivalent CLI recipe is:

```sh
venv/bin/python -m tools.ppo_neural --task inchworm \
  --out .astrovoid-local/neural/inchworm-pilot \
  --seed 0 --workers 4 --episodes 24 --horizon 45 \
  --iterations 5000 --budget-seconds 7200 \
  --bootstrap-episodes 40 --bootstrap-epochs 4 \
  --lr 0.0001 --gamma 0.997 --gae-lambda 0.97
```

The JSON is a settings recipe, not an auto-running job. The command above has
not been executed. To continue a run later, use its recorded settings and
`--resume --out RUN`; resume validates schemas, reward settings and physical rules.

## Curriculum and pass criteria

| Lesson | Physical objective | Held-out success gate |
| --- | --- | --- |
| 1. Crawl | Reach a marker 60–90 px ahead while attached | 80% |
| 2. Turn | Curl, twist, transfer grip, unfold and advance toward a marker behind; head must face the new direction | 80% |
| 3. Reach | Rear toward an elevated target and maintain actual mouth contact with rear support | 80% |
| 4. Feed | Deliver two actual health-reducing bites | 75% |
| 5. Recover | Grasp a slowly evasive target, withstand a scheduled shove, regain support and deliver two subsequent bites | 65% |

The environment uses real Creature/Encounter traits and the same articulated
solver as play. No stage teleports feet or prey. Stage 5's target receives small
physical evasive/restoring accelerations and the worm receives a real impulse.
Success is measured from physical pose, contacts and accepted damage.

Training surfaces rotate through four cardinal orientations. Validation uses
four different diagonal orientations and 12 fixed cases per lesson. Promotion
requires two consecutive passing validation blocks, with full survival. Validation
runs every five iterations. Each later training stage retains earlier drills in
one-quarter of its episodes to limit forgetting. Seed sets are separate for
training, validation, bootstrap and final evaluation.

Final evaluation uses another four held-out orientations, 12 cases per lesson,
and paired reflex baselines. A deployment pass requires every lesson's success
gate and a paired 95% bootstrap lower bound of at least -0.05 for success-rate
change versus the reflex controller. An incomplete comparison fails. No result
automatically installs a policy; the report records the evaluated checkpoint hash.
An early-stage best checkpoint is not deployment approval.

## Reward accounting

| Signal | Coefficient / units |
| --- | --- |
| Signed reduction in goal or mouth-to-target distance | +0.04 per pixel; increases in distance subtract equally |
| Actual bite damage | +2 per accepted bite |
| Lesson success | +4 once, then terminate |
| Death | -5 once, then terminate |
| Mean muscle effort | -0.03 per second at full effort |
| No planted grip | -0.08 per second, excluding forced stun |
| Elapsed time | -0.002 per second |
| Motor-command change | -0.01 times mean squared change per decision |

Progress is a telescoping potential. Oscillating, releasing and regripping do not
reset a progress bonus. Holding alone earns nothing; feeding rewards require real
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
