# Neural student, stage 3: learning from environmental feedback

Status: draft. Follows `2026-10-12-neural-student-design.md` (stages 1 and 2, built on `feat/neural-student`).

## Goal

Start from the shipped imitation policy (`assets/neural/hunter.npz`) and improve it with reinforcement learning, using
only what the game reports: kills, wall hits, enemy hits and idling. No rules pilot, no teacher, no labels.
Stage 2 left the policy killing as fast as the rules pilot but hitting walls about 6 times as often and enemies about
twice as often (held-out score 0.58 of the rules pilot's). Stage 3 aims to close that gap.

## Decisions (made with the owner)

- **Reward**: the lab's own score terms, per event, with the frozen weights. No new terms.
- **Method**: recurrent PPO fine-tuning of the existing GRU.
- **Success**: the original gate, scored once on held-out levels at 18 seeds: score at least 0.8 of the rules pilot's,
  wall hits and enemy hits at most 1.25 times its. Nothing is chosen using the held-out result.
- Decision rate (6 frames) and turn rate (1.0) stay fixed: the shipped policy was trained for them.

## Reward

Given at the moment each event happens, per episode:

| event | reward |
|---|---|
| a kill | +100 / (enemies at start + enemies spawned in that episode) |
| a wall hit | -3.4 |
| an enemy hit | -3.5 |
| each second idle | -77 / episode length in seconds, summed over the idle frames |

An episode's undiscounted return equals its lab score times its length in minutes (the lab's 45 s floor on short
episodes is ignored in training; the gate still uses the lab's score). The weights are `experiments.score.Weights`,
imported, never copied. Discount 0.99 per decision step and GAE lambda 0.95 are starting values, recorded in the
experiment notes if changed.

## Components

- `experiments/rollout.py`: flies the lab harness with a sampling `NeuralController` and a per-frame reward recorder,
  and returns per-decision-step senses, the sampled controls, their log-probabilities, the reward earned over the step,
  and an end-of-episode flag. Built from the harness's existing hooks (`recorder`, `on_result`) and the lab's event
  counter. Deterministic given the policy, the seed and the random generator seed.
- `tools/ppo_neural.py`: the learner. Loads the shipped `.npz` into the torch `TorchNet` (from `tools/train_neural.py`),
  runs iterations of rollouts across a worker pool, computes advantages (GAE) with a small learned value head, and
  updates with the PPO clipped objective on windows of 64 consecutive steps, the first 16 as unscored warm-up (as in
  stage 2). Adds a KL penalty towards the frozen imitation policy, fading over the first part of training. Saves the
  policy as the same `.npz` format; the value head is training-only and is not saved.
- `experiments/neural_lab.py`: unchanged; it is the judge. A `--sample` switch is not needed (the gate flies greedily).
- `NeuralController` already has `greedy` and `rng`; rollouts use `greedy=False` with a seeded generator.

## Training schedule

- An iteration is about 96 episodes (12 workers by 8) on the tune levels, seeds 300 to 399 (disjoint from teaching
  100-139, correction 200-239 and evaluation 0-17).
- Every few iterations the tune-set gate is flown greedily at 6 seeds; the best checkpoint by tune score is kept.
- Training stops when that check passes, or after a fixed iteration budget set after timing a first iteration.
- Checkpoints and logs go under `.astrovoid-local/neural/rl/`, not into git. Only the final policy is copied to
  `assets/neural/hunter.npz`, and only after the held-out gate has been run and recorded.

## Testing

- Rollout: deterministic for a seed; reward sums to the lab score times minutes on a recorded episode; end-of-episode
  flag set exactly once; log-probabilities match the policy's own softmax.
- Learner: on a toy environment where one action is rewarded, PPO raises its probability; the exported `.npz` loads
  with `NeuralPolicy.load` and matches the torch net's outputs (as the stage-2 parity test); the KL anchor holds the
  policy near the imitation policy when the reward is zero.
- Torch is a training-only dependency, as in stage 2.

## Experiments

1. Time one iteration; fix the iteration budget.
2. Baseline: the shipped policy sampled (not greedy) against greedy on the tune set, to see how much sampling alone
   costs.
3. Train; log the tune score, collision rates and KL every few iterations in `docs/experiments/015-neural-rl.md`.
4. Gate once on the held-out levels; record the result whether it passes or not.

## Risks

- Wall hits are the hardest term: the imitation stage never got below about 5 times the rules pilot's rate.
- The policy may learn to avoid everything and stop hunting. Guards: the idle term, the kill reward, and the KL
  anchor. Watch kills per minute alongside the collision terms in every log line.
- Compute: an episode takes seconds; training is hours, not minutes. Measured first (experiment 1).
- PPO on a sparse kill signal can be slow to move. If it stalls the finding is recorded and the options (a larger
  reward for clearance, a bigger network, more history) are a separate decision.

## Out of scope

Changing the senses, the network size, the decision rate, the game's rules, or learning inside the live game.
