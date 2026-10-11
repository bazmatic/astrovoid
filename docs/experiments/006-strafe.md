# 006: Strafe (dodge sideways between aimed bursts)

Date: 2026-10-11. Switch: `strafe` (+ `strafe_cells`). Base: the rules defaults (005 / `RULES`), tune
set, 18 seeds per level (216 episodes per arm), paired.

## What "strafe" can mean here

The engine thrusts only along the nose, and `track` holds the nose on the target, so the hunter cannot
slide sideways while aiming. The version tested is a dodge in bursts: right after a `track` decision,
with an enemy aimed at and the hunter not braking, swing the nose aside for one decision and burn a
lateral nudge toward a point `strafe_cells` of maze cells to the side, then track again. That
alternates aiming and dodging every other decision, and it keeps the trigger held (shots only release
when the nose is on target).

## Hypothesis and prediction

Moving sideways makes the hunter harder to hit. Prediction: fewer enemy hits per minute, at a small
cost to the kill rate, with some risk of more wall hits.

## Results (candidate minus base, tune set; every interval excludes zero)

| variant | score | kills, % per min | wall hits | enemy hits | idle |
|---|---|---|---|---|---|
| side with more room, 1.0 cell | -36.8 (-44.9 to -29.1) | -22.6 | +1.9 | +3.6 | -0.063 |
| side with more room, 0.3 cell | -50.1 (-58.7 to -41.9) | -24.2 | +5.4 | +3.9 | -0.076 |
| against current drift, 1.0 cell | -41.4 (-49.8 to -33.2) | -23.7 | +2.5 | +3.9 | -0.058 |

Base: score 49.0, kills 89.4 %/min, wall hits 2.9, enemy hits 4.1, idle 0.210.

## Interpretation

The prediction was wrong in direction: enemy hits roughly doubled (4.1 to about 8.0 per minute) as well
as wall hits rising, and the kill rate fell by about a quarter. Only idle time improved. A smaller dodge
did not help, and dodging against accumulated sideways drift (so the nudges cancel) did not rescue it,
so drift alone is not the explanation. A likely cause, not tested: swinging the nose off the target
every other decision halves the time the guns can fire, so enemies live longer and reach the hunter.
Dodging unconditionally is the problem; there is no evidence about dodging only when a bullet is
actually coming.

## Decision

Rejected; `strafe` stays off (and is left in `RuleParams` so the result can be reproduced).

## Next

A narrower hypothesis: dodge only in response to a threat, for example when a hostile projectile is
heading for the hunter (the state lists `hostile_projectiles` with bearings and distances) or an enemy
is very close. That keeps the guns on target the rest of the time.
