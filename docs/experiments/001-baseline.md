# 001: Baseline

Date: 2026-10-11. Code: branch `feat/rules-lab` (rules pilot, default `RuleParams`).

## Setup

- Scenario: hunter alone (player parked and hidden), 1352x878, horizon 90 simulated seconds.
- The hunter is **indestructible**, as in the game. Episodes end when every enemy is dead or at the
  horizon. Hits are counted at the damage path, one per 0.5 s window.
- Tune set: levels 13, 14, 15, 17, 19, 20, 22, 25, 26, 27, 18, 30. Held-out set: 16, 21, 23, 28, 29, 24.
  Seeds 0 to 5 per level: 72 tune and 36 held-out episodes. Rates use a 45 s floor on the episode
  length.
- Parameters: all defaults (`hunter/rule_params.py`). Run: `python -m experiments.lab baseline`
  (108 episodes in 52 s on 12 cores).

## Results

| term | tune mean | held-out mean | std over all 108 |
|---|---|---|---|
| kills, % of all enemies per minute | 85.2 | 93.7 | 33.8 |
| kills per minute (raw, reported only) | 26.3 | 30.9 | 24.3 |
| wall hits per minute | 3.24 | 2.81 | 5.15 |
| hits taken per minute | 4.37 | 3.94 | 4.96 |
| idle fraction | 0.246 | 0.168 | 0.223 |
| **score** (frozen weights) | **41.0** | **58.3** | |

How the 108 episodes ended: 53 cleared the level, 55 reached the horizon.

## Weights

By the spec's rule (each penalty's weight is 0.5 x std(kills, % per minute) / std(that term), over
the baseline episodes): wall 3.3, hit 3.4, idle 76 (two significant figures). Frozen in
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
- **Half the episodes do not finish.** 55 of 108 reach the 90 s horizon with enemies left, and idle
  time is 22% of the episode on average (up to two thirds of the episode on some level 30 seeds). Finding enemies is
  likely a bigger lever than shooting them.
- **Boss levels differ.** Levels 18 and 24 (small mazes, eggs and children) clear quickly with 4 to 11
  hits taken; level 30 is the opposite, mostly idle.

## Revision note

This baseline was redone twice after changes to the lab: the death term was dropped (indestructible
hunter), kills became a share of all enemies, and then the comparison was strengthened with six seeds
per level and a 45 s rate floor (the 24-episode version could not detect effects smaller than about
10 to 50 score points; see 002). The numbers above are the current ones.
