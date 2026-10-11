# Rules lab notebook

Experiments that refine the rules hunter (`hunter/rules_pilot.py`). Design:
`docs/superpowers/specs/2026-10-11-rules-lab-design.md`.

## How to run

- `venv/bin/python -m experiments.lab baseline`: default rules on the tune and held-out sets.
- `venv/bin/python -m experiments.lab round1`: random search plus hill-climbing over the numbers
  in `hunter/rule_params.py`, then one held-out check.
- `venv/bin/python -m experiments.run --params FILE.json --set tune|heldout`: score any parameter
  file. Raw results go to `.astrovoid-local/experiments/` (not committed).

## Fixed conditions

Hunter alone, 1352x878, damage on, horizon 90 s, seeds 0 and 1. Tune levels 13, 14, 15, 17, 19,
20, 22, 25, 26, 27, 18, 30; held-out levels 16, 21, 23, 28, 29, 24 (scored once per round, never
used to choose). Score weights are frozen in `experiments/score.py`. A change counts only if the
paired 95% bootstrap interval on the tune set excludes zero.

## Entries

| # | experiment | tune score | held-out score | decision |
|---|---|---|---|---|
| 001 | [baseline](001-baseline.md) | -18.3 | -7.0 | reference |

Add an entry per experiment: hypothesis, prediction, change, results with all terms, decision.
