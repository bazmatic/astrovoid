# 007: Confident exploration (faster, longer-sighted wall-following)

Date: 2026-10-11. Parameters: `wall_follow_cruise` (default 0.6) and `wall_lookahead_cells` (0.75, newly
exposed). Base: the rules defaults with the investigate rule (see 005). Tune set, 18 seeds per level
(216 episodes per arm), paired.

## What was slow and cautious

With nothing to shoot or follow, the hunter wall-follows. Its speed was capped at about 0.6 x
sqrt(thrust x standoff), roughly 27 m/s against a speed limit of 480, and the point it steers for sits
only 0.75 of a maze cell ahead along the wall.

## Hypothesis and prediction

Faster and further-sighted wall-following finds enemies sooner: less idle time and a higher kill rate,
at some cost in wall hits.

## Results (candidate minus base, tune set)

| setting | score | kills, % per min | wall hits | enemy hits | idle |
|---|---|---|---|---|---|
| cruise 1.2 | +4.8 (-0.9 to +10.0) | +5.1 (+0.7 to +9.1) | +0.25 | +0.34 (+0.09 to +0.61) | -0.022 |
| cruise 2.0 | +4.3 (-1.4 to +10.4) | +4.8 (+0.9 to +9.0) | +0.57 (+0.21 to +0.90) | +0.07 | -0.023 |
| cruise 3.0 | +1.9 (-3.7 to +7.5) | +2.6 (-1.4 to +6.5) | +0.52 (+0.17 to +0.84) | +0.05 | -0.017 |
| look-ahead 1.5 | -0.6 (-5.8 to +4.6) | -0.5 | -0.08 | +0.07 | +0.001 |
| look-ahead 2.5 | +3.4 (-2.4 to +8.8) | +2.4 | -0.16 | +0.02 | -0.007 |
| cruise 1.2 + look-ahead 1.5 | +5.3 (-0.6 to +11.1) | +4.6 (+0.3 to +8.7) | +0.19 | +0.03 | -0.019 |
| **cruise 2.0 + look-ahead 2.5** | **+11.3 (+5.2 to +17.8)** | **+8.4 (+3.8 to +13.1)** | +0.11 | -0.06 | **-0.040 (-0.067 to -0.013)** |

Held-out set, scored once for the chosen setting (cruise 2.0 + look-ahead 2.5, 18 seeds, 108 episodes
per arm): **score +5.3 (+1.8 to +9.2)**, kills +3.3 points (+0.8 to +6.0), idle -0.028 (-0.045 to
-0.012), wall hits +0.03 and enemy hits +0.02 (both within noise).

## Interpretation

Speed alone and look-ahead alone each gave a gain that did not clear chance, and a faster cruise
costs wall hits. Together they are clearly better, which fits the mechanism: a hunter that sees further
along a wall can commit to long runs, and only a higher speed limit lets it use them. Seven settings
were tried, so the best tune estimate (+11.3) is optimistic; the held-out estimate (+5.3, about half)
is the one to believe. Wall hits and enemy hits did not rise beyond noise at the chosen setting.

## Decision

Adopted: `RULES` now sets `wall_follow_cruise` to 2.0 and `wall_lookahead_cells` to 2.5 (on top of the
investigate rule from 004). Jev and the student keep `DEFAULT`.

## New reference baseline (the rules defaults after this change)

6 seeds per level, 90 s horizon, frozen weights (as 001 and 005):

| term | tune mean | held-out mean |
|---|---|---|
| kills, % of all enemies per minute | 93.7 | 103.3 |
| kills per minute (raw, reported only) | 29.0 | 35.7 |
| wall hits per minute | 3.14 | 2.57 |
| hits taken per minute | 4.24 | 4.18 |
| idle fraction | 0.190 | 0.101 |
| **score** | **53.6** | **72.2** |

## Caveats

Hunter alone, player parked and hidden. The look-ahead and cruise were chosen from seven combinations,
not from a systematic search, so a better pair may exist. A faster hunter may behave differently
beside a moving player.
