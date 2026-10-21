# Frame times: Creatures, stages 1–2

Measured with `venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1`: a real `Game` on a
1352×878 surface, dummy video and audio, rules hunter pilot, 60 warm-up frames, then 600 timed frames. Each number is
the median of three runs. Times in milliseconds per frame.

Machine: Apple M2 Pro, macOS 26.3, Python 3.10.13, pygame 2.6.1. Date: 2026-10-20.

The gate: a frame (update + draw) on each level may be at most 20% slower than the baseline.

## Baseline (420b0e2)

Measured at `d3638c0`, which only adds docs on top of `420b0e2`.

| level | enemies | update_ms_mean | update_ms_p95 | draw_ms_mean | frame (update + draw) | 20% limit |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 0.161 | 0.176 | 3.131 | 3.292 | 3.950 |
| 8 | 33 | 1.422 | 1.829 | 3.455 | 4.877 | 5.852 |
| 9 | 22 | 1.959 | 2.558 | 4.627 | 6.586 | 7.903 |
| 40 | 32 | 1.428 | 1.734 | 7.990 | 9.418 | 11.302 |

## Dispatch gate (Task 2)

`venv/bin/python -m tools.frame_timer --levels 9 --frames 600 --seed 1 --creatures N`, N = 0 and N = 33, run
alternately three times each. The 33 test Creatures each have six traits whose `on_frame` does one attribute write,
and a Body that does nothing; the Encounter still finds each one's target every frame.

| N | update_ms_mean (three runs) | median |
|---:|---|---:|
| 0 | 2.398, 2.189, 2.105 | 2.189 |
| 33 | 2.223, 2.230, 2.243 | 2.230 |

33 creatures add **0.041 ms** per frame. The gate is 20% of level 8's baseline update time: 0.2 × 1.422 = 0.284 ms.
**Passed**, with the difference inside the run-to-run noise (the N = 0 runs alone spread by 0.29 ms).

With the skeleton in place and no kind moved yet, the four levels measure (medians of three) 0.176 / 1.426 / 2.001 /
1.442 ms update and 3.188 / 3.455 / 4.682 / 8.018 ms draw on levels 1 / 8 / 9 / 40: within 3% of the baseline.

## Second gate (Task 6): Urchin, Crab and Jelly are Creatures, `Enemy` deleted

Same command as the baseline, three runs, medians.

| level | update_ms_mean | update_ms_p95 | draw_ms_mean | frame (update + draw) | baseline frame | change |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.168 | 0.182 | 3.100 | 3.268 | 3.292 | −0.7% |
| 8 | 1.410 | 1.805 | 3.399 | 4.809 | 4.877 | −1.4% |
| 9 | 2.115 | 2.856 | 4.571 | 6.686 | 6.586 | +1.5% |
| 40 | 1.449 | 1.724 | 7.915 | 9.364 | 9.418 | −0.6% |

**Passed**: every level is well inside the 20% limit. Level 9 (20 Jellies) is the only one slower: its update is 8%
slower than the baseline (2.115 against 1.959 ms), about 0.16 ms a frame.

## Stage 3 gate: the four squids are Creatures

Measured on 2026-10-21 while another job's 12 training workers kept all 12 cores busy (load average 17 to 31). Wall
time was meaningless (two trees with identical squid code differed by 30%), so each frame was timed in **CPU time**
(`time.process_time`, the timer's own code otherwise unchanged), and three trees ran alternately, five rounds each:
`420b0e2` (the stage 1 baseline's code), `4479984` (this stage's start: stage 2 plus `main` merged in) and the commit that
deletes the old squid classes (this stage's end). Medians of five, update + draw, ms per frame.

| level | 420b0e2 | 4479984 | stage 3 | vs 420b0e2 | vs 4479984 | stage 3 spread |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.88 | 3.64 | 3.94 | +1.6% | +8.2% | 3.29–4.14 |
| 8 | 5.68 | 5.16 | 5.84 | +2.9% | +13.2% | 4.86–6.03 |
| 9 | 7.37 | 8.27 | 8.11 | +10.0% | −1.9% | 7.21–8.96 |
| 40 | 10.47 | 9.71 | 10.12 | −3.4% | +4.2% | 9.70–11.95 |
| 18 | 3.76 | 4.18 | 3.72 | −1.1% | −11.0% | 3.63–4.53 |
| 42 | 5.87 | 5.89 | 6.21 | +5.9% | +5.6% | 5.58–6.77 |
| 48 | 4.76 | 4.54 | 5.15 | +8.0% | +13.4% | 4.30–5.25 |

**Passed**: every level is inside 20% of both baselines; the largest change, +13.4%, is inside the run-to-run spread
(about 20% under this load). Level 9 has no squids: its +10% against `420b0e2` came with `main` (the crowd is now also
pushed out of walls each round). Re-measure on an idle machine to confirm.

## Stage 4 gate: the Egg, Anemone, Flocker and Flighthouse are Creatures

Measured on 2026-10-21, again under another job's training load (load average about 24), in **CPU time** as in stage 3.
Two clean worktrees ran alternately, five rounds each: `6f5eff6` (this stage's start) and `1e89c76` plus the commit
that deletes `EnemyUpdater` (this stage's end). Neither had the other session's uncommitted hunter work. Medians of
five, update + draw, ms per frame, 600 frames after 60 to warm up, seed 1.

| level | enemies | 6f5eff6 | stage 4 | change | stage 4 spread |
|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 4.20 | 4.32 | +2.8% | 3.96–4.40 |
| 7 | 21 | 7.60 | 7.67 | +0.9% | 7.33–8.24 |
| 8 | 33 | 5.66 | 5.90 | +4.1% | 5.39–6.25 |
| 9 | 22 | 8.96 | 8.38 | −6.6% | 7.48–9.04 |
| 15 | 25 | 6.60 | 6.95 | +5.3% | 6.70–7.52 |
| 18 | 5 | 4.28 | 4.58 | +7.0% | 4.15–4.77 |
| 40 | 32 | 11.36 | 12.82 | +12.8% | 12.09–13.26 |

**Passed**: every level is inside the 20% limit. Level 40 (all eight kinds moved so far, 32 enemies) is the largest,
mostly in drawing (+0.9 ms). Timing each kind's draw alone on that level shows no difference between the trees
(7.4 against 7.1 ms over all its enemies, and a whole `draw_game` 10.3 against 9.0 to 10.0), so the gap is the game
playing out differently: every Creature draws its starting angle, which shifts the random stream and with it what is
on screen.
