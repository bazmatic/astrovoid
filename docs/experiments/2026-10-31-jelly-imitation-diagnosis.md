# Jelly imitation diagnosis — 2026-10-31

Run 152 is paused at iteration 42 at the user's request. No production behaviour was changed or training restarted during this investigation. The experimental policies below are debug artifacts, not installed models.

## Reproduction

The saved run152 bootstrap catches nothing in a fixed ten-second stage 1 episode on level 23/seed 900. Run 151's shorter bootstrap catches once in the same episode. This is a deterministic, small reproduction of the previously measured held-out collapse (0 versus 0.67 solo catches/minute across the three validation caves).

Harness: `.astrovoid-local/neural/experiments/imitation-debug-2026-10-31/repro.py`.

```sh
SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. ./venv/bin/python .astrovoid-local/neural/experiments/imitation-debug-2026-10-31/repro.py
```

Actual result: catches 0, seconds 10, reward approximately0; assertion fails with `saved imitation policy fails to catch a reachable target`. Adding `--run run151` catches 1 and passes. `--open` replaces the cave with an EMPTY 10-cell arena; `--teacher` follows the route teacher. The old saved policy and these experiment seeds are fixed. The original failure remains; this task was diagnosis, not a claim of a production fix.

## Ranked hypotheses and probes

1. **Demonstration difficulty/idle examples.** Prediction: simpler pursuit demonstrations or removing stalled trajectories should improve closed-loop behaviour. Thirteen of 64 episodes contain more than 99% braking actions; 52% of all actions brake. Filtering those 13 alone did not fix the cave repro. Empty-arena teaching improved open-arena pursuit.
2. **Demonstration fit is not closed-loop competence.** Prediction: an actor can match later teacher states but fail to accelerate from rest; additional passes will not necessarily improve rollout catching. This is observed below. The teacher also has a full-maze route that is not part of the student's local observation, so the evidence does not establish that all cave labels are inferable from those observations.
3. **Idle braking avoids the existing stuck penalty.** Prediction: explicitly holding the brake can yield no movement and no stuck charge. A ten-second level 23/seed 900 rollout with constant brake had movement 0 px, stuck_seconds 0, catches 0 and total reward about -2e-17. The stuck rule requires accelerating throughout its window; it does not charge stationary braking.

All comparisons below begin from the same run150/iter0048 checkpoint. Teacher data uses training seeds 100 onward; tests use unseen seeds 900 onward. Twenty passes, existing optimizer/learning rate, and unchanged observations/actions are used for the offline candidate fits.

## Controlled ten-second reproduction results

| Warm-start | Cave23/900 catches | Empty arena/900 catches |
|---|---:|---:|
| Existing 8 cave episodes × 4 passes (run151 bootstrap) |1|1|
| Existing 64 cave episodes × 20 passes (run152 bootstrap) |0|0|
| First 8 cave episodes × 20 passes |0|0|
| 51 cave episodes × 20 passes, removing 13 idle-only episodes |0|0|
| 8 empty-arena episodes × 20 passes |0|1|

The last two interventions distinguish stalled demonstrations from task difficulty: removing only idle trajectories is insufficient, whereas simpler demonstrations help the corresponding simpler task. Neither is a demonstrated cave solution.

## Empty-arena holdout check

Three unseen seeds, ten seconds each, same moving targets/rewards/body physics. Catches per seed:

| Actor |900|901|902|
|---|---:|---:|---:|
| Short cave warm-start |1|0|0|
| Long cave warm-start |0|0|0|
| Empty-arena warm-start |1|1|0|
| Teacher |1|2|1|

This small check is promising evidence for an easier first lesson, not a statistically established training improvement. It says nothing about team coordination or ship combat.

## Why imitation loss was misleading

On their own recorded teacher trajectories:

| Measure | Short warm-start | Long warm-start |
|---|---:|---:|
| Acceleration-sign agreement across all steps |85.2%|94.6%|
| Teacher accelerates at episode start |87.5%|78.1%|
| Student accelerates at episode start |37.5%|20.3%|
| Mean circular heading error |57.8°|21.5°|

The long warm-start fits recorded trajectories better while failing more starts. This isolates an important failure pattern: good predictions on teacher-visited moving states do not guarantee that the closed-loop student will leave rest and reach those states. It does not prove one unique optimizer or representation cause.

## Recommended next change

1. Teach a solo Jelly to accelerate, steer, and repeatedly catch a target in an empty arena. Use shorter varied episodes to provide more starts. Evaluate on held-out empty-arena seeds, with cave evaluation reported separately.
2. Introduce a simple barrier. Give the teacher a wall-following/exploration fallback instead of indefinite braking when routing fails. Validate target reachability; wall-following cannot solve genuinely disconnected pockets.
3. Add caves gradually after simple pursuit and obstacle navigation work. Keep this navigation curriculum distinct from the existing solo/team/ship-fight stages.
4. If adding boredom, penalize sustained lack of movement independently of the acceleration command, with a grace period. Do not penalize every temporary increase in straight-line target distance: valid wall-following detours can move away from the target.

Do not spend another long run merely increasing imitation epochs on the same difficult cave lessons. The evidence supports redesigning the initial lesson and checking closed-loop behaviour before launching PPO again.

## Artifacts and cleanup

Throwaway scripts/results/checkpoints are retained only under the explicitly named `.astrovoid-local/neural/experiments/imitation-debug-2026-10-31/` folder (`compare.py`, `results.json`, `open_holdout.py`, `open-holdout.json`, `fit_metrics.py`). No debug logging or experiment code was added to production modules. The paused run and its checkpoints are unchanged. No new production regression test is claimed: a concrete fix has not yet been selected.
