# 004: Investigate where a remembered enemy was last seen

Date: 2026-10-11. Switch: `investigate_memory`. Base: 001 (all switches off).

## Hypothesis and prediction

When no enemy is in sight but one was seen in the last 10 seconds, the hunter wall-follows instead of
going back to where the enemy was. Heading for the nearest remembered enemy's last position should
cut idle time and raise the kill rate, without more wall or enemy hits.

## Results

| run | score | kills, % per min | idle fraction | wall hits | enemy hits |
|---|---|---|---|---|---|
| tune, 6 seeds (72 episodes) | +6.7 (-0.7 to +14.4) | +3.3 (-2.4 to +9.2) | -0.030 (-0.068 to +0.009) | -0.157 | -0.146 |
| tune, 18 seeds (216 episodes) | **+4.7 (+1.1 to +8.8)** | **+2.9 (+0.2 to +6.0)** | **-0.022 (-0.042 to -0.005)** | -0.037 | +0.009 |
| held-out, 18 seeds (108 episodes) | **+4.6 (+0.8 to +9.2)** | **+3.9 (+1.0 to +7.2)** | -0.015 (-0.036 to +0.004) | -0.010 | +0.123 (-0.012 to +0.300) |

(Differences are candidate minus base; intervals are paired 95% bootstrap. All three rows were produced
after the harness fixes described in 001 and the later counter fix, so they are current.) Base scores at
18 seeds: 44.3 on tune and 52.0 on held-out.

Note on the procedure: the 6-seed look was inconclusive and the comparison was then repeated with 18
seeds (which include seeds 0 to 5). That is optional stopping, so the tune result alone would be weak
evidence; the held-out set, scored once and never used to choose, is the confirmation.

## Interpretation

The 6-seed run pointed the right way on every term but could not rule out chance, so the same
comparison was repeated with 18 seeds. There it clears zero on the tune set for the score, kill rate and
idle time, and the held-out set (scored once, never used to choose) agrees. Wall hits and enemy hits
did not get worse beyond noise (enemy hits +0.12 per minute on held-out, interval -0.01 to +0.30), so
the gain is not from recklessness. The effect is modest, about 11% of the score, and consistent with
the mechanism: less time idle, more kills.

## Decision

Adopted for the rules pilot. `hunter/rule_params.py` now has `RULES` (`DEFAULT` plus
`investigate_memory=True`), which `RulesClient` and the lab use by default. Jev and the student keep
`DEFAULT` because Jev's instructions do not know about the new block. `JevPilot` takes its parameters
from a client that carries them.

## Caveats

Tested with the player parked and hidden only; behaviour with a moving player is not measured. The
rule uses the perception's 10-second memory of enemies, so it helps only when an enemy was seen
recently.
