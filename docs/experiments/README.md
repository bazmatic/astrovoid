# Rules lab notebook

Experiments that refine the rules hunter (`hunter/rules_pilot.py`). Design:
`docs/superpowers/specs/2026-10-11-rules-lab-design.md`.

## How to run

- `venv/bin/python -m experiments.lab baseline [--baseline-of default]`: the rules defaults (or the
  global ones) on the tune and held-out sets.
- `venv/bin/python -m experiments.lab compare --candidate steer_band_degrees=25 --set tune --seeds 18`:
  paired comparison of a candidate against the current rules defaults (`RULES`), per term; `--base`
  takes overrides too (for example `--base investigate_memory=false`). Use
  `--set heldout` once, at the end.
- `venv/bin/python -m experiments.lab round1`: random search plus hill-climbing over the numbers
  in `hunter/rule_params.py`, then one held-out check.
- `venv/bin/python -m experiments.run --params FILE.json --set tune|heldout`: score any parameter
  file. Raw results go to `.astrovoid-local/experiments/` (not committed).

## Fixed conditions

Hunter alone and indestructible (as in the game), 1352x878, horizon 90 s, seeds 0 to 5 (72 tune, 36 held-out episodes). Tune levels 13, 14, 15, 17, 19,
20, 22, 25, 26, 27, 18, 30; held-out levels 16, 21, 23, 28, 29, 24 (scored once per round, never
used to choose). Score weights are frozen in `experiments/score.py`. A change counts only if the
paired 95% bootstrap interval on the tune set excludes zero.

## Entries

| # | experiment | tune score | held-out score | decision |
|---|---|---|---|---|
| 001 | [baseline, global defaults](001-baseline.md) | 41.9 | 58.0 | reference for 004 |
| 002 | [round 1 numeric search](002-round1-numeric-search.md) | no move accepted | n/a | superseded (pre-fix lab; too few seeds) |
| 003 | [pursue unaimed](003-pursue-unaimed.md) | +0.0 | n/a | rejected: the switch never fires |
| 004 | [investigate memory](004-investigate-memory.md) | +4.7 | +4.6 | **adopted** as `RULES` |
| 005 | [baseline, rules defaults](005-baseline-rules.md) | 48.6 | 65.7 | current reference |
| 006 | [strafe](006-strafe.md) | -36.8 to -50.1 | n/a | rejected: more hits, fewer kills |

Add an entry per experiment: hypothesis, prediction, change, results with all terms, decision.

Intervals are paired bootstraps over episodes and describe the 12 tune (or 6 held-out) levels; they do
not account for levels being sampled from a larger population, so the held-out set is the real check on
generalisation. When a comparison is repeated with more seeds after an inconclusive first look (as in 004),
say so in its entry, because that is optional stopping.
