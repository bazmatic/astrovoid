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
| kills, % of all enemies per minute | 105.4 | 120.4 | 70.9 |
| kills per minute (raw, reported only) | 30.0 | 46.1 | 32.3 |
| wall hits per minute | 2.81 | 3.51 | 3.71 |
| hits taken per minute | 4.61 | 5.13 | 5.18 |
| idle fraction | 0.216 | 0.122 | 0.206 |
| **score** (frozen weights) | **10.4** | **31.0** | |

How the 36 episodes ended: 18 cleared the level, 18 reached the horizon.

## Weights

By the spec's rule (each penalty's weight is 0.5 x std(kills, % per minute) / std(that term), over
the baseline episodes): wall 9.6, hit 6.8, idle 170 (two significant figures). Frozen in
`experiments/score.py`; not changed during a comparison.

## History: the first baseline had damage switched on

The first version of the lab made the hunter destructible (3 health) and scored deaths, so that
enemy hits would cost something. Its baseline showed the hunter destroyed in 61% of episodes, often
within 6 to 10 simulated seconds on levels 26 to 29. That was a lab artefact, because the real
hunter cannot die. It also cut episodes short and made the score lumpy, so the lab was changed to
the indestructible definition above (no death term). A control run showed the kill counter itself is
sound: with the hunter forced to do nothing, 0 enemies died in 6 of 6 cases.

## Findings

- **Kills are scored as a share of all enemies.** The first version of the metric used raw kills per
  minute. Lighthouses and egg-laying bosses keep spawning enemies, so on levels 27 and 29 the hunter
  was credited with 125 and 183 kills against about 26 at the start, and those episodes dominated the
  spread. The score now uses the percentage of all enemies that existed (start plus spawned) killed
  per minute; on those levels it is 57 to 120 %/min, in line with the rest. Raw kills per minute is
  still reported.
- **Half the episodes do not finish.** 18 of 36 reach the 90 s horizon with enemies left, and idle
  time is 18% of the episode on average (up to 66 of 90 s on level 30 seed 0). Finding enemies is
  likely a bigger lever than shooting them.
- **Boss levels differ.** Levels 18 and 24 (small mazes, eggs and children) clear quickly with 4 to 11
  hits taken; level 30 is the opposite, mostly idle.
