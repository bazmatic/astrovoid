# 001: Baseline

Date: 2026-10-11. Code: branch `feat/rules-lab` (rules pilot, default `RuleParams`).

## Setup

- Scenario: hunter alone (player parked and hidden), 1352x878, damage on
  (`indestructible=False`, 3 health), horizon 90 simulated seconds.
- Tune set: levels 13, 14, 15, 17, 19, 20, 22, 25, 26, 27, 18, 30. Held-out set: 16, 21, 23, 28, 29, 24.
  Seeds 0 and 1 per level, so 24 tune and 12 held-out episodes.
- Parameters: all defaults (`hunter/rule_params.py`). Run: `python -m experiments.lab baseline`
  (36 episodes in 13 s on 12 cores).

## Results

| term | tune mean | held-out mean | std over all 36 |
|---|---|---|---|
| kills per minute | 23.8 | 42.4 | 21.7 |
| wall hits per minute | 2.64 | 3.35 | 3.84 |
| hits taken per minute | 5.07 | 6.77 | 3.64 |
| idle fraction | 0.142 | 0.060 | 0.205 |
| died | 0.54 | 0.75 | 0.49 |
| **score** (frozen weights) | **-18.3** | **-7.0** | |

How episodes ended over all 36: 22 died, 8 cleared the level, 6 reached the horizon.

## Weights

By the spec's rule (each penalty's weight is 0.5 x std(kills per minute) / std(that term), over
the baseline episodes): wall 2.8, hit 3.0, idle 53, death 22 (two significant figures). They are
frozen in `experiments/score.py` and are not changed during a comparison.

## Findings

- **The hunter usually dies.** With damage on it is destroyed in 61% of episodes (54% tune, 75%
  held-out), often within 6 to 10 simulated seconds on levels 26 to 29, where 25+ enemies start
  near it. So "not getting hit" is the largest headroom, more than finding enemies.
- **The kill counter is valid.** Control run: with the hunter forced to do nothing (no fire,
  coasting), 0 enemies died in 6 of 6 cases, so every counted kill is the hunter's. The idle
  hunter itself died in 4 to 7 s on those levels.
- **Kill rate is dominated by the level and by early clears.** Rates use a 20 s floor, so a fast
  clear scores a very high rate. The tune and held-out means differ mostly because of the level
  mix (the held-out set has a fast boss level, 24). Comparisons must stay paired by episode, which
  the search does.
- **Deaths end episodes early.** A hunter that dies at 8 s has few chances to idle or hit walls;
  the death term (22) is there so that does not look like a good run.
