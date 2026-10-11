# 008: The hunter's thrust

Date: 2026-10-11. Setting: `HunterSettings.thrust_multiplier` (the hunter's engine as a share of the
player's; today 0.25). Lab parameter: `thrust_multiplier`. Base: the rules defaults (`RULES`, as in 007).
The player's own ship is never touched; the setting is shared by every pilot of the hunter.

## Aim

Make the hunter as powerful as possible, so find the best thrust, with no cap at the player's.

## Sweep (candidate minus 0.25, tune set, 6 seeds = 72 episodes per arm)

| thrust | 0.15 | 0.25 | 0.35 | 0.4 | 0.5 | 1.0 | 1.5 | 2.0 | 4.0 | 6.0 |
|---|---|---|---|---|---|---|---|---|---|---|
| score | +8.6 | 0 | +11.0 | +5.2 | **+16.1** | +6.3 | **+12.6** | +0.4 | +1.6 | **-16.5** |

Bold = interval excludes zero. The curve zigzags, and even a weaker engine (0.15) scores positive, so it
is not a clean hill: a likely cause is that the 72-episode base happened to sit below its true mean, which
makes nearly every candidate look better.

## Confirmation (18 seeds = 216 episodes per arm)

| thrust | score | kills, % per min | idle | wall hits | enemy hits |
|---|---|---|---|---|---|
| 0.35 | +4.6 (-2.6 to +11.3) | +1.4 | -0.021 | -0.33 | -0.12 |
| 0.5 | +3.7 (-4.3 to +11.3) | +3.4 | -0.035 | +0.62 | +0.07 |

Both shrank to within noise: the +16.1 at 0.5 was a lucky draw. Thrust between 0.15 and about 1.5 makes no
measurable difference; above about 2 wall hits climb by 1.3 per minute, and 6.0 is reliably worse.

## Trying 1.0 anyway (a decision, then measured)

Thrust was set to 1.0 on request and the code adapted to it:
- The wall-follow cruise is a share of sqrt(thrust x standoff), so a 4x engine doubled the pace by itself.
  Rescaling it (0.3 for Jev and the student, 1.0 for the rules pilot) kept the absolute pace. Without that,
  a pilot with Jev's 0.45 s decision lag hit the wall in the scripted wall-follow test (0 px clear; with the
  rescale, 9 px; at the old engine, 35 px).
- A burn shorter than 2 frames was treated as noise, which at 4x thrust is a dead-band of 18 m/s in speed.
  The cutoff now scales with the engine (two frames at the reference engine, never below one), and is
  unchanged at the old engine. **This change was kept.**
- Fourteen hunter tests had constants tied to the old engine; they were rewritten in terms of the engine.

Measured against the old setup (thrust 0.25, cruise 2.0), the same absolute pace, 18 seeds:

| | tune | held-out |
|---|---|---|
| score | +2.5 (-5.2 to +9.9) | **-21.6 (-31.2 to -12.1)** |
| wall hits per min | **+0.77** | **+1.49** |
| enemy hits per min | **+0.54** | **+2.62** |

A 4x bigger pulse was ruled out as the cause (a 1.5-frame pulse scored -1.1, no effect). The cause is
unknown; coarser per-frame control is a guess.

## Decision

Reverted to 0.25 (`HunterSettings` and the `RuleParams` default; the cruise defaults are back to 0.6 for
Jev and the student and 2.0 for the rules pilot). The revert reproduces the reference baseline of 007 to
three decimals (53.553 tune, 72.174 held-out). The lab parameter and the widened range (0.1 to 6.0) stay,
so the result can be reproduced.

## Caveats

Hunter alone, player parked and hidden. Jev's behaviour at other thrusts was not measured (it needs the
API); only its latency model was checked, in the scripted wall-follow test. The student model was trained
at 0.25 and would need retraining at any other thrust.
