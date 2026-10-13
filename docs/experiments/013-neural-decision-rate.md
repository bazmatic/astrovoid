# 013: Decision rate for the neural student

Date: 2026-10-12. How often the student decides (frames per decision) at turn rate 1.0, tune set, 6 seeds.

| frames per decision | round 0 | round 1 | round 2 | round 3 |
|---|---|---|---|---|
| 6 (10 a second) | 0.36 | 0.83 | 0.72 | 0.71 |
| 3 (20 a second) | 0.53 | 0.89 | 0.73 | 0.83 |

Score ratio against the rules pilot. Wall hits stayed 3.7 to 7.9 times the rules pilot's in every cell; enemy hits
1.3 to 2.8 times. Three frames looks slightly better on score but not clearly so on 6 seeds. The 18-seed
comparison and the 1-frame arm were not run (stopped by decision: the owner chose to keep the 6-frame arm).

**Chosen: 6 frames.** `neuralDecisionFrames` = 6. Unexplored: 1 frame per decision.
