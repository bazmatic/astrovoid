# 010: The hunter's turn rate

Date: 2026-10-12. Setting: `HunterSettings.turn_rate_multiplier` (the hunter's turn rate as a share of the
player's; today 0.5). Lab parameter: `turn_rate_multiplier`, applied to the ship directly (the ship fixes it
when it is built; a test guards that it reaches the ship). Base: the rules defaults after 009 (sight 0.8).

## Hypothesis and prediction

008 suggested a stronger engine only helps if the hunter can steer to use it. Turning faster should cut
collisions (it steers its own momentum better) and help aiming.

## Coarse pass (candidate minus 0.5, tune set, 6 seeds = 72 episodes per arm)

| turn rate | score | kills, % per min | wall hits | enemy hits |
|---|---|---|---|---|
| 0.25 | **-26.9 (-40.7 to -13.5)** | -11.2 | **+3.99** | **+1.93** |
| 1.0 | +14.6 (-0.3 to +29.0) | +3.1 | **-2.34** | **-1.60** |
| 2.0 | **+24.3 (+10.7 to +38.1)** | +6.8 | **-2.76** | **-2.65** |
| 4.0 | **+27.1 (+13.9 to +41.5)** | +7.5 | **-2.99** | **-3.15** |

## Confirmation (18 seeds = 216 tune and 108 held-out episodes per arm)

| turn rate | set | score | kills, % per min | wall hits | enemy hits | idle |
|---|---|---|---|---|---|---|
| 1.0 | tune | **+18.2 (+10.3 to +26.1)** | +5.4 | **-2.26** | **-1.70** | +0.011 |
| 2.0 | tune | **+25.9 (+18.8 to +33.2)** | +7.3 | **-2.86** | **-2.68** | +0.007 |
| 2.0 | held-out | **+27.4 (+18.4 to +36.3)** | +7.1 | **-2.54** | **-3.36** | +0.001 |
| 4.0 | tune | **+31.6 (+24.2 to +38.9)** | +9.5 | **-3.10** | **-3.15** | -0.007 |
| 4.0 | held-out | **+23.7 (+14.0 to +33.5)** | +2.9 (-3.4 to +9.3) | **-3.19** | **-3.67** | +0.038 |

(Base scores: 78.7 on tune, 68.4 on held-out.)

## Interpretation

This is the strongest and most consistent result in the lab. It survived the larger sample and the held-out
set (about +27 at 2.0, where the other adopted changes were +5), unlike thrust (008). It works by cutting
collisions: wall hits fall from 3.7 to under 1 per minute and enemy hits from 4.6 to under 2, with the kill
rate rising a little. Unlike sensor range (009), which bought kills with extra collisions, this reduces
them. Gains flatten above 2.0: 4.0 is higher on tune but not on held-out, where its raw kill rate and idle
time are worse. A slower turn (0.25) is reliably disastrous.

## The cost the lab cannot see

A held left or right turns the ship for a whole decision. At 0.5 that is 68 degrees; at 1.0, 135; at 2.0,
**270**; at 4.0, 540. The tracking and navigator modes cap their turn at the exact angle needed, so they
are unaffected, and the lab's hunter flies almost entirely with them. But:
- Jev's rubric (and the student that copies it) uses held left and right, and `HunterSettings` carries the
  comment that the turn rate is set so held steering stays controllable.
- The rules pilot's follow-the-player branch uses held left and right inside a 20 degree band. The lab hides
  the player, so that branch is not exercised here.

## Decision

Adopted for the **rules pilot only**: `RULES.turn_rate_multiplier` is 2.0 (the best-measured setting and where
the gains flatten), and the game builds the hunter from `hunter_settings_for(game.hunterPilot)`
(`hunter/settings_for.py`), which gives the rules pilot's hunter that turn rate. Jev and the student keep
0.5, because their held left and right turns steer for a whole decision (68 degrees at 0.5, 270 at 2.0).
A test checks that the game's hunter and the lab's agree on thrust, sight and turn rate.

## New reference baseline (the rules defaults after this change)

6 seeds per level, 90 s horizon, frozen weights:

| term | tune mean | held-out mean |
|---|---|---|
| kills, % of all enemies per minute | 120.5 | 110.8 |
| kills per minute (raw, reported only) | 29.2 | 32.0 |
| wall hits per minute | 0.90 | 1.01 |
| hits taken per minute | 1.95 | 2.09 |
| idle fraction | 0.098 | 0.153 |
| **score** | **103.0** | **88.2** |

## Still to check by hand

The rules pilot's follow-the-player branch holds left or right inside a 20 degree band, and at 2.0 a held
decision turns the ship 270 degrees. The lab hides the player, so this branch has not been measured. Play
beside the hunter with `hunterPilot` set to `"rules"` and watch it keep station. If it flails, the fix is to
make that branch steer by exact angle (as the course and track modes do), not to lower the turn rate.
