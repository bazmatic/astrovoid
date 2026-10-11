# 001: Baseline

Date: 2026-10-11. Code: branch `feat/rules-lab` (rules pilot, default `RuleParams`).

## Setup

- Scenario: hunter alone (player parked and hidden), 1352x878, horizon 90 simulated seconds.
- The hunter is **indestructible**, as in the game. Episodes end when every enemy is dead or at the
  horizon. Hits are counted at the damage path, one per 0.5 s window.
- Tune set: levels 13, 14, 15, 17, 19, 20, 22, 25, 26, 27, 18, 30. Held-out set: 16, 21, 23, 28, 29, 24.
  Seeds 0 and 1 per level: 24 tune and 12 held-out episodes.
- Parameters: all defaults (`hunter/rule_params.py`). Run: `python -m experiments.lab baseline`
  (36 episodes in 27 s on 12 cores).

## Results

| term | tune mean | held-out mean | std over all 36 |
|---|---|---|---|
| kills per minute | 29.9 | 46.1 | 32.4 |
| wall hits per minute | 2.81 | 3.51 | 3.71 |
| hits taken per minute | 4.60 | 5.13 | 5.18 |
| idle fraction | 0.215 | 0.122 | 0.213 |
| **score** (frozen weights) | **-13.1** | **5.4** | |

How the 36 episodes ended: 18 cleared the level, 18 reached the horizon.

## Weights

By the spec's rule (each penalty's weight is 0.5 x std(kills per minute) / std(that term), over
the baseline episodes): wall 4.4, hit 3.1, idle 76 (two significant figures). Frozen in
`experiments/score.py`; not changed during a comparison.

## History: the first baseline had damage switched on

The first version of the lab made the hunter destructible (3 health) and scored deaths, so that
enemy hits would cost something. Its baseline showed the hunter destroyed in 61% of episodes, often
within 6 to 10 simulated seconds on levels 26 to 29. That was a lab artefact, because the real
hunter cannot die. It also cut episodes short and made the score lumpy, so the lab was changed to
the indestructible definition above (no death term). A control run showed the kill counter itself is
sound: with the hunter forced to do nothing, 0 enemies died in 6 of 6 cases.

## Findings

- **Kill farming inflates some rates.** On levels 27 and 29 the hunter is credited with 125 and 183
  kills against 26 and 27 enemies at the start, because lighthouses keep spawning flockers. Such
  episodes dominate the kill-rate spread (std 32 on a mean of 35) and so raise the weights above
  what a typical episode would suggest. Comparisons are paired per episode, which cancels the
  level's scale, but watch for these episodes in any result.
- **Half the episodes do not finish.** 18 of 36 reach the 90 s horizon with enemies left, and idle
  time is 18% of the episode on average (up to 66 of 90 s on level 30 seed 0). Finding enemies is
  likely a bigger lever than shooting them.
- **Boss levels differ.** Levels 18 and 24 (small mazes, eggs and children) produce 18 to 51 kills in
  under a minute with 4 to 11 hits taken; level 30 is the opposite (6 to 17 kills, mostly idle).
