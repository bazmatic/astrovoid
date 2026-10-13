# 014: Teacher-corrected rounds, and the gate

Date: 2026-10-12. At turn rate 1.0, 6 frames per decision. Each round: the student flies tune levels (seeds
200-239), the rules pilot relabels every state it reaches (round 1 executes the teacher's choice on 30% of steps),
and training continues from the last policy on the teaching set plus every round so far (10 epochs).
Gate on the tune set, 6 seeds.

| round | score ratio | wall hits (x rules) | enemy hits (x rules) |
|---|---|---|---|
| 0 | 0.36 | 7.9 | 3.6 |
| 1 | 0.83 | 5.7 | 1.32 |
| 2 | 0.72 | 4.7 | 2.1 |
| 3 | 0.71 | 6.1 | 1.7 |
| 4 | 0.75 | 5.2 | 1.8 |
| 5 | 0.78 | 5.0 | 1.75 |

Five rounds did not pass the gate (score at least 0.8, collisions at most 1.25 times the rules pilot). The score
ratio reached 0.83 in round 1 and then did not improve; wall hits fell from 7.9 to about 5 and stayed there.
Per-step validation agreement stayed near 82% turn, 85% thrust, 99% fire throughout, and says nothing about flying.

Likely cause, not tested: the rules pilot avoids walls with solved quantities (safe speed, stopping distance) that
the student only has as raw wall-ray distances and its own speed. Learning that braking rule from imitation alone
is the hard part.

**Held-out gate, 18 seeds, round 1 policy (run once, nothing chosen from it):** score 55.6 against 95.6, ratio 0.58;
wall hits 6.3 per minute against 1.06 (5.9 times); enemy hits 4.6 against 2.2 (2.1 times); kills 38.4 against 33.5
per minute. **Gate FAILED.** The owner accepted the result and moved on: the policy is the starting point for
learning from environmental feedback alone (stage 3, a separate spec), which has the collision terms to work on.
Shipped as `assets/neural/hunter.npz`.
