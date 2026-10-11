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
| kills, % of all enemies per minute | 86.3 | 94.0 | 34.8 |
| kills per minute (raw, reported only) | 26.7 | 31.5 | 24.3 |
| wall hits per minute | 3.44 | 2.85 | 5.13 |
| hits taken per minute | 4.60 | 3.97 | 4.93 |
| idle fraction | 0.232 | 0.163 | 0.224 |
| **score** (frozen weights) | **40.4** | **57.7** | |

How the 108 episodes ended: 53 cleared the level, 55 reached the horizon.

## Weights

By the spec's rule (each penalty's weight is 0.5 x std(kills, % per minute) / std(that term), over
the baseline episodes): wall 3.4, hit 3.5, idle 78 (two significant figures). Frozen in
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
  time is 21% of the episode on average (up to two thirds of the episode on some level 30 seeds). Finding enemies is
  likely a bigger lever than shooting them.
- **Boss levels differ.** Levels 18 and 24 (small mazes, eggs and children) clear quickly; level 30 is
  the opposite, mostly idle.

## Revision note (a harness bug, found and fixed)

After the first comparisons on this baseline, two episodes of the same level and seed gave different
results in different runs (10 of 72 differed). The cause was in the lab, not the hunter: picking up a
Jev beacon re-summoned the hunter mid-episode. The new hunter's controller used the real clock, so
results depended on machine speed, and the harness kept counting the old hunter, so hits and wall
hits after the re-summon were not counted at all. Each episode now keeps its one hunter and one
simulated clock (and raises if the hunter is ever replaced), and two parallel runs of 72 episodes now
match exactly. Every number in this file and in 002 was produced before the fix; this file has been
redone, and 002 has not (see its note).

## Earlier revisions

This baseline was redone twice after changes to the lab: the death term was dropped (indestructible
hunter), kills became a share of all enemies, and then the comparison was strengthened with six seeds
per level and a 45 s rate floor (the 24-episode version could not detect effects smaller than about
10 to 50 score points; see 002). The numbers above are the current ones.
