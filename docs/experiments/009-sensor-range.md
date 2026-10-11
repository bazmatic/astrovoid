# 009: How far the hunter sees

Date: 2026-10-11. Setting: `HunterSettings.sensor_range_fraction` (today 0.4: the share of the maze's width
the hunter can see). Lab parameter: `sensor_range_fraction`. Base: `RULES` (as in 007). The lab applies the
setting to the hunter's perception and fire control (a test guards that it reaches the perception).

## Hypothesis and prediction

About a fifth of the hunter's time is spent idle with no enemy in sight. Seeing further should find
enemies sooner: less idle time and a higher kill rate, at some risk of more collisions.

## Coarse pass (candidate minus 0.4, tune set, 6 seeds = 72 episodes per arm)

| sight | score | kills, % per min | idle | wall hits | enemy hits |
|---|---|---|---|---|---|
| 0.2 | **-40.7 (-52.6 to -29.6)** | -33.5 | -0.023 | +0.74 | **+1.83** |
| 0.6 | **+20.0 (+7.7 to +32.4)** | +16.9 | -0.084 | +0.64 | +0.33 |
| 0.8 | **+25.2 (+13.4 to +37.3)** | +19.9 | -0.107 | +0.52 | +0.36 |
| 1.2 | **+23.9 (+12.0 to +35.9)** | +19.6 | -0.110 | +0.75 | +0.47 |

Monotone, and idle time falls steadily as sight grows. It plateaus from about 0.8 (1.0 is the full
width of the maze, so there is nothing more to see). Halving the sight is reliably catastrophic.

## Confirmation (18 seeds = 216 tune and 108 held-out episodes per arm)

| sight | set | score | kills, % per min | idle | wall hits | enemy hits |
|---|---|---|---|---|---|---|
| 0.6 | tune | **+18.6 (+12.1 to +25.1)** | +16.9 | -0.084 | +0.84 | +0.55 |
| 0.6 | held-out | +4.0 (-1.5 to +9.2) | +7.8 | -0.015 | +0.67 | +0.77 |
| 0.8 | tune | **+18.4 (+11.9 to +24.8)** | +16.3 | -0.083 | +0.69 | +0.55 |
| 0.8 | held-out | **+6.5 (+1.1 to +12.0)** | +10.0 | -0.029 | +0.81 | +0.88 |

(Base scores: 60.3 on tune, 61.9 on held-out.)

## Interpretation

Unlike thrust (008), this one survives the larger sample: the tune gain went from +25 to +18, not to
zero, and the held-out set (scored once, never used to choose) agrees in direction, with 0.8 clearing
zero. The held-out gain is about a third of the tune gain, so +6 is the number to believe. The cost is
real: wall hits (+0.7 to +0.8 per minute) and enemy hits (+0.55 on tune, +0.88 on held-out) both rose
reliably. The gain is kills and less idling, paid for in collisions.

## Decision

Best setting: 0.8 (it cleared zero on both sets; 0.6 did not on held-out). **Not yet adopted:** sight is a
property of the hunter that Jev and the student share, and the game builds the hunter with the default
`HunterSettings`. Adopting it for the rules pilot only needs a small hook in the game; adopting it for
everyone means changing the default (and retraining the student, which was trained at 0.4).

## Caveats

Hunter alone, player parked and hidden. The collision cost is real and the score weights treat it as
modest; a heavier penalty would shrink the gain. Jev's behaviour with a longer sight was not measured.
