# 012: Turn rate for the neural student

Date: 2026-10-12. The student flies with left, right, thrust and fire only, taught by the rules pilot
(spec: `docs/superpowers/specs/2026-10-12-neural-student-design.md`). Does the ship's turn rate matter?

Method: for each turn rate, record 480 teaching episodes (seeds 100-139, tune levels), train round 0 (20 epochs),
fly the gate on the tune set, 6 seeds, 6 frames per decision. Reference: the rules pilot at its own turn rate (2.0).

| turn rate | score ratio | wall hits (x rules) | enemy hits (x rules) | validation agreement (turn / thrust / fire) |
|---|---|---|---|---|
| 0.5 | 0.18 | 8.5 | 4.5 | 85 / 91 / 99% |
| 1.0 | 0.36 | 7.9 | 3.6 | 82 / 90 / 99% |
| 2.0 | 0.38 | 6.6 | 3.5 | 83 / 90 / 99% |

Round 0 fails the gate at every rate: it kills about as fast as the rules pilot but hits walls and enemies several
times as often. 0.5 is clearly worst. 1.0 and 2.0 are within noise of each other on 6 seeds (0.36 against 0.38).

**Chosen: 1.0** (the owner's call; 2.0 was nominally best by 0.02). `neuralTurnRate` = 1.0.
