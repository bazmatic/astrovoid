# 005: Current baseline, the rules defaults

Date: 2026-10-11. Parameters: `RULES` (the global defaults plus `investigate_memory`, adopted in 004).
Run: `python -m experiments.lab baseline` (the default is the rules defaults). Same conditions and frozen
weights as 001: 72 tune and 36 held-out episodes, 6 seeds per level, 90 s horizon.

| term | tune mean | held-out mean |
|---|---|---|
| kills, % of all enemies per minute | 89.8 | 100.0 |
| kills per minute (raw, reported only) | 29.6 | 34.9 |
| wall hits per minute | 3.28 | 2.74 |
| hits taken per minute | 4.45 | 4.21 |
| idle fraction | 0.188 | 0.133 |
| **score** | **48.6** | **65.7** |

This is the reference for new experiments: `lab compare` measures a candidate against these rules.
Compared with 001 (all switches off) the score is about +6.7 on tune and +7.7 on
held-out at 6 seeds, in line with the 18-seed comparison in 004.
