# 002: Round 1, numeric search

> **Superseded in detail.** This run predates the harness fix described in `001-baseline.md`
> (a mid-episode hunter re-summon made results depend on machine speed and undercounted hits).
> Its conclusion, that 24 episodes could not detect small effects, still stands and was the reason
> for the six-seed design, but its numbers should not be quoted. Redoing it on the fixed lab is
> listed as a follow-up.

Date: 2026-10-11. Baseline: 001. Search: `python -m experiments.lab round1` (12 minutes on 12 cores).

## Hypothesis and prediction

The default numbers in `RuleParams` are not optimal for the score. Prediction: random search plus
one-parameter hill-climbing finds at least one setting that beats the baseline on the tune set
(paired 95% interval above zero), and the held-out set agrees.

## What was done

40 random candidates screened on 12 short tune episodes (seed 0, 45 s), the best four ranked on
the full tune set (24 episodes, 90 s), then one hill-climbing sweep (each parameter up and down by
15%) from the baseline, since no random candidate beat it.

## Result

- **No random candidate** beat the baseline, so hill-climbing started from the defaults.
- **None of the 20 hill-climbing moves was accepted.** Best parameters = defaults; the held-out
  comparison was baseline against itself (+0.000).
- The intervals are wide. Half-widths of the paired 95% interval ranged from about 3 points
  (`far_ratio`, `cruising_speed_fraction`, `too_close_ratio` down) to about 50 points
  (`engage_standoff_cells`, `request_interval`), against a baseline tune score of 10.4. Examples:

| move | mean difference | 95% interval |
|---|---|---|
| `harmless_speed` 15 to 12.75 | -7.1 | -16.2 to -0.7 (reliably worse) |
| `steer_band_degrees` 20 to 17 | +4.0 | -1.0 to +12.0 |
| `request_interval` 0.25 to 0.2875 | +26.8 | -8.2 to +64.5 |
| `engage_standoff_cells` 1.5 to 1.725 | +21.2 | -28.4 to +71.8 |

## Interpretation

Not "the defaults are optimal": the test is too weak to say. Changing almost any parameter makes
the episode take a different course (different shots, different spawns), so the paired difference
is large noise, not a small shift. Two moves had positive means with intervals that nearly clear
zero (`steer_band_degrees` 17, `request_interval`); one was reliably worse (`harmless_speed` down),
which is mild evidence that value is near a good setting. With 24 episodes the lab can detect only
differences of roughly 10 to 50 score points, far larger than the effects numeric tweaks are likely
to have.

## Decision

Defaults unchanged. Round 1 shows the lab works end to end (search, acceptance rule, held-out
check) but does not yet have the statistical power to tune numbers.

## Next

1. **More episodes per comparison.** 6 seeds per level (72 tune episodes) would cut the intervals by
   about 40%; 12 seeds would halve them. Episodes cost about 0.5 s each, so a full evaluation of 144
   episodes is about 1 minute on 12 cores.
2. **Reduce score variance.** The kill-rate floor (20 s) makes very quick clears score up to 300%/min;
   a capped or log-scaled kill term would make the score less jumpy.
3. **Spend effort on structure, not numbers.** The baseline shows 18 of 36 episodes not finishing and
   about a fifth of the time idle. A hypothesis-driven change (for example: when no enemy is
   visible, search where one was last seen) is likelier to move the score by more than the noise.
